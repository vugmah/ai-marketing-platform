"""
AI Architecture service layer.

Provides 6 core services:
- OpenAIService: Async OpenAI API client with retry logic and cost estimation
- PromptTemplateService: CRUD and template rendering for AI prompts
- AISuggestionService: Marketing suggestion generation and feedback tracking
- RecommendationEngine: Data-driven recommendation generation and ranking
- AIUsageTracker: API usage logging, token/cost tracking, and limit enforcement
- AICacheService: Redis-based response caching with TTL and hit tracking
"""

import asyncio
import hashlib
import json
import logging
import time
import uuid
from datetime import datetime, timedelta
from typing import Any, Dict, List, Optional, Tuple

import httpx
from sqlalchemy import desc, func, select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.ai.constants import (
    CACHE_KEY_PREFIX_COMPLETION,
    CACHE_TTL_COMPLETION,
    CACHE_TTL_LONG,
    CACHE_TTL_MEDIUM,
    CIRCUIT_BREAKER_FAILURE_THRESHOLD,
    CIRCUIT_BREAKER_HALF_OPEN_MAX_CALLS,
    CIRCUIT_BREAKER_RECOVERY_TIMEOUT_SECONDS,
    COST_PER_1K_TOKENS,
    DEFAULT_CACHE_TTL,
    DEFAULT_COMPANY_RPM_LIMIT,
    DEFAULT_COMPANY_TPM_LIMIT,
    DEFAULT_MAX_TOKENS,
    DEFAULT_MODEL,
    DEFAULT_MONTHLY_COST_LIMIT_USD,
    DEFAULT_MONTHLY_TOKEN_LIMIT,
    DEFAULT_SYSTEM_PROMPT,
    DEFAULT_TEMPERATURE,
    DEFAULT_USER_DAILY_REQUEST_LIMIT,
    DEFAULT_USER_DAILY_TOKEN_LIMIT,
    FALLBACK_MESSAGE_CIRCUIT_OPEN,
    FALLBACK_MESSAGE_MODERATION_BLOCKED,
    FALLBACK_MESSAGE_NO_API_KEY,
    FALLBACK_MESSAGE_RATE_LIMITED,
    MAX_RETRIES,
    MAX_SUGGESTIONS_PER_REQUEST,
    MODERATION_ENABLED,
    MODERATION_REJECT_CATEGORIES,
    OPENAI_CHAT_COMPLETIONS_ENDPOINT,
    OPENAI_MODERATION_ENDPOINT,
    RECOMMENDATION_CATEGORIES,
    RECOMMENDATION_SYSTEM_PROMPT,
    RETRYABLE_STATUS_CODES,
    RETRY_BASE_DELAY_SECONDS,
    RETRY_EXPONENTIAL_BASE,
    RETRY_MAX_DELAY_SECONDS,
    STREAM_TIMEOUT_SECONDS,
    SUGGESTION_SYSTEM_PROMPT,
    SUGGESTION_TRIGGER_TYPES,
    USAGE_LIMIT_ALERT_THRESHOLD,
)
from app.ai.models import (
    AICache,
    AIConversation,
    AIMessage,
    AIModelName,
    AIPrompt,
    AIRecommendation,
    AIUsageLog,
    AISuggestion,
    ConversationStatus,
    MessageRole,
    RecommendationCategory,
    RecommendationStatus,
    SuggestionTriggerType,
    UserFeedback,
)
from app.exceptions import NotFoundError, ValidationError
from app.redis_client import get_cache

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# OpenAI Service
# ---------------------------------------------------------------------------

class CircuitBreakerState:
    """Circuit breaker state for OpenAI API calls.

    States: CLOSED (normal), OPEN (failing), HALF_OPEN (testing).
    """

    CLOSED = "closed"
    OPEN = "open"
    HALF_OPEN = "half_open"


class CircuitBreaker:
    """Simple in-memory circuit breaker for OpenAI API calls."""

    _instance = None

    def __new__(cls):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
            cls._instance.state = CircuitBreakerState.CLOSED
            cls._instance.failure_count = 0
            cls._instance.last_failure_time = None
            cls._instance.half_open_calls = 0
        return cls._instance

    def record_success(self) -> None:
        if self.state == CircuitBreakerState.HALF_OPEN:
            self.half_open_calls += 1
            if self.half_open_calls >= CIRCUIT_BREAKER_HALF_OPEN_MAX_CALLS:
                self.state = CircuitBreakerState.CLOSED
                self.failure_count = 0
                self.half_open_calls = 0
                logger.info("Circuit breaker: CLOSED (recovered after %d half-open successes)", CIRCUIT_BREAKER_HALF_OPEN_MAX_CALLS)
        elif self.state == CircuitBreakerState.CLOSED:
            self.failure_count = max(0, self.failure_count - 1)
        # OPEN state: success should not happen (can_execute returns False)

    def record_failure(self) -> None:
        self.failure_count += 1
        self.last_failure_time = time.time()
        if self.failure_count >= CIRCUIT_BREAKER_FAILURE_THRESHOLD:
            self.state = CircuitBreakerState.OPEN
            logger.error(
                "Circuit breaker: OPEN after %d failures", self.failure_count
            )

    def can_execute(self) -> bool:
        if self.state == CircuitBreakerState.CLOSED:
            return True
        if self.state == CircuitBreakerState.OPEN:
            elapsed = time.time() - (self.last_failure_time or 0)
            if elapsed >= CIRCUIT_BREAKER_RECOVERY_TIMEOUT_SECONDS:
                self.state = CircuitBreakerState.HALF_OPEN
                self.half_open_calls = 0
                logger.info("Circuit breaker: HALF_OPEN (testing recovery)")
                return True
            return False
        if self.state == CircuitBreakerState.HALF_OPEN:
            return self.half_open_calls < CIRCUIT_BREAKER_HALF_OPEN_MAX_CALLS
        return True

    def get_fallback_response(self, model: str) -> Dict[str, Any]:
        return {
            "content": FALLBACK_MESSAGE_CIRCUIT_OPEN,
            "model": model,
            "tokens_input": 0,
            "tokens_output": 0,
            "total_tokens": 0,
            "cost_estimate": 0.0,
            "latency_ms": 0,
            "finish_reason": "circuit_breaker",
            "raw_response": None,
            "fallback": True,
            "error": "CIRCUIT_BREAKER_OPEN",
        }


class OpenAIService:
    """
    Async OpenAI API client with retry logic, token counting, and cost estimation.

    Uses httpx for async HTTP requests with exponential backoff retry strategy.
    All API calls are logged through AIUsageTracker for cost monitoring.
    Includes graceful fallback when API key is missing, rate limiting,
    output moderation, and circuit breaker pattern.
    """

    def __init__(self, api_key: Optional[str] = None):
        """Initialize the OpenAI service.

        Args:
            api_key: OpenAI API key. If not provided, uses the one from config.
        """
        from app.config import settings

        self.api_key = api_key or getattr(settings, "OPENAI_API_KEY", "")
        self.supervised_mode = getattr(settings, "AI_SUPERVISED_MODE", True)
        self.base_url = "https://api.openai.com/v1"
        self.headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json",
        }
        self.timeout = STREAM_TIMEOUT_SECONDS
        self.circuit_breaker = CircuitBreaker()

    def _has_api_key(self) -> bool:
        """Check if API key is configured.

        Returns:
            True if API key is present and not empty.
        """
        return bool(self.api_key) and self.api_key.strip() != ""

    def _get_fallback_no_api_key(self, model: str) -> Dict[str, Any]:
        """Return graceful fallback response when API key is missing.

        Returns:
            Dict with fallback message and metadata.
        """
        return {
            "content": FALLBACK_MESSAGE_NO_API_KEY,
            "model": model,
            "tokens_input": 0,
            "tokens_output": 0,
            "total_tokens": 0,
            "cost_estimate": 0.0,
            "latency_ms": 0,
            "finish_reason": None,
            "raw_response": None,
            "fallback": True,
            "error": "AI_API_KEY_MISSING",
        }

    def _estimate_tokens(self, text: str) -> int:
        """Roughly estimate token count for a given text.

        Uses a conservative heuristic of ~4 characters per token.

        Args:
            text: Input text to estimate tokens for.

        Returns:
            Estimated token count.
        """
        if not text:
            return 0
        # Rough heuristic: ~4 characters per token on average
        return max(1, len(text) // 4)

    def _calculate_cost(
        self, model: str, tokens_input: int, tokens_output: int
    ) -> float:
        """Calculate the estimated cost for an API call.

        Args:
            model: The model name used.
            tokens_input: Number of input tokens.
            tokens_output: Number of output tokens.

        Returns:
            Estimated cost in USD.
        """
        model_costs = COST_PER_1K_TOKENS.get(model, COST_PER_1K_TOKENS[DEFAULT_MODEL])
        input_cost = (tokens_input / 1000.0) * model_costs["input"]
        output_cost = (tokens_output / 1000.0) * model_costs["output"]
        return round(input_cost + output_cost, 6)

    def _get_retry_delay(self, attempt: int) -> float:
        """Calculate exponential backoff delay for a retry attempt.

        Args:
            attempt: The current retry attempt number (0-indexed).

        Returns:
            Delay in seconds before the next retry.
        """
        delay = RETRY_BASE_DELAY_SECONDS * (RETRY_EXPONENTIAL_BASE ** attempt)
        return min(delay, RETRY_MAX_DELAY_SECONDS)

    def estimate_request_cost(
        self,
        messages: List[Dict[str, str]],
        model: str = DEFAULT_MODEL,
        max_tokens: Optional[int] = None,
    ) -> Dict[str, Any]:
        """Pre-calculate estimated cost before making the API call.

        Args:
            messages: List of message dicts with 'role' and 'content' keys.
            model: Model name to use.
            max_tokens: Maximum tokens to generate.

        Returns:
            Dict with cost estimate breakdown.
        """
        estimated_input_tokens = sum(
            self._estimate_tokens(m.get("content", "")) for m in messages
        )
        estimated_output_tokens = max_tokens or DEFAULT_MAX_TOKENS
        input_cost = self._calculate_cost(model, estimated_input_tokens, 0)
        output_cost = self._calculate_cost(model, 0, estimated_output_tokens)
        total_cost = input_cost + output_cost

        return {
            "model": model,
            "estimated_input_tokens": estimated_input_tokens,
            "estimated_output_tokens": estimated_output_tokens,
            "estimated_total_tokens": estimated_input_tokens + estimated_output_tokens,
            "estimated_input_cost_usd": round(input_cost, 6),
            "estimated_output_cost_usd": round(output_cost, 6),
            "estimated_total_cost_usd": round(total_cost, 6),
        }

    async def check_rate_limit(
        self,
        company_id: Optional[int] = None,
        user_id: Optional[int] = None,
        estimated_tokens: int = 0,
    ) -> Tuple[bool, Dict[str, Any]]:
        """Check per-company and per-user rate limits.

        Uses Redis for rate limit tracking (sliding window).

        Args:
            company_id: Company ID for rate limit check.
            user_id: User ID for rate limit check.
            estimated_tokens: Estimated tokens for this request.

        Returns:
            Tuple of (allowed, rate_limit_info).
        """
        rate_info = {
            "company_allowed": True,
            "user_allowed": True,
            "company_rpm_remaining": DEFAULT_COMPANY_RPM_LIMIT,
            "user_daily_remaining": DEFAULT_USER_DAILY_REQUEST_LIMIT,
            "reason": None,
        }

        if not company_id and not user_id:
            return True, rate_info

        try:
            cache = await get_cache()
            now = int(time.time())
            window_minute = now // 60
            window_day = now // 86400

            # Per-company rate limit (requests per minute)
            if company_id:
                company_key = f"ai:rate_limit:company:{company_id}:{window_minute}"
                company_requests = await cache.increment(company_key, 1)
                if company_requests == 1:
                    await cache.expire(company_key, 60)
                rate_info["company_rpm_remaining"] = max(
                    0, DEFAULT_COMPANY_RPM_LIMIT - company_requests
                )
                if company_requests > DEFAULT_COMPANY_RPM_LIMIT:
                    rate_info["company_allowed"] = False
                    rate_info["reason"] = f"Company rate limit exceeded ({DEFAULT_COMPANY_RPM_LIMIT} RPM)"

            # Per-user rate limit (daily requests)
            if user_id:
                user_key = f"ai:rate_limit:user:{user_id}:{window_day}"
                user_requests = await cache.increment(user_key, 1)
                if user_requests == 1:
                    await cache.expire(user_key, 86400)
                rate_info["user_daily_remaining"] = max(
                    0, DEFAULT_USER_DAILY_REQUEST_LIMIT - user_requests
                )
                if user_requests > DEFAULT_USER_DAILY_REQUEST_LIMIT:
                    rate_info["user_allowed"] = False
                    rate_info["reason"] = f"User daily limit exceeded ({DEFAULT_USER_DAILY_REQUEST_LIMIT})"

            return rate_info["company_allowed"] and rate_info["user_allowed"], rate_info

        except Exception as exc:
            logger.warning("Rate limit check error: %s", str(exc))
            # Allow request if rate limit check fails
            return True, rate_info

    async def moderate_content(self, content: str) -> Tuple[bool, Dict[str, Any]]:
        """Check content against OpenAI moderation API.

        Args:
            content: The text content to moderate.

        Returns:
            Tuple of (is_safe, moderation_result).
            is_safe is True if content passes moderation.
        """
        if not MODERATION_ENABLED:
            return True, {"flagged": False, "categories": {}}

        if not self._has_api_key():
            return True, {"flagged": False, "categories": {}, "skipped": True}

        try:
            async with httpx.AsyncClient(timeout=30.0) as client:
                response = await client.post(
                    OPENAI_MODERATION_ENDPOINT,
                    headers=self.headers,
                    json={"input": content[:2000]},  # Limit to 2000 chars
                )
                response.raise_for_status()
                result = response.json()

                flagged = False
                categories = {}

                if "results" in result and result["results"]:
                    moderation = result["results"][0]
                    flagged = moderation.get("flagged", False)
                    categories = moderation.get("categories", {})
                    category_scores = moderation.get("category_scores", {})

                    # Check reject categories
                    for category in MODERATION_REJECT_CATEGORIES:
                        if categories.get(category, False):
                            logger.warning(
                                "Content flagged by moderation: category=%s", category
                            )
                            flagged = True

                return not flagged, {
                    "flagged": flagged,
                    "categories": categories,
                    "category_scores": category_scores,
                }

        except Exception as exc:
            logger.warning("Moderation check failed: %s", str(exc))
            # Allow content if moderation check fails
            return True, {"flagged": False, "categories": {}, "error": str(exc)}

    async def create_chat_completion(
        self,
        messages: List[Dict[str, str]],
        model: str = DEFAULT_MODEL,
        temperature: Optional[float] = None,
        max_tokens: Optional[int] = None,
        stream: bool = False,
        company_id: Optional[int] = None,
        user_id: Optional[int] = None,
        branch_id: Optional[int] = None,
        prompt_id: Optional[int] = None,
        db: Optional[Any] = None,
    ) -> Dict[str, Any]:
        """Create a chat completion with retry logic and usage tracking.

        Args:
            messages: List of message dicts with 'role' and 'content' keys.
            model: Model name to use.
            temperature: Sampling temperature (0.0-2.0).
            max_tokens: Maximum tokens to generate.
            stream: Whether to stream the response.
            company_id: Company ID for usage tracking.
            user_id: User ID for usage tracking.
            branch_id: Branch ID for branch-aware analytics.
            prompt_id: Prompt template ID used for this request.
            db: Database session for quota checks.

        Returns:
            Dict containing the completion response with usage metadata.
            Returns graceful fallback if API key is missing or rate limited.

        Raises:
            ValidationError: If the API key is not configured and fallback is disabled.
            Exception: If all retries are exhausted.
        """
        # ------------------------------------------------------------------
        # 1. Check API key - return graceful fallback if missing
        # ------------------------------------------------------------------
        if not self._has_api_key():
            logger.warning("OpenAI API key not configured - returning graceful fallback")
            return self._get_fallback_no_api_key(model)

        # ------------------------------------------------------------------
        # 2. Check circuit breaker
        # ------------------------------------------------------------------
        if not self.circuit_breaker.can_execute():
            logger.warning("Circuit breaker is OPEN - returning fallback response")
            return self.circuit_breaker.get_fallback_response(model)

        # ------------------------------------------------------------------
        # 3. Pre-request cost estimation
        # ------------------------------------------------------------------
        cost_estimate = self.estimate_request_cost(messages, model, max_tokens)
        logger.info(
            "AI cost estimate: model=%s input_tokens=%d output_tokens=%d cost=$%.6f",
            model,
            cost_estimate["estimated_input_tokens"],
            cost_estimate["estimated_output_tokens"],
            cost_estimate["estimated_total_cost_usd"],
        )

        # ------------------------------------------------------------------
        # 4. Check per-company quota (daily/monthly) - via AIUsageTracker
        # ------------------------------------------------------------------
        if company_id and db:
            tracker = AIUsageTracker(db)
            within_quota, quota_info = await tracker.check_company_quota(
                company_id=company_id,
            )
            if not within_quota:
                logger.warning("Company quota exceeded: %s", quota_info.get("reason"))
                return {
                    "content": (
                        "AI kullanim limiti asildi. "
                        "Lutfen yonetici ile iletisime gecin."
                    ),
                    "model": model,
                    "tokens_input": cost_estimate["estimated_input_tokens"],
                    "tokens_output": 0,
                    "total_tokens": cost_estimate["estimated_input_tokens"],
                    "cost_estimate": 0.0,
                    "latency_ms": 0,
                    "finish_reason": None,
                    "raw_response": None,
                    "fallback": True,
                    "error": "QUOTA_EXCEEDED",
                    "quota_info": quota_info,
                    "supervised": self.supervised_mode,
                }

        # ------------------------------------------------------------------
        # 5. Check rate limits (per-company RPM, per-user daily)
        # ------------------------------------------------------------------
        estimated_tokens = cost_estimate["estimated_input_tokens"]
        rate_allowed, rate_info = await self.check_rate_limit(
            company_id=company_id,
            user_id=user_id,
            estimated_tokens=estimated_tokens,
        )
        if not rate_allowed:
            logger.warning("Rate limit exceeded: %s", rate_info.get("reason"))
            return {
                "content": FALLBACK_MESSAGE_RATE_LIMITED,
                "model": model,
                "tokens_input": estimated_tokens,
                "tokens_output": 0,
                "total_tokens": estimated_tokens,
                "cost_estimate": 0.0,
                "latency_ms": 0,
                "finish_reason": None,
                "raw_response": None,
                "fallback": True,
                "error": "RATE_LIMIT_EXCEEDED",
                "rate_limit_info": rate_info,
                "supervised": self.supervised_mode,
            }

        # ------------------------------------------------------------------
        # 6. Check moderation on user messages
        # ------------------------------------------------------------------
        user_content = " ".join(
            m.get("content", "") for m in messages if m.get("role") == "user"
        )
        moderation_result = None
        if user_content:
            is_safe, mod_result = await self.moderate_content(user_content)
            moderation_result = mod_result
            if not is_safe:
                logger.warning("Content blocked by moderation: %s", mod_result)
                return {
                    "content": FALLBACK_MESSAGE_MODERATION_BLOCKED,
                    "model": model,
                    "tokens_input": estimated_tokens,
                    "tokens_output": 0,
                    "total_tokens": estimated_tokens,
                    "cost_estimate": 0.0,
                    "latency_ms": 0,
                    "finish_reason": None,
                    "raw_response": None,
                    "fallback": True,
                    "error": "MODERATION_BLOCKED",
                    "moderation": mod_result,
                    "supervised": self.supervised_mode,
                }

        # ------------------------------------------------------------------
        # 7. Build payload and call API with retry
        # ------------------------------------------------------------------
        payload = {
            "model": model,
            "messages": messages,
            "stream": stream,
        }
        if temperature is not None:
            payload["temperature"] = temperature
        if max_tokens is not None:
            payload["max_tokens"] = max_tokens

        start_time = time.time()
        last_exception: Optional[Exception] = None

        for attempt in range(MAX_RETRIES):
            try:
                async with httpx.AsyncClient(
                    timeout=self.timeout,
                    headers=self.headers,
                ) as client:
                    response = await client.post(
                        OPENAI_CHAT_COMPLETIONS_ENDPOINT,
                        json=payload,
                    )

                    # Handle rate limiting (429) with retry
                    if response.status_code == 429:
                        retry_after = int(
                            response.headers.get("Retry-After", self._get_retry_delay(attempt))
                        )
                        logger.warning(
                            "OpenAI rate limit hit, retrying after %d seconds (attempt %d/%d)",
                            retry_after,
                            attempt + 1,
                            MAX_RETRIES,
                        )
                        await asyncio.sleep(retry_after)
                        continue

                    # Handle retryable errors
                    if response.status_code in RETRYABLE_STATUS_CODES:
                        delay = self._get_retry_delay(attempt)
                        logger.warning(
                            "OpenAI returned %d, retrying in %.1fs (attempt %d/%d)",
                            response.status_code,
                            delay,
                            attempt + 1,
                            MAX_RETRIES,
                        )
                        await asyncio.sleep(delay)
                        continue

                    response.raise_for_status()
                    result = response.json()

                    # Calculate metrics
                    latency_ms = int((time.time() - start_time) * 1000)
                    usage = result.get("usage", {})
                    tokens_input = usage.get("prompt_tokens", 0)
                    tokens_output = usage.get("completion_tokens", 0)
                    total_tokens = usage.get("total_tokens", tokens_input + tokens_output)
                    cost = self._calculate_cost(model, tokens_input, tokens_output)

                    # Extract finish reason
                    choices = result.get("choices", [])
                    finish_reason = choices[0].get("finish_reason") if choices else None

                    # Record success in circuit breaker
                    self.circuit_breaker.record_success()

                    response_content = (
                        choices[0].get("message", {}).get("content", "")
                        if choices and not stream else ""
                    )

                    return {
                        "content": response_content,
                        "model": result.get("model", model),
                        "tokens_input": tokens_input,
                        "tokens_output": tokens_output,
                        "total_tokens": total_tokens,
                        "cost_estimate": cost,
                        "latency_ms": latency_ms,
                        "finish_reason": finish_reason,
                        "raw_response": result,
                        "fallback": False,
                        "supervised": self.supervised_mode,
                        "requires_approval": self.supervised_mode,
                        "cost_estimate_pre": cost_estimate["estimated_total_cost_usd"],
                        "moderation": moderation_result,
                        "prompt_id": prompt_id,
                        "branch_id": branch_id,
                    }

            except httpx.HTTPStatusError as exc:
                last_exception = exc
                status_code = exc.response.status_code
                if status_code in RETRYABLE_STATUS_CODES or status_code == 429:
                    delay = self._get_retry_delay(attempt)
                    await asyncio.sleep(delay)
                    continue
                # Non-retryable error - record failure in circuit breaker
                self.circuit_breaker.record_failure()
                raise ValidationError(
                    f"OpenAI API error: {status_code} - {exc.response.text}"
                ) from exc

            except (httpx.ConnectError, httpx.TimeoutException, httpx.ReadTimeout) as exc:
                last_exception = exc
                delay = self._get_retry_delay(attempt)
                logger.warning(
                    "OpenAI connection error on attempt %d/%d: %s. Retrying in %.1fs",
                    attempt + 1,
                    MAX_RETRIES,
                    str(exc),
                    delay,
                )
                self.circuit_breaker.record_failure()
                await asyncio.sleep(delay)
                continue

            except Exception as exc:
                last_exception = exc
                self.circuit_breaker.record_failure()
                logger.error(
                    "Unexpected error calling OpenAI API (attempt %d/%d): %s",
                    attempt + 1,
                    MAX_RETRIES,
                    str(exc),
                )
                raise

        # All retries exhausted
        self.circuit_breaker.record_failure()
        logger.error("OpenAI API failed after %d retries", MAX_RETRIES)
        # Return graceful fallback instead of raising
        return {
            "content": FALLBACK_MESSAGE_CIRCUIT_OPEN,
            "model": model,
            "tokens_input": 0,
            "tokens_output": 0,
            "total_tokens": 0,
            "cost_estimate": 0.0,
            "latency_ms": 0,
            "finish_reason": "max_retries_exceeded",
            "raw_response": None,
            "fallback": True,
            "error": "MAX_RETRIES_EXCEEDED",
            "error_detail": str(last_exception),
            "supervised": self.supervised_mode,
        }


# ---------------------------------------------------------------------------
# Prompt Template Service
# ---------------------------------------------------------------------------

class PromptTemplateService:
    """
    CRUD operations and template rendering for AI prompt templates.

    Manages reusable prompt templates with variable substitution
    and validation for the AI marketing platform.
    """

    def __init__(self, db: AsyncSession):
        """Initialize the service with a database session.

        Args:
            db: Async SQLAlchemy session.
        """
        self.db = db

    async def create_prompt(self, data: Dict[str, Any]) -> AIPrompt:
        """Create a new AI prompt template.

        Args:
            data: Dictionary with prompt template fields.

        Returns:
            The created AIPrompt instance.

        Raises:
            ValidationError: If required fields are missing or model is invalid.
        """
        model_name = data.get("model_name", DEFAULT_MODEL)
        if model_name not in [m.value for m in AIModelName]:
            raise ValidationError(f"Invalid model name: {model_name}")

        prompt = AIPrompt(
            company_id=data["company_id"],
            branch_id=data.get("branch_id"),
            name=data["name"],
            description=data.get("description"),
            system_prompt=data["system_prompt"],
            user_prompt_template=data["user_prompt_template"],
            model_name=AIModelName(model_name),
            temperature=data.get("temperature", DEFAULT_TEMPERATURE),
            max_tokens=data.get("max_tokens", 2048),
            variables=data.get("variables", []),
            is_active=data.get("is_active", True),
        )
        self.db.add(prompt)
        await self.db.commit()
        await self.db.refresh(prompt)
        logger.info("Created AI prompt template id=%d name='%s'", prompt.id, prompt.name)
        return prompt

    async def get_prompt(self, prompt_id: int, company_id: int) -> AIPrompt:
        """Get a prompt template by ID with tenant check.

        Args:
            prompt_id: The prompt template ID.
            company_id: The company ID for tenant isolation.

        Returns:
            The AIPrompt instance.

        Raises:
            NotFoundError: If the prompt is not found.
        """
        result = await self.db.execute(
            select(AIPrompt).where(
                AIPrompt.id == prompt_id,
                AIPrompt.company_id == company_id,
            )
        )
        prompt = result.scalar_one_or_none()
        if not prompt:
            raise NotFoundError(f"Prompt template {prompt_id} not found")
        return prompt

    async def list_prompts(
        self,
        company_id: int,
        branch_id: Optional[int] = None,
        active_only: bool = True,
        page: int = 1,
        page_size: int = 20,
    ) -> Tuple[List[AIPrompt], int]:
        """List prompt templates with optional filtering.

        Args:
            company_id: The company ID for tenant isolation.
            branch_id: Optional branch ID filter.
            active_only: Whether to filter to active prompts only.
            page: Page number (1-indexed).
            page_size: Items per page.

        Returns:
            Tuple of (list of prompts, total count).
        """
        query = select(AIPrompt).where(AIPrompt.company_id == company_id)

        if branch_id is not None:
            query = query.where(
                (AIPrompt.branch_id == branch_id) | (AIPrompt.branch_id.is_(None))
            )
        if active_only:
            query = query.where(AIPrompt.is_active.is_(True))

        # Count total
        count_query = select(func.count()).select_from(query.subquery())
        total_result = await self.db.execute(count_query)
        total = total_result.scalar() or 0

        # Paginated results
        query = query.order_by(AIPrompt.created_at.desc())
        query = query.offset((page - 1) * page_size).limit(page_size)
        result = await self.db.execute(query)
        prompts = result.scalars().all()

        return list(prompts), total

    async def update_prompt(
        self, prompt_id: int, company_id: int, data: Dict[str, Any]
    ) -> AIPrompt:
        """Update a prompt template.

        Args:
            prompt_id: The prompt template ID.
            company_id: The company ID for tenant isolation.
            data: Dictionary of fields to update.

        Returns:
            The updated AIPrompt instance.

        Raises:
            NotFoundError: If the prompt is not found.
        """
        prompt = await self.get_prompt(prompt_id, company_id)

        updateable_fields = [
            "name", "description", "system_prompt", "user_prompt_template",
            "temperature", "max_tokens", "variables", "is_active",
        ]
        for field in updateable_fields:
            if field in data and data[field] is not None:
                setattr(prompt, field, data[field])

        if "model_name" in data and data["model_name"] is not None:
            model_name = data["model_name"]
            if model_name not in [m.value for m in AIModelName]:
                raise ValidationError(f"Invalid model name: {model_name}")
            prompt.model_name = AIModelName(model_name)

        prompt.updated_at = datetime.utcnow()
        await self.db.commit()
        await self.db.refresh(prompt)
        logger.info("Updated AI prompt template id=%d", prompt.id)
        return prompt

    async def delete_prompt(self, prompt_id: int, company_id: int) -> None:
        """Soft delete a prompt template by marking it inactive.

        Args:
            prompt_id: The prompt template ID.
            company_id: The company ID for tenant isolation.

        Raises:
            NotFoundError: If the prompt is not found.
        """
        prompt = await self.get_prompt(prompt_id, company_id)
        prompt.is_active = False
        prompt.updated_at = datetime.utcnow()
        await self.db.commit()
        logger.info("Soft-deleted AI prompt template id=%d", prompt.id)

    def render_template(self, template: str, variables: Dict[str, Any]) -> str:
        """Render a prompt template with variable substitution.

        Uses Jinja2-style {{variable}} syntax for placeholders.

        Args:
            template: The template string with placeholders.
            variables: Dictionary of variable names to values.

        Returns:
            The rendered template string.
        """
        rendered = template
        for key, value in variables.items():
            placeholder = f"{{{{{key}}}}}"
            rendered = rendered.replace(placeholder, str(value))
        return rendered

    def validate_template(self, template: str, variables: List[str]) -> List[str]:
        """Validate a template by checking that all referenced variables exist.

        Args:
            template: The template string to validate.
            variables: List of defined variable names.

        Returns:
            List of missing variable names, empty if all are defined.
        """
        import re
        referenced = re.findall(r"\{\{(\w+)\}\}", template)
        variable_set = set(variables)
        missing = [v for v in referenced if v not in variable_set]
        return missing

    async def get_branch_aware_prompt(
        self,
        company_id: int,
        branch_id: Optional[int] = None,
        prompt_id: Optional[int] = None,
        category: Optional[str] = None,
    ) -> Optional[AIPrompt]:
        """Get the best prompt template for a company/branch context.

        Selection priority:
        1. If prompt_id provided: return that specific prompt (with tenant check)
        2. Branch-specific prompt (branch_aware=True, matching branch_id)
        3. Company-wide default prompt (is_default=True, branch_id IS NULL)
        4. Any active prompt for the company
        5. None (use built-in defaults)

        Args:
            company_id: The company ID for tenant isolation.
            branch_id: Optional branch ID for branch-specific selection.
            prompt_id: Optional specific prompt template ID.
            category: Optional category filter.

        Returns:
            The best AIPrompt instance or None.
        """
        # 1. Specific prompt ID requested
        if prompt_id:
            try:
                return await self.get_prompt(prompt_id, company_id)
            except NotFoundError:
                logger.warning(
                    "Requested prompt_id=%d not found for company=%d",
                    prompt_id, company_id,
                )

        query = select(AIPrompt).where(
            AIPrompt.company_id == company_id,
            AIPrompt.is_active.is_(True),
        )

        if category:
            query = query.where(AIPrompt.category == category)

        # 2. Branch-specific prompt
        if branch_id is not None:
            branch_query = query.where(
                AIPrompt.branch_aware.is_(True),
                AIPrompt.branch_id == branch_id,
            )
            result = await self.db.execute(branch_query)
            branch_prompt = result.scalar_one_or_none()
            if branch_prompt:
                logger.info(
                    "Selected branch-specific prompt id=%d branch=%d",
                    branch_prompt.id, branch_id,
                )
                return branch_prompt

        # 3. Company-wide default prompt
        default_query = query.where(
            AIPrompt.is_default.is_(True),
            AIPrompt.branch_id.is_(None),
        )
        result = await self.db.execute(default_query)
        default_prompt = result.scalar_one_or_none()
        if default_prompt:
            logger.info(
                "Selected company default prompt id=%d", default_prompt.id,
            )
            return default_prompt

        # 4. Any active prompt for the company (non-branch-aware)
        fallback_query = query.where(
            AIPrompt.branch_id.is_(None),
        ).order_by(AIPrompt.created_at.desc()).limit(1)
        result = await self.db.execute(fallback_query)
        fallback_prompt = result.scalar_one_or_none()
        if fallback_prompt:
            logger.info(
                "Selected fallback prompt id=%d", fallback_prompt.id,
            )
            return fallback_prompt

        logger.info("No prompt template found for company=%d", company_id)
        return None


# ---------------------------------------------------------------------------
# AI Suggestion Service
# ---------------------------------------------------------------------------

class AISuggestionService:
    """
    Service for generating and managing AI marketing suggestions.

    Generates contextual marketing suggestions (content ideas, timing,
    audience targeting, etc.) and tracks user feedback for improvement.
    """

    def __init__(
        self,
        db: AsyncSession,
        openai_service: Optional[OpenAIService] = None,
    ):
        """Initialize the service.

        Args:
            db: Async SQLAlchemy session.
            openai_service: Optional OpenAIService instance.
        """
        self.db = db
        self.openai = openai_service or OpenAIService()

    async def generate_suggestions(
        self,
        company_id: int,
        branch_id: Optional[int],
        trigger_type: str,
        context: Dict[str, Any],
        count: int = 3,
    ) -> List[AISuggestion]:
        """Generate AI marketing suggestions for a given context.

        Args:
            company_id: The company ID for tenant isolation.
            branch_id: Optional branch ID.
            trigger_type: Type of suggestion to generate.
            context: Contextual data for the suggestion generation.
            count: Number of suggestions to generate.

        Returns:
            List of created AISuggestion instances.

        Raises:
            ValidationError: If trigger_type is invalid.
        """
        if trigger_type not in SUGGESTION_TRIGGER_TYPES:
            raise ValidationError(
                f"Invalid trigger_type. Must be one of: {', '.join(SUGGESTION_TRIGGER_TYPES)}"
            )

        count = min(count, MAX_SUGGESTIONS_PER_REQUEST)

        # Build the system and user prompts
        system_prompt = SUGGESTION_SYSTEM_PROMPT

        user_prompt = (
            f"Generate {count} marketing suggestions for trigger type: {trigger_type}.\n\n"
            f"Context:\n{json.dumps(context, indent=2, default=str)}\n\n"
            "For each suggestion, provide:\n"
            "- title: A concise, actionable title\n"
            "- description: Detailed explanation with reasoning\n"
            "- confidence: Estimated impact confidence (0.0-1.0)\n"
            "Format as a JSON array."
        )

        messages = [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_prompt},
        ]

        # Call OpenAI API
        result = await self.openai.create_chat_completion(
            messages=messages,
            model=DEFAULT_MODEL,
            temperature=0.7,
            max_tokens=2048,
            company_id=company_id,
        )

        # Handle fallback responses
        if result.get("fallback", False):
            raise ValidationError(
                f"AI service unavailable: {result.get('error', 'Unknown error')}"
            )

        # Parse the response content
        raw_content = result["content"]

        # Store the suggestion
        suggestion = AISuggestion(
            company_id=company_id,
            branch_id=branch_id,
            trigger_type=SuggestionTriggerType(trigger_type),
            context=context,
            prompt_used=user_prompt,
            response=raw_content,
            tokens_used=result["total_tokens"],
            model=AIModelName(result["model"]),
            was_applied=False,
        )
        self.db.add(suggestion)
        await self.db.commit()
        await self.db.refresh(suggestion)

        logger.info(
            "Generated AI suggestion id=%d trigger=%s company=%d",
            suggestion.id,
            trigger_type,
            company_id,
        )
        return [suggestion]

    async def list_suggestions(
        self,
        company_id: int,
        branch_id: Optional[int] = None,
        trigger_type: Optional[str] = None,
        page: int = 1,
        page_size: int = 20,
    ) -> Tuple[List[AISuggestion], int]:
        """List AI suggestions with optional filtering.

        Args:
            company_id: The company ID for tenant isolation.
            branch_id: Optional branch ID filter.
            trigger_type: Optional trigger type filter.
            page: Page number (1-indexed).
            page_size: Items per page.

        Returns:
            Tuple of (list of suggestions, total count).
        """
        query = select(AISuggestion).where(AISuggestion.company_id == company_id)

        if branch_id is not None:
            query = query.where(
                (AISuggestion.branch_id == branch_id)
                | (AISuggestion.branch_id.is_(None))
            )
        if trigger_type:
            query = query.where(AISuggestion.trigger_type == trigger_type)

        # Count total
        count_query = select(func.count()).select_from(query.subquery())
        total_result = await self.db.execute(count_query)
        total = total_result.scalar() or 0

        # Paginated results
        query = query.order_by(desc(AISuggestion.created_at))
        query = query.offset((page - 1) * page_size).limit(page_size)
        result = await self.db.execute(query)
        suggestions = result.scalars().all()

        return list(suggestions), total

    async def submit_feedback(
        self,
        suggestion_id: int,
        company_id: int,
        feedback: str,
        notes: Optional[str] = None,
    ) -> AISuggestion:
        """Submit user feedback for a suggestion.

        Args:
            suggestion_id: The suggestion ID.
            company_id: The company ID for tenant isolation.
            feedback: Feedback type (helpful, not_helpful, applied, dismissed).
            notes: Optional feedback notes.

        Returns:
            The updated AISuggestion instance.

        Raises:
            NotFoundError: If the suggestion is not found.
            ValidationError: If feedback type is invalid.
        """
        if feedback not in [f.value for f in UserFeedback]:
            raise ValidationError(
                f"Invalid feedback. Must be one of: {', '.join(f.value for f in UserFeedback)}"
            )

        result = await self.db.execute(
            select(AISuggestion).where(
                AISuggestion.id == suggestion_id,
                AISuggestion.company_id == company_id,
            )
        )
        suggestion = result.scalar_one_or_none()
        if not suggestion:
            raise NotFoundError(f"Suggestion {suggestion_id} not found")

        suggestion.user_feedback = UserFeedback(feedback)
        if feedback == "applied":
            suggestion.was_applied = True

        await self.db.commit()
        await self.db.refresh(suggestion)
        logger.info(
            "Submitted feedback for suggestion id=%d feedback=%s",
            suggestion_id,
            feedback,
        )
        return suggestion


# ---------------------------------------------------------------------------
# Recommendation Engine
# ---------------------------------------------------------------------------

class RecommendationEngine:
    """
    Service for generating and managing AI marketing recommendations.

    Generates data-driven recommendations based on analytics data,
    ranks them by confidence score, and tracks applied/dismissed status.
    """

    def __init__(
        self,
        db: AsyncSession,
        openai_service: Optional[OpenAIService] = None,
    ):
        """Initialize the recommendation engine.

        Args:
            db: Async SQLAlchemy session.
            openai_service: Optional OpenAIService instance.
        """
        self.db = db
        self.openai = openai_service or OpenAIService()

    async def generate_recommendations(
        self,
        company_id: int,
        branch_id: Optional[int],
        categories: Optional[List[str]] = None,
        context: Dict[str, Any] = None,
        count: int = 5,
    ) -> List[AIRecommendation]:
        """Generate AI marketing recommendations based on analytics data.

        Args:
            company_id: The company ID for tenant isolation.
            branch_id: Optional branch ID.
            categories: Optional list of recommendation categories to filter by.
            context: Analytics data context for recommendation generation.
            count: Number of recommendations to generate.

        Returns:
            List of created AIRecommendation instances.

        Raises:
            ValidationError: If categories contain invalid values.
        """
        if categories is None:
            categories = RECOMMENDATION_CATEGORIES

        invalid = [c for c in categories if c not in RECOMMENDATION_CATEGORIES]
        if invalid:
            raise ValidationError(
                f"Invalid categories: {', '.join(invalid)}. "
                f"Must be one of: {', '.join(RECOMMENDATION_CATEGORIES)}"
            )

        context = context or {}

        system_prompt = RECOMMENDATION_SYSTEM_PROMPT

        user_prompt = (
            f"Generate {count} marketing recommendations for the following categories: "
            f"{', '.join(categories)}.\n\n"
            f"Analytics Context:\n{json.dumps(context, indent=2, default=str)}\n\n"
            "For each recommendation, provide:\n"
            "- category: One of (content/timing/audience/channel/budget/creative)\n"
            "- title: A clear, actionable title\n"
            "- description: Detailed explanation with expected impact\n"
            "- confidence_score: Confidence level (0.0-1.0)\n"
            "- data_source: What data informed this recommendation\n"
            "- action_items: Array of specific actionable steps\n"
            "Format as a JSON array."
        )

        messages = [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_prompt},
        ]

        result = await self.openai.create_chat_completion(
            messages=messages,
            model=DEFAULT_MODEL,
            temperature=0.6,
            max_tokens=3000,
            company_id=company_id,
        )

        # Handle fallback responses
        if result.get("fallback", False):
            raise ValidationError(
                f"AI service unavailable: {result.get('error', 'Unknown error')}"
            )

        # Parse recommendations from response
        raw_content = result["content"]
        recommendations: List[AIRecommendation] = []

        try:
            parsed = json.loads(raw_content)
            if isinstance(parsed, list):
                items = parsed
            elif isinstance(parsed, dict) and "recommendations" in parsed:
                items = parsed["recommendations"]
            else:
                items = [parsed]
        except (json.JSONDecodeError, TypeError):
            # If JSON parsing fails, create a single recommendation with the raw text
            items = [{
                "category": categories[0] if categories else "content",
                "title": "AI Analysis",
                "description": raw_content[:1000],
                "confidence_score": 0.7,
                "data_source": "ai_analysis",
                "action_items": [],
            }]

        for item in items[:count]:
            try:
                category = item.get("category", categories[0] if categories else "content")
                if category not in RECOMMENDATION_CATEGORIES:
                    category = "content"

                rec = AIRecommendation(
                    company_id=company_id,
                    branch_id=branch_id,
                    category=RecommendationCategory(category),
                    title=item.get("title", "Untitled Recommendation")[:255],
                    description=item.get("description", ""),
                    confidence_score=float(item.get("confidence_score", 0.7)),
                    data_source=item.get("data_source", "ai_analysis"),
                    action_items=item.get("action_items", []),
                    status=RecommendationStatus.PENDING,
                )
                self.db.add(rec)
                recommendations.append(rec)
            except (KeyError, ValueError, TypeError) as exc:
                logger.warning("Skipping invalid recommendation item: %s", str(exc))
                continue

        await self.db.commit()
        for rec in recommendations:
            await self.db.refresh(rec)

        logger.info(
            "Generated %d AI recommendations for company=%d",
            len(recommendations),
            company_id,
        )
        return recommendations

    async def list_recommendations(
        self,
        company_id: int,
        branch_id: Optional[int] = None,
        category: Optional[str] = None,
        status: Optional[str] = None,
        page: int = 1,
        page_size: int = 20,
    ) -> Tuple[List[AIRecommendation], int]:
        """List AI recommendations with optional filtering.

        Args:
            company_id: The company ID for tenant isolation.
            branch_id: Optional branch ID filter.
            category: Optional category filter.
            status: Optional status filter.
            page: Page number (1-indexed).
            page_size: Items per page.

        Returns:
            Tuple of (list of recommendations, total count).
        """
        query = select(AIRecommendation).where(
            AIRecommendation.company_id == company_id
        )

        if branch_id is not None:
            query = query.where(
                (AIRecommendation.branch_id == branch_id)
                | (AIRecommendation.branch_id.is_(None))
            )
        if category:
            query = query.where(AIRecommendation.category == category)
        if status:
            query = query.where(AIRecommendation.status == status)

        # Count total
        count_query = select(func.count()).select_from(query.subquery())
        total_result = await self.db.execute(count_query)
        total = total_result.scalar() or 0

        # Paginated results, ordered by confidence score descending
        query = query.order_by(desc(AIRecommendation.confidence_score))
        query = query.offset((page - 1) * page_size).limit(page_size)
        result = await self.db.execute(query)
        recommendations = result.scalars().all()

        return list(recommendations), total

    async def apply_recommendation(
        self, recommendation_id: int, company_id: int
    ) -> AIRecommendation:
        """Mark a recommendation as applied.

        Args:
            recommendation_id: The recommendation ID.
            company_id: The company ID for tenant isolation.

        Returns:
            The updated AIRecommendation instance.

        Raises:
            NotFoundError: If the recommendation is not found.
        """
        result = await self.db.execute(
            select(AIRecommendation).where(
                AIRecommendation.id == recommendation_id,
                AIRecommendation.company_id == company_id,
            )
        )
        rec = result.scalar_one_or_none()
        if not rec:
            raise NotFoundError(f"Recommendation {recommendation_id} not found")

        rec.status = RecommendationStatus.APPLIED
        await self.db.commit()
        await self.db.refresh(rec)
        logger.info("Applied AI recommendation id=%d", recommendation_id)
        return rec

    async def dismiss_recommendation(
        self, recommendation_id: int, company_id: int
    ) -> AIRecommendation:
        """Mark a recommendation as dismissed.

        Args:
            recommendation_id: The recommendation ID.
            company_id: The company ID for tenant isolation.

        Returns:
            The updated AIRecommendation instance.

        Raises:
            NotFoundError: If the recommendation is not found.
        """
        result = await self.db.execute(
            select(AIRecommendation).where(
                AIRecommendation.id == recommendation_id,
                AIRecommendation.company_id == company_id,
            )
        )
        rec = result.scalar_one_or_none()
        if not rec:
            raise NotFoundError(f"Recommendation {recommendation_id} not found")

        rec.status = RecommendationStatus.DISMISSED
        await self.db.commit()
        await self.db.refresh(rec)
        logger.info("Dismissed AI recommendation id=%d", recommendation_id)
        return rec


# ---------------------------------------------------------------------------
# AI Usage Tracker
# ---------------------------------------------------------------------------

class AIUsageTracker:
    """
    Service for tracking AI API usage, costs, and enforcing usage limits.

    Logs every API call with tokens, costs, and latency.
    Provides aggregated analytics and enforces company-level usage limits.
    """

    def __init__(self, db: AsyncSession):
        """Initialize the usage tracker.

        Args:
            db: Async SQLAlchemy session.
        """
        self.db = db

    async def log_usage(
        self,
        company_id: int,
        user_id: Optional[int],
        model: str,
        endpoint: str,
        tokens_input: int,
        tokens_output: int,
        cost_estimate: float,
        latency_ms: int,
        status: str,
        branch_id: Optional[int] = None,
        supervised_mode: bool = True,
        request_metadata: Optional[Dict[str, Any]] = None,
    ) -> AIUsageLog:
        """Log a single AI API usage entry.

        Args:
            company_id: The company ID.
            user_id: Optional user ID.
            model: The model name used.
            endpoint: The API endpoint called.
            tokens_input: Number of input tokens.
            tokens_output: Number of output tokens.
            cost_estimate: Estimated cost in USD.
            latency_ms: Request latency in milliseconds.
            status: Request status (success/fallback/error).
            branch_id: Optional branch ID for branch-aware analytics.
            supervised_mode: Whether AI is running in supervised mode.
            request_metadata: Extra metadata (prompt_id, cache_hit, etc.).

        Returns:
            The created AIUsageLog instance.
        """
        log_entry = AIUsageLog(
            company_id=company_id,
            user_id=user_id,
            model=AIModelName(model) if model in [m.value for m in AIModelName] else AIModelName.GPT_4O_MINI,
            endpoint=endpoint,
            tokens_input=tokens_input,
            tokens_output=tokens_output,
            cost_estimate=cost_estimate,
            latency_ms=latency_ms,
            status=status,
            branch_id=branch_id,
            supervised_mode=supervised_mode,
            request_metadata=request_metadata or {},
        )
        self.db.add(log_entry)
        await self.db.commit()
        await self.db.refresh(log_entry)
        return log_entry

    async def get_usage_summary(
        self,
        company_id: Optional[int] = None,
        user_id: Optional[int] = None,
        model: Optional[str] = None,
        start_date: Optional[datetime] = None,
        end_date: Optional[datetime] = None,
    ) -> Dict[str, Any]:
        """Get aggregated AI usage summary.

        Args:
            company_id: Optional company ID filter.
            user_id: Optional user ID filter.
            model: Optional model name filter.
            start_date: Optional start date filter.
            end_date: Optional end date filter.

        Returns:
            Dictionary with aggregated usage statistics.
        """
        query = select(AIUsageLog)

        if company_id:
            query = query.where(AIUsageLog.company_id == company_id)
        if user_id:
            query = query.where(AIUsageLog.user_id == user_id)
        if model:
            query = query.where(AIUsageLog.model == model)
        if start_date:
            query = query.where(AIUsageLog.created_at >= start_date)
        if end_date:
            query = query.where(AIUsageLog.created_at <= end_date)

        result = await self.db.execute(query)
        logs = result.scalars().all()

        if not logs:
            return {
                "total_requests": 0,
                "total_tokens_input": 0,
                "total_tokens_output": 0,
                "total_tokens": 0,
                "total_cost_estimate": 0.0,
                "avg_latency_ms": 0.0,
                "avg_tokens_per_request": 0.0,
                "requests_by_model": {},
                "requests_by_status": {},
                "tokens_by_day": {},
                "cost_by_day": {},
            }

        total_requests = len(logs)
        total_tokens_input = sum(l.tokens_input for l in logs)
        total_tokens_output = sum(l.tokens_output for l in logs)
        total_tokens = total_tokens_input + total_tokens_output
        total_cost = sum(l.cost_estimate for l in logs)
        avg_latency = sum(l.latency_ms for l in logs) / total_requests

        requests_by_model: Dict[str, int] = {}
        requests_by_status: Dict[str, int] = {}
        tokens_by_day: Dict[str, int] = {}
        cost_by_day: Dict[str, float] = {}

        for log in logs:
            model_key = log.model.value if hasattr(log.model, "value") else str(log.model)
            requests_by_model[model_key] = requests_by_model.get(model_key, 0) + 1
            requests_by_status[log.status] = requests_by_status.get(log.status, 0) + 1

            day_key = log.created_at.strftime("%Y-%m-%d")
            tokens_by_day[day_key] = tokens_by_day.get(day_key, 0) + log.tokens_input + log.tokens_output
            cost_by_day[day_key] = cost_by_day.get(day_key, 0.0) + log.cost_estimate

        return {
            "total_requests": total_requests,
            "total_tokens_input": total_tokens_input,
            "total_tokens_output": total_tokens_output,
            "total_tokens": total_tokens,
            "total_cost_estimate": round(total_cost, 6),
            "avg_latency_ms": round(avg_latency, 2),
            "avg_tokens_per_request": round(total_tokens / total_requests, 2),
            "requests_by_model": requests_by_model,
            "requests_by_status": requests_by_status,
            "tokens_by_day": tokens_by_day,
            "cost_by_day": cost_by_day,
        }

    async def list_usage_logs(
        self,
        company_id: Optional[int] = None,
        user_id: Optional[int] = None,
        model: Optional[str] = None,
        page: int = 1,
        page_size: int = 20,
    ) -> Tuple[List[AIUsageLog], int]:
        """List AI usage logs with optional filtering.

        Args:
            company_id: Optional company ID filter.
            user_id: Optional user ID filter.
            model: Optional model name filter.
            page: Page number (1-indexed).
            page_size: Items per page.

        Returns:
            Tuple of (list of logs, total count).
        """
        query = select(AIUsageLog)

        if company_id:
            query = query.where(AIUsageLog.company_id == company_id)
        if user_id:
            query = query.where(AIUsageLog.user_id == user_id)
        if model:
            query = query.where(AIUsageLog.model == model)

        # Count total
        count_query = select(func.count()).select_from(query.subquery())
        total_result = await self.db.execute(count_query)
        total = total_result.scalar() or 0

        # Paginated results
        query = query.order_by(desc(AIUsageLog.created_at))
        query = query.offset((page - 1) * page_size).limit(page_size)
        result = await self.db.execute(query)
        logs = result.scalars().all()

        return list(logs), total

    async def check_usage_limit(self, company_id: int) -> Tuple[bool, Dict[str, Any]]:
        """Check if a company has exceeded its usage limits.

        Args:
            company_id: The company ID to check.

        Returns:
            Tuple of (within_limit, limit_info).
        """
        now = datetime.utcnow()
        month_start = now.replace(day=1, hour=0, minute=0, second=0, microsecond=0)

        summary = await self.get_usage_summary(
            company_id=company_id,
            start_date=month_start,
        )

        from app.ai.constants import DEFAULT_MONTHLY_TOKEN_LIMIT, USAGE_LIMIT_ALERT_THRESHOLD

        total_tokens = summary["total_tokens"]
        limit = DEFAULT_MONTHLY_TOKEN_LIMIT
        usage_ratio = total_tokens / limit if limit > 0 else 0
        within_limit = usage_ratio < 1.0
        alert_triggered = usage_ratio >= USAGE_LIMIT_ALERT_THRESHOLD

        limit_info = {
            "monthly_token_limit": limit,
            "tokens_used_this_month": total_tokens,
            "usage_ratio": round(usage_ratio, 4),
            "within_limit": within_limit,
            "alert_triggered": alert_triggered,
            "remaining_tokens": max(0, limit - total_tokens),
        }

        return within_limit, limit_info

    async def check_company_quota(
        self,
        company_id: int,
    ) -> Tuple[bool, Dict[str, Any]]:
        """Check per-company daily and monthly usage quotas.

        Queries the database for actual usage and compares against limits.

        Args:
            company_id: The company ID to check quota for.

        Returns:
            Tuple of (within_quota, quota_info).
        """
        from app.ai.constants import (
            DEFAULT_MONTHLY_TOKEN_LIMIT,
            DEFAULT_MONTHLY_COST_LIMIT_USD,
            USAGE_LIMIT_ALERT_THRESHOLD,
        )

        quota_info = {
            "company_id": company_id,
            "daily_requests": 0,
            "daily_tokens": 0,
            "monthly_tokens": 0,
            "monthly_cost_usd": 0.0,
            "monthly_token_limit": DEFAULT_MONTHLY_TOKEN_LIMIT,
            "monthly_cost_limit": DEFAULT_MONTHLY_COST_LIMIT_USD,
            "usage_ratio_tokens": 0.0,
            "usage_ratio_cost": 0.0,
            "within_limit": True,
            "alert_triggered": False,
            "reason": None,
        }

        try:
            now = datetime.utcnow()
            today_start = now.replace(hour=0, minute=0, second=0, microsecond=0)
            month_start = now.replace(day=1, hour=0, minute=0, second=0, microsecond=0)

            # Daily stats
            daily_count = select(func.count(AIUsageLog.id)).where(
                AIUsageLog.company_id == company_id,
                AIUsageLog.created_at >= today_start,
            )
            daily_tokens = select(func.coalesce(
                func.sum(AIUsageLog.tokens_input + AIUsageLog.tokens_output), 0
            )).where(
                AIUsageLog.company_id == company_id,
                AIUsageLog.created_at >= today_start,
            )
            daily_count_result = await self.db.execute(daily_count)
            daily_tokens_result = await self.db.execute(daily_tokens)
            quota_info["daily_requests"] = daily_count_result.scalar() or 0
            quota_info["daily_tokens"] = daily_tokens_result.scalar() or 0

            # Monthly stats
            monthly_tokens_query = select(func.coalesce(
                func.sum(AIUsageLog.tokens_input + AIUsageLog.tokens_output), 0
            )).where(
                AIUsageLog.company_id == company_id,
                AIUsageLog.created_at >= month_start,
            )
            monthly_cost_query = select(func.coalesce(
                func.sum(AIUsageLog.cost_estimate), 0.0
            )).where(
                AIUsageLog.company_id == company_id,
                AIUsageLog.created_at >= month_start,
            )
            monthly_tokens_result = await self.db.execute(monthly_tokens_query)
            monthly_cost_result = await self.db.execute(monthly_cost_query)
            quota_info["monthly_tokens"] = monthly_tokens_result.scalar() or 0
            quota_info["monthly_cost_usd"] = round(monthly_cost_result.scalar() or 0.0, 4)

            # Calculate ratios
            token_ratio = (
                quota_info["monthly_tokens"] / DEFAULT_MONTHLY_TOKEN_LIMIT
                if DEFAULT_MONTHLY_TOKEN_LIMIT > 0 else 0
            )
            cost_ratio = (
                quota_info["monthly_cost_usd"] / DEFAULT_MONTHLY_COST_LIMIT_USD
                if DEFAULT_MONTHLY_COST_LIMIT_USD > 0 else 0
            )
            quota_info["usage_ratio_tokens"] = round(token_ratio, 4)
            quota_info["usage_ratio_cost"] = round(cost_ratio, 4)
            quota_info["within_limit"] = token_ratio < 1.0 and cost_ratio < 1.0
            quota_info["alert_triggered"] = (
                token_ratio >= USAGE_LIMIT_ALERT_THRESHOLD
                or cost_ratio >= USAGE_LIMIT_ALERT_THRESHOLD
            )

            if not quota_info["within_limit"]:
                if token_ratio >= 1.0:
                    quota_info["reason"] = (
                        f"Aylik token limiti asildi "
                        f"({quota_info['monthly_tokens']:,}/{DEFAULT_MONTHLY_TOKEN_LIMIT:,})"
                    )
                elif cost_ratio >= 1.0:
                    quota_info["reason"] = (
                        f"Aylik maliyet limiti asildi "
                        f"(${quota_info['monthly_cost_usd']:.2f}/${DEFAULT_MONTHLY_COST_LIMIT_USD:.2f})"
                    )

            return quota_info["within_limit"], quota_info

        except Exception as exc:
            logger.warning("Quota check error: %s", str(exc))
            return True, quota_info


# ---------------------------------------------------------------------------
# AI Cache Service
# ---------------------------------------------------------------------------

class AICacheService:
    """
    Service for caching AI completion responses using Redis.

    Provides cache key generation from prompt hash, TTL-based expiration,
    and hit count tracking for cache analytics.
    """

    def __init__(self):
        """Initialize the cache service."""
        self.prefix = CACHE_KEY_PREFIX_COMPLETION

    def _generate_cache_key(self, model: str, prompt_hash: str) -> str:
        """Generate a cache key from model and prompt hash.

        Args:
            model: The model name.
            prompt_hash: The SHA-256 hash of the prompt.

        Returns:
            Cache key string.
        """
        return f"{self.prefix}:{model}:{prompt_hash}"

    def _hash_prompt(self, prompt: str) -> str:
        """Generate a SHA-256 hash of a prompt string.

        Args:
            prompt: The prompt string to hash.

        Returns:
            Hexadecimal hash string.
        """
        return hashlib.sha256(prompt.encode("utf-8")).hexdigest()

    async def get_cached_response(
        self, model: str, prompt: str
    ) -> Optional[Dict[str, Any]]:
        """Get a cached response from Redis if available.

        Args:
            model: The model name used.
            prompt: The prompt string.

        Returns:
            Cached response dict if found and not expired, None otherwise.
        """
        prompt_hash = self._hash_prompt(prompt)
        cache_key = self._generate_cache_key(model, prompt_hash)

        try:
            cache = await get_cache()
            cached = await cache.get(cache_key)
            if cached is not None:
                # Parse cached response
                if isinstance(cached, str):
                    try:
                        cached = json.loads(cached)
                    except json.JSONDecodeError:
                        return None

                if isinstance(cached, dict) and "response" in cached:
                    logger.debug("Cache hit for key=%s", cache_key)
                    return {
                        "content": cached["response"],
                        "model": cached.get("model", model),
                        "tokens": cached.get("tokens", 0),
                        "cached": True,
                    }
        except Exception as exc:
            logger.warning("Cache read error: %s", str(exc))

        return None

    async def cache_response(
        self,
        model: str,
        prompt: str,
        response: str,
        tokens: int,
        ttl: int = DEFAULT_CACHE_TTL,
    ) -> None:
        """Store a response in the cache.

        Args:
            model: The model name used.
            prompt: The prompt string.
            response: The AI response to cache.
            tokens: Number of tokens in the response.
            ttl: Time-to-live in seconds.
        """
        prompt_hash = self._hash_prompt(prompt)
        cache_key = self._generate_cache_key(model, prompt_hash)

        try:
            cache = await get_cache()
            cache_data = {
                "response": response,
                "model": model,
                "tokens": tokens,
                "cached_at": datetime.utcnow().isoformat(),
            }
            await cache.set(cache_key, cache_data, ttl=ttl)
            logger.debug("Cached response for key=%s ttl=%d", cache_key, ttl)
        except Exception as exc:
            logger.warning("Cache write error: %s", str(exc))

    async def invalidate_cache(self, model: str, prompt: str) -> None:
        """Invalidate a cached response.

        Args:
            model: The model name.
            prompt: The prompt string.
        """
        prompt_hash = self._hash_prompt(prompt)
        cache_key = self._generate_cache_key(model, prompt_hash)

        try:
            cache = await get_cache()
            await cache.delete(cache_key)
            logger.debug("Invalidated cache key=%s", cache_key)
        except Exception as exc:
            logger.warning("Cache delete error: %s", str(exc))

    async def get_cache_stats(self) -> Dict[str, Any]:
        """Get cache statistics from Redis.

        Returns:
            Dictionary with cache statistics.
        """
        try:
            cache = await get_cache()
            # Scan for all cache keys
            redis_client = cache._redis
            keys = []
            cursor = 0
            pattern = f"{self.prefix}:*"
            while True:
                cursor, batch = await redis_client.scan(cursor, match=pattern, count=100)
                keys.extend(batch)
                if cursor == 0:
                    break

            total_entries = len(keys)
            if total_entries == 0:
                return {
                    "total_entries": 0,
                    "active_entries": 0,
                    "expired_entries": 0,
                    "total_hits": 0,
                    "hit_rate": 0.0,
                    "avg_hit_count": 0.0,
                    "total_tokens_saved": 0,
                    "estimated_cost_savings": 0.0,
                }

            ttl_values = []
            total_tokens_saved = 0
            for key in keys:
                try:
                    data = await cache.get(key)
                    if isinstance(data, dict):
                        total_tokens_saved += data.get("tokens", 0)
                    ttl = await redis_client.ttl(key)
                    ttl_values.append(ttl)
                except Exception:
                    continue

            active_entries = sum(1 for t in ttl_values if t > 0)
            expired_entries = total_entries - active_entries

            return {
                "total_entries": total_entries,
                "active_entries": active_entries,
                "expired_entries": expired_entries,
                "total_hits": 0,  # Redis doesn't track hits per key by default
                "hit_rate": 0.0,
                "avg_hit_count": 0.0,
                "total_tokens_saved": total_tokens_saved,
                "estimated_cost_savings": round(
                    (total_tokens_saved / 1000.0) * 0.0006, 6
                ),  # Approximate cost
            }
        except Exception as exc:
            logger.warning("Cache stats error: %s", str(exc))
            return {
                "total_entries": 0,
                "active_entries": 0,
                "expired_entries": 0,
                "total_hits": 0,
                "hit_rate": 0.0,
                "avg_hit_count": 0.0,
                "total_tokens_saved": 0,
                "estimated_cost_savings": 0.0,
            }


# ---------------------------------------------------------------------------
# Conversation Service
# ---------------------------------------------------------------------------

class ConversationService:
    """
    Service for managing AI conversations and messages.

    Handles conversation creation, message sending with AI completion,
    and conversation lifecycle management.
    """

    def __init__(
        self,
        db: AsyncSession,
        openai_service: Optional[OpenAIService] = None,
    ):
        """Initialize the conversation service.

        Args:
            db: Async SQLAlchemy session.
            openai_service: Optional OpenAIService instance.
        """
        self.db = db
        self.openai = openai_service or OpenAIService()

    async def create_conversation(
        self,
        company_id: int,
        branch_id: Optional[int],
        user_id: int,
        title: str,
        model: str = DEFAULT_MODEL,
        prompt_id: Optional[int] = None,
    ) -> AIConversation:
        """Create a new conversation.

        Args:
            company_id: The company ID.
            branch_id: Optional branch ID.
            user_id: The user ID.
            title: Conversation title.
            model: The model name to use.
            prompt_id: Optional prompt template ID.

        Returns:
            The created AIConversation instance.
        """
        if model not in [m.value for m in AIModelName]:
            model = DEFAULT_MODEL

        conversation = AIConversation(
            company_id=company_id,
            branch_id=branch_id,
            user_id=user_id,
            session_id=str(uuid.uuid4()),
            title=title,
            model=AIModelName(model),
            total_tokens=0,
            status=ConversationStatus.ACTIVE,
            prompt_id=prompt_id,
        )
        self.db.add(conversation)
        await self.db.commit()
        await self.db.refresh(conversation)
        logger.info(
            "Created conversation id=%d session=%s user=%d",
            conversation.id,
            conversation.session_id,
            user_id,
        )
        return conversation

    async def get_conversation(
        self, conversation_id: int, company_id: int, user_id: Optional[int] = None
    ) -> AIConversation:
        """Get a conversation by ID with tenant check.

        Args:
            conversation_id: The conversation ID.
            company_id: The company ID for tenant isolation.
            user_id: Optional user ID for additional filtering.

        Returns:
            The AIConversation instance.

        Raises:
            NotFoundError: If the conversation is not found.
        """
        query = select(AIConversation).where(
            AIConversation.id == conversation_id,
            AIConversation.company_id == company_id,
        )
        if user_id:
            query = query.where(AIConversation.user_id == user_id)

        result = await self.db.execute(query)
        conversation = result.scalar_one_or_none()
        if not conversation:
            raise NotFoundError(f"Conversation {conversation_id} not found")
        return conversation

    async def list_conversations(
        self,
        company_id: int,
        branch_id: Optional[int] = None,
        user_id: Optional[int] = None,
        status: str = "active",
        page: int = 1,
        page_size: int = 20,
    ) -> Tuple[List[AIConversation], int]:
        """List conversations with optional filtering.

        Args:
            company_id: The company ID for tenant isolation.
            branch_id: Optional branch ID filter.
            user_id: Optional user ID filter.
            status: Conversation status filter.
            page: Page number (1-indexed).
            page_size: Items per page.

        Returns:
            Tuple of (list of conversations, total count).
        """
        query = select(AIConversation).where(
            AIConversation.company_id == company_id,
        )

        if branch_id is not None:
            query = query.where(
                (AIConversation.branch_id == branch_id)
                | (AIConversation.branch_id.is_(None))
            )
        if user_id:
            query = query.where(AIConversation.user_id == user_id)
        if status:
            query = query.where(AIConversation.status == status)

        # Count total
        count_query = select(func.count()).select_from(query.subquery())
        total_result = await self.db.execute(count_query)
        total = total_result.scalar() or 0

        # Paginated results
        query = query.order_by(desc(AIConversation.created_at))
        query = query.offset((page - 1) * page_size).limit(page_size)
        result = await self.db.execute(query)
        conversations = result.scalars().all()

        return list(conversations), total

    async def send_message(
        self,
        conversation_id: int,
        company_id: int,
        user_id: int,
        content: str,
    ) -> Tuple[AIMessage, AIMessage]:
        """Send a user message and get an AI response.

        Args:
            conversation_id: The conversation ID.
            company_id: The company ID for tenant isolation.
            user_id: The user ID.
            content: The user message content.

        Returns:
            Tuple of (user_message, assistant_message).

        Raises:
            NotFoundError: If the conversation is not found.
            ValidationError: If the conversation is not active.
        """
        conversation = await self.get_conversation(conversation_id, company_id, user_id)

        if conversation.status != ConversationStatus.ACTIVE:
            raise ValidationError("Conversation is not active")

        # Create user message
        user_message = AIMessage(
            conversation_id=conversation_id,
            role=MessageRole.USER,
            content=content,
            tokens=self.openai._estimate_tokens(content),
        )
        self.db.add(user_message)
        await self.db.flush()

        # Build message history for the API call
        messages = []

        # Add system prompt if conversation has an associated prompt template
        if conversation.prompt_id:
            from app.ai.models import AIPrompt
            prompt_result = await self.db.execute(
                select(AIPrompt).where(AIPrompt.id == conversation.prompt_id)
            )
            prompt = prompt_result.scalar_one_or_none()
            if prompt:
                messages.append({"role": "system", "content": prompt.system_prompt})
        else:
            messages.append({"role": "system", "content": DEFAULT_SYSTEM_PROMPT})

        # Add conversation history (last 10 messages)
        history_result = await self.db.execute(
            select(AIMessage)
            .where(AIMessage.conversation_id == conversation_id)
            .order_by(AIMessage.created_at)
            .limit(10)
        )
        history = history_result.scalars().all()

        for msg in history:
            role = msg.role.value if hasattr(msg.role, "value") else str(msg.role)
            messages.append({"role": role, "content": msg.content})

        # Add current user message if not already in history
        if not any(m.get("content") == content for m in messages if m.get("role") == "user"):
            messages.append({"role": "user", "content": content})

        # Call OpenAI API with full orchestration
        result = await self.openai.create_chat_completion(
            messages=messages,
            model=conversation.model.value,
            company_id=company_id,
            user_id=user_id,
            branch_id=conversation.branch_id,
            prompt_id=conversation.prompt_id,
            db=self.db,
        )

        # Handle fallback responses gracefully in conversation context
        if result.get("fallback", False):
            fallback_content = result["content"]
            error_code = result.get("error", "UNKNOWN_ERROR")
            logger.warning(
                "AI fallback in conversation id=%d error=%s",
                conversation_id,
                error_code,
            )

        # Create assistant message
        assistant_message = AIMessage(
            conversation_id=conversation_id,
            role=MessageRole.ASSISTANT,
            content=result["content"],
            tokens=result["tokens_output"],
            model=conversation.model,
            finish_reason=result.get("finish_reason"),
        )
        self.db.add(assistant_message)

        # Update conversation totals
        conversation.total_tokens += result["total_tokens"]
        conversation.updated_at = datetime.utcnow()

        await self.db.commit()
        await self.db.refresh(user_message)
        await self.db.refresh(assistant_message)

        logger.info(
            "Message sent in conversation id=%d tokens=%d fallback=%s",
            conversation_id,
            result["total_tokens"],
            result.get("fallback", False),
        )
        return user_message, assistant_message

    async def delete_conversation(
        self, conversation_id: int, company_id: int, user_id: Optional[int] = None
    ) -> None:
        """Soft delete a conversation.

        Args:
            conversation_id: The conversation ID.
            company_id: The company ID for tenant isolation.
            user_id: Optional user ID filter.

        Raises:
            NotFoundError: If the conversation is not found.
        """
        conversation = await self.get_conversation(conversation_id, company_id, user_id)
        conversation.status = ConversationStatus.DELETED
        conversation.updated_at = datetime.utcnow()
        await self.db.commit()
        logger.info("Deleted conversation id=%d", conversation_id)
