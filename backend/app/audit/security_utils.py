"""Security utility functions for the audit module.

Provides:
- JWT refresh token rotation
- Webhook HMAC signature verification
- Upload file validation (type, size, content)
- Secret scanning in text (API key leak detection)
- IP reputation checking
"""

import hashlib
import hmac
import ipaddress
import json
import mimetypes
import os
import re
import secrets
from datetime import datetime, timedelta, timezone
from typing import Any, Dict, List, Optional, Tuple
from urllib.parse import urlparse

from app.audit.constants import (
    ALLOWED_UPLOAD_EXTENSIONS,
    ALLOWED_UPLOAD_MIME_TYPES,
    MAX_UPLOAD_SIZE_BYTES,
    SECRET_PATTERNS,
)
from app.config import settings


# ============================================================================
# JWT Refresh Token Rotation
# ============================================================================


class TokenRotationManager:
    """Manages refresh token rotation to prevent token replay attacks.

    Each refresh token can only be used once. When a refresh token is used,
    a new pair of access + refresh tokens is issued and the old refresh token
    is revoked.
    """

    @staticmethod
    def generate_token_family() -> str:
        """Generate a unique token family identifier.

        A token family groups together all refresh tokens issued in a
        chain of refresh operations.

        Returns:
            A cryptographically secure random token family ID.
        """
        return secrets.token_urlsafe(32)

    @staticmethod
    def get_redis_rotation_key(token_family: str) -> str:
        """Get the Redis key for tracking token rotation state.

        Args:
            token_family: The token family identifier.

        Returns:
            Redis key string.
        """
        return f"token_rotation:{token_family}"

    @staticmethod
    async def is_token_valid(token_family: str, token_jti: str) -> bool:
        """Check if a refresh token is still valid (not rotated or revoked).

        Args:
            token_family: The token family identifier.
            token_jti: The JWT ID (jti claim) of the refresh token.

        Returns:
            True if the token is the current active token in its family.
        """
        from app.redis_client import get_redis_client

        try:
            redis = await get_redis_client()
            key = TokenRotationManager.get_redis_rotation_key(token_family)
            current_jti = await redis.get(key)

            if current_jti is None:
                # New token family - first use is valid
                await redis.set(key, token_jti, ex=settings.REFRESH_TOKEN_EXPIRE_DAYS * 86400)
                return True

            return current_jti == token_jti
        except Exception:
            # If Redis is unavailable, deny rotation (fail secure)
            return False

    @staticmethod
    async def rotate_token(token_family: str, old_jti: str, new_jti: str) -> bool:
        """Atomically rotate a refresh token.

        Replaces the current active JTI with a new one in the token family.

        Args:
            token_family: The token family identifier.
            old_jti: The JTI of the token being used.
            new_jti: The JTI of the new token to issue.

        Returns:
            True if rotation succeeded, False if token was already used.
        """
        from app.redis_client import get_redis_client

        try:
            redis = await get_redis_client()
            key = TokenRotationManager.get_redis_rotation_key(token_family)

            # Use a Lua script for atomic compare-and-swap
            lua_script = """
                local current = redis.call('get', KEYS[1])
                if current == ARGV[1] then
                    redis.call('set', KEYS[1], ARGV[2], 'EX', ARGV[3])
                    return 1
                end
                return 0
            """

            ttl = settings.REFRESH_TOKEN_EXPIRE_DAYS * 86400
            result = await redis.eval(
                lua_script, 1, key, old_jti, new_jti, str(ttl)
            )

            if result == 0:
                # Token reuse detected! The old_jti doesn't match current
                # Mark the entire family as compromised
                await TokenRotationManager.revoke_family(token_family)
                return False

            return True
        except Exception:
            return False

    @staticmethod
    async def revoke_family(token_family: str) -> None:
        """Revoke an entire token family (compromised detection).

        Args:
            token_family: The token family to revoke.
        """
        from app.redis_client import get_redis_client

        try:
            redis = await get_redis_client()
            key = TokenRotationManager.get_redis_rotation_key(token_family)
            await redis.delete(key)
            # Also add to revoked families set
            await redis.sadd("revoked_token_families", token_family)
        except Exception:
            pass

    @staticmethod
    def decode_token_family(token: str) -> Optional[str]:
        """Extract token family from a refresh token payload.

        Args:
            token: The JWT refresh token string.

        Returns:
            The token family ID, or None if not found.
        """
        import jwt

        try:
            # Decode without verification to extract family
            payload = jwt.decode(
                token,
                settings.JWT_SECRET_KEY,
                algorithms=[settings.JWT_ALGORITHM],
                options={"verify_exp": False},
            )
            return payload.get("token_family")
        except Exception:
            return None

    @staticmethod
    def decode_token_jti(token: str) -> Optional[str]:
        """Extract JTI from a refresh token payload.

        Args:
            token: The JWT refresh token string.

        Returns:
            The JTI (JWT ID), or None if not found.
        """
        import jwt

        try:
            payload = jwt.decode(
                token,
                settings.JWT_SECRET_KEY,
                algorithms=[settings.JWT_ALGORITHM],
                options={"verify_exp": False},
            )
            return payload.get("jti")
        except Exception:
            return None


# ============================================================================
# Webhook Signature Verification
# ============================================================================


class WebhookSignatureVerifier:
    """Verifies webhook request signatures using HMAC.

    Supports multiple signature schemes:
    - stripe: t=timestamp,v1=signature (Stripe-style)
    - github: sha256=signature (GitHub-style)
    - generic: hmac-sha256 hex digest
    """

    @staticmethod
    def verify_stripe_signature(
        payload: bytes, signature: str, secret: str, tolerance: int = 300
    ) -> bool:
        """Verify a Stripe-style webhook signature.

        Format: t=timestamp,v1=signature

        Args:
            payload: Raw request body bytes.
            signature: The Stripe-Signature header value.
            secret: The webhook signing secret.
            tolerance: Maximum age in seconds (default 5 minutes).

        Returns:
            True if the signature is valid and not expired.
        """
        try:
            timestamp_str, sig = None, []
            for part in signature.split(","):
                kv = part.strip().split("=")
                if len(kv) == 2:
                    if kv[0] == "t":
                        timestamp_str = kv[1]
                    elif kv[0] == "v1":
                        sig.append(kv[1])

            if not timestamp_str or not sig:
                return False

            timestamp = int(timestamp_str)
            now = int(datetime.now(timezone.utc).timestamp())

            if abs(now - timestamp) > tolerance:
                return False

            signed_payload = f"{timestamp_str}.".encode() + payload
            expected_sig = hmac.new(
                secret.encode(), signed_payload, hashlib.sha256
            ).hexdigest()

            return any(
                hmac.compare_digest(expected_sig, s) for s in sig
            )
        except Exception:
            return False

    @staticmethod
    def verify_github_signature(
        payload: bytes, signature: str, secret: str
    ) -> bool:
        """Verify a GitHub-style webhook signature.

        Format: sha256=hex_hmac_signature

        Args:
            payload: Raw request body bytes.
            signature: The X-Hub-Signature-256 header value.
            secret: The webhook secret.

        Returns:
            True if the signature is valid.
        """
        try:
            if not signature.startswith("sha256="):
                return False

            provided_sig = signature[7:]  # Remove "sha256=" prefix
            expected_sig = hmac.new(
                secret.encode(), payload, hashlib.sha256
            ).hexdigest()

            return hmac.compare_digest(provided_sig, expected_sig)
        except Exception:
            return False

    @staticmethod
    def verify_generic_hmac(
        payload: bytes, signature: str, secret: str, algorithm: str = "sha256"
    ) -> bool:
        """Verify a generic HMAC hex signature.

        Args:
            payload: Raw request body bytes.
            signature: The hex-encoded HMAC signature.
            secret: The shared secret.
            algorithm: Hash algorithm (sha256, sha512, etc.).

        Returns:
            True if the signature matches.
        """
        try:
            hash_func = getattr(hashlib, algorithm, hashlib.sha256)
            expected_sig = hmac.new(
                secret.encode(), payload, hash_func
            ).hexdigest()
            return hmac.compare_digest(signature, expected_sig)
        except Exception:
            return False

    @staticmethod
    def verify_signature(
        payload: bytes,
        signature_header: str,
        secret: str,
        scheme: str = "generic",
        tolerance: int = 300,
    ) -> bool:
        """Verify a webhook signature with auto scheme detection.

        Args:
            payload: Raw request body bytes.
            signature_header: The signature header value.
            secret: The shared secret.
            scheme: Signature scheme (stripe, github, generic).
            tolerance: Timestamp tolerance for Stripe-style signatures.

        Returns:
            True if the signature is valid.
        """
        if scheme == "stripe":
            return WebhookSignatureVerifier.verify_stripe_signature(
                payload, signature_header, secret, tolerance
            )
        elif scheme == "github":
            return WebhookSignatureVerifier.verify_github_signature(
                payload, signature_header, secret
            )
        else:
            return WebhookSignatureVerifier.verify_generic_hmac(
                payload, signature_header, secret
            )

    @staticmethod
    def generate_signature(
        payload: bytes, secret: str, algorithm: str = "sha256"
    ) -> str:
        """Generate an HMAC signature for webhook testing.

        Args:
            payload: The request body bytes.
            secret: The shared secret.
            algorithm: Hash algorithm.

        Returns:
            Hex-encoded HMAC signature.
        """
        hash_func = getattr(hashlib, algorithm, hashlib.sha256)
        return hmac.new(secret.encode(), payload, hash_func).hexdigest()


# ============================================================================
# Upload File Validation
# ============================================================================


class UploadValidator:
    """Validates uploaded files for security.

    Checks file extension, MIME type, size, and performs basic content
    validation to prevent malicious uploads.
    """

    @staticmethod
    def validate_extension(filename: str) -> Tuple[bool, Optional[str]]:
        """Check if a file extension is allowed.

        Args:
            filename: The uploaded filename.

        Returns:
            Tuple of (is_valid, error_message).
        """
        ext = os.path.splitext(filename.lower())[1]
        if ext not in ALLOWED_UPLOAD_EXTENSIONS:
            allowed = ", ".join(sorted(ALLOWED_UPLOAD_EXTENSIONS))
            return False, f"Extension '{ext}' not allowed. Allowed: {allowed}"
        return True, None

    @staticmethod
    def validate_mime_type(
        declared_mime: str, file_content: Optional[bytes] = None
    ) -> Tuple[bool, Optional[str]]:
        """Validate MIME type of uploaded content.

        Args:
            declared_mime: The MIME type declared by the client.
            file_content: Optional raw file content for verification.

        Returns:
            Tuple of (is_valid, error_message).
        """
        normalized = declared_mime.lower().strip()

        if normalized not in ALLOWED_UPLOAD_MIME_TYPES:
            allowed = ", ".join(sorted(ALLOWED_UPLOAD_MIME_TYPES))
            return False, f"MIME type '{declared_mime}' not allowed. Allowed: {allowed}"

        # If we have content, verify the declared MIME matches actual content
        if file_content:
            detected = UploadValidator._detect_mime_from_content(file_content)
            if detected and detected != normalized:
                # Some MIME types are aliases
                aliases = {
                    "application/octet-stream": ["text/plain", "application/json"],
                    "text/plain": ["application/json"],
                }
                if normalized not in aliases.get(detected, []):
                    return False, (
                        f"MIME type mismatch: declared '{declared_mime}' "
                        f"but detected '{detected}'"
                    )

        return True, None

    @staticmethod
    def validate_size(size_bytes: int) -> Tuple[bool, Optional[str]]:
        """Check if file size is within allowed limits.

        Args:
            size_bytes: The file size in bytes.

        Returns:
            Tuple of (is_valid, error_message).
        """
        if size_bytes <= 0:
            return False, "File is empty"

        if size_bytes > MAX_UPLOAD_SIZE_BYTES:
            max_mb = MAX_UPLOAD_SIZE_BYTES / (1024 * 1024)
            actual_mb = size_bytes / (1024 * 1024)
            return False, (
                f"File size {actual_mb:.1f}MB exceeds maximum of {max_mb:.0f}MB"
            )

        return True, None

    @staticmethod
    def validate_content(
        file_content: bytes, expected_mime: str
    ) -> Tuple[bool, Optional[str]]:
        """Perform content-level validation for specific file types.

        Args:
            file_content: The raw file content.
            expected_mime: The expected MIME type.

        Returns:
            Tuple of (is_valid, error_message).
        """
        # Check for embedded executable signatures
        executable_signatures = [
            b"MZ",           # Windows executable
            b"\x7fELF",      # Linux executable
            b"#!",           # Shebang script
            b"<?php",        # PHP
            b"<script",      # HTML with script tag
        ]

        content_start = file_content[:1024]
        for sig in executable_signatures:
            if sig in content_start:
                return False, "File contains executable content"

        # Validate JSON files
        if expected_mime == "application/json":
            try:
                json.loads(file_content.decode("utf-8"))
            except (json.JSONDecodeError, UnicodeDecodeError) as e:
                return False, f"Invalid JSON content: {str(e)}"

        # Validate CSV files have headers
        if expected_mime == "text/csv":
            try:
                lines = file_content.decode("utf-8").splitlines()
                if len(lines) < 1:
                    return False, "CSV file must have at least a header row"
            except UnicodeDecodeError:
                return False, "Invalid CSV encoding (must be UTF-8)"

        return True, None

    @staticmethod
    def validate_upload(
        filename: str,
        size_bytes: int,
        declared_mime: str,
        file_content: bytes,
    ) -> Tuple[bool, List[str]]:
        """Perform full upload validation.

        Args:
            filename: Original filename.
            size_bytes: File size in bytes.
            declared_mime: Declared MIME type.
            file_content: Raw file content.

        Returns:
            Tuple of (all_valid, list_of_error_messages).
        """
        errors: List[str] = []

        checks = [
            UploadValidator.validate_extension(filename),
            UploadValidator.validate_size(size_bytes),
            UploadValidator.validate_mime_type(declared_mime, file_content),
            UploadValidator.validate_content(file_content, declared_mime),
        ]

        for is_valid, error in checks:
            if not is_valid and error:
                errors.append(error)

        return len(errors) == 0, errors

    @staticmethod
    def _detect_mime_from_content(content: bytes) -> Optional[str]:
        """Detect MIME type from file content magic numbers.

        Args:
            content: Raw file content.

        Returns:
            Detected MIME type or None.
        """
        if content.startswith(b"\x89PNG\r\n\x1a\n"):
            return "image/png"
        elif content[:3] == b"\xff\xd8\xff":
            return "image/jpeg"
        elif content.startswith(b"PK"):
            # Could be XLSX or other ZIP-based
            if b"xl/" in content[:1024]:
                return "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
            return "application/zip"
        elif content.startswith(b"%PDF"):
            return "application/pdf"
        elif content.startswith(b"{\\rtf"):
            return "application/rtf"
        # Try text-based detection
        try:
            text = content[:1024].decode("utf-8").strip()
            if text.startswith("{") or text.startswith("["):
                return "application/json"
            if "," in text.split("\n", 1)[0]:
                return "text/csv"
            return "text/plain"
        except UnicodeDecodeError:
            return "application/octet-stream"


# ============================================================================
# Secret Scanning
# ============================================================================


class SecretScanner:
    """Scans text for accidentally leaked secrets and API keys.

    Uses regex patterns to detect common secret formats in request/response
    bodies, logs, and user-generated content.
    """

    @staticmethod
    def scan_text(text: str) -> List[Dict[str, Any]]:
        """Scan text for potential secret leaks.

        Args:
            text: The text to scan.

        Returns:
            List of detected secrets with type, position, and masked value.
        """
        findings: List[Dict[str, Any]] = []

        for secret_type, pattern in SECRET_PATTERNS.items():
            for match in re.finditer(pattern, text):
                finding = {
                    "type": secret_type,
                    "start": match.start(),
                    "end": match.end(),
                    "matched": SecretScanner._mask_secret(match.group()),
                }
                findings.append(finding)

        return findings

    @staticmethod
    def scan_dict(data: Dict[str, Any], path: str = "") -> List[Dict[str, Any]]:
        """Recursively scan a dictionary for leaked secrets.

        Args:
            data: The dictionary to scan.
            path: Current key path for nested reporting.

        Returns:
            List of findings with full key paths.
        """
        findings: List[Dict[str, Any]] = []

        for key, value in data.items():
            current_path = f"{path}.{key}" if path else key

            # Check the key name itself
            if SecretScanner._is_sensitive_key(key):
                if isinstance(value, str) and len(value) > 8:
                    findings.append({
                        "type": "sensitive_key",
                        "path": current_path,
                        "key": key,
                        "matched": SecretScanner._mask_secret(value),
                    })

            if isinstance(value, str):
                text_findings = SecretScanner.scan_text(value)
                for f in text_findings:
                    f["path"] = current_path
                findings.extend(text_findings)
            elif isinstance(value, dict):
                findings.extend(SecretScanner.scan_dict(value, current_path))
            elif isinstance(value, list):
                for i, item in enumerate(value):
                    if isinstance(item, str):
                        text_findings = SecretScanner.scan_text(item)
                        for f in text_findings:
                            f["path"] = f"{current_path}[{i}]"
                        findings.extend(text_findings)
                    elif isinstance(item, (dict, list)):
                        item_path = f"{current_path}[{i}]"
                        if isinstance(item, dict):
                            findings.extend(SecretScanner.scan_dict(item, item_path))

        return findings

    @staticmethod
    def has_secrets(text: str) -> bool:
        """Quick check if text contains any secrets.

        Args:
            text: The text to check.

        Returns:
            True if any secrets were detected.
        """
        return len(SecretScanner.scan_text(text)) > 0

    @staticmethod
    def _is_sensitive_key(key: str) -> bool:
        """Check if a key name suggests it contains sensitive data.

        Args:
            key: The dictionary key name.

        Returns:
            True if the key looks sensitive.
        """
        key_lower = key.lower()
        sensitive_patterns = [
            "password", "secret", "token", "api_key", "apikey",
            "private_key", "access_key", "auth",
        ]
        return any(pattern in key_lower for pattern in sensitive_patterns)

    @staticmethod
    def _mask_secret(value: str, visible_chars: int = 4) -> str:
        """Mask a secret value, showing only first/last few characters.

        Args:
            value: The secret value.
            visible_chars: Number of characters to show at each end.

        Returns:
            Masked string like "AKI***WXYZ".
        """
        if len(value) <= visible_chars * 2 + 3:
            return "***"
        return f"{value[:visible_chars]}***{value[-visible_chars:]}"


# ============================================================================
# IP Reputation
# ============================================================================


class IPReputationChecker:
    """Check IP address reputation for security scoring.

    Provides basic checks for private/reserved ranges and maintains
    a local blocklist in Redis.
    """

    # Known bad IP ranges (example: Tor exit nodes, known botnets)
    # In production, these would be loaded from a threat intelligence feed
    SUSPICIOUS_RANGES: List[str] = []

    @staticmethod
    def is_private_ip(ip_str: str) -> bool:
        """Check if an IP is in a private/reserved range.

        Args:
            ip_str: The IP address string.

        Returns:
            True if the IP is private, loopback, or reserved.
        """
        try:
            ip = ipaddress.ip_address(ip_str)
            return ip.is_private or ip.is_loopback or ip.is_reserved or ip.is_multicast
        except ValueError:
            return False

    @staticmethod
    def is_bogon(ip_str: str) -> bool:
        """Check if an IP is a bogon (should not appear on public internet).

        Args:
            ip_str: The IP address string.

        Returns:
            True if the IP is a bogon.
        """
        try:
            ip = ipaddress.ip_address(ip_str)
            return (
                ip.is_private
                or ip.is_loopback
                or ip.is_reserved
                or ip.is_multicast
                or ip.is_link_local
                or ip.is_unspecified
            )
        except ValueError:
            return True

    @staticmethod
    async def is_blocked(ip_str: str) -> bool:
        """Check if an IP is in the Redis blocklist.

        Args:
            ip_str: The IP address string.

        Returns:
            True if the IP is blocked.
        """
        from app.redis_client import get_redis_client

        try:
            redis = await get_redis_client()
            blocked = await redis.sismember("ip_blocklist", ip_str)
            return bool(blocked)
        except Exception:
            return False

    @staticmethod
    async def block_ip(ip_str: str, duration_seconds: int = 3600, reason: str = "") -> None:
        """Add an IP to the temporary blocklist.

        Args:
            ip_str: The IP address to block.
            duration_seconds: How long to block for.
            reason: Optional reason for blocking.
        """
        from app.redis_client import get_redis_client

        try:
            redis = await get_redis_client()
            key = f"ip_block:{ip_str}"
            await redis.set(key, reason or "blocked", ex=duration_seconds)
            await redis.sadd("ip_blocklist", ip_str)
        except Exception:
            pass

    @staticmethod
    async def unblock_ip(ip_str: str) -> None:
        """Remove an IP from the blocklist.

        Args:
            ip_str: The IP address to unblock.
        """
        from app.redis_client import get_redis_client

        try:
            redis = await get_redis_client()
            key = f"ip_block:{ip_str}"
            await redis.delete(key)
            await redis.srem("ip_blocklist", ip_str)
        except Exception:
            pass

    @staticmethod
    def get_reputation_score(ip_str: str) -> int:
        """Calculate a reputation score for an IP (0-100, higher = riskier).

        Args:
            ip_str: The IP address string.

        Returns:
            Reputation score from 0 (safe) to 100 (high risk).
        """
        score = 0

        if IPReputationChecker.is_bogon(ip_str):
            score += 50

        if IPReputationChecker.is_private_ip(ip_str):
            score += 30

        # TODO: Integrate with external threat intelligence
        # score += await _check_threat_intel(ip_str)

        return min(score, 100)


# ============================================================================
# API Key Generation & Hashing
# ============================================================================


def generate_api_key() -> str:
    """Generate a cryptographically secure API key.

    Format: amp_<base64url_random> (amp = AI Marketing Platform)

    Returns:
        A new API key string.
    """
    random_part = secrets.token_urlsafe(32)
    return f"amp_{random_part}"


def hash_api_key(plain_key: str) -> str:
    """Hash an API key for secure storage.

    Uses SHA-256 hash with a pepper from settings.

    Args:
        plain_key: The plain API key.

    Returns:
        Hex-encoded hash.
    """
    pepper = settings.SECRET_KEY.encode()
    return hashlib.sha256(plain_key.encode() + pepper).hexdigest()


def verify_api_key(plain_key: str, key_hash: str) -> bool:
    """Verify an API key against its stored hash.

    Args:
        plain_key: The plain API key to verify.
        key_hash: The stored hash.

    Returns:
        True if the key matches.
    """
    expected = hash_api_key(plain_key)
    return hmac.compare_digest(expected, key_hash)


def generate_correlation_id() -> str:
    """Generate a unique correlation ID for request tracing.

    Returns:
        A correlation ID string.
    """
    return secrets.token_hex(16)
