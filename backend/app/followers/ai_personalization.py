"""AI Personalized Messaging Service

LLM-powered message personalization with moderation, confidence scoring,
and approval preview. Uses existing OpenAIService from app.ai module.

Rules:
- No aggressive marketing language
- No spam patterns
- Short and natural messages
- Low confidence → manual review
"""

import logging
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)


# Safe prompt templates for each message type
SAFE_PROMPTS = {
    "welcome_new_follower": """You are a helpful, warm assistant for a Turkish business.
Write a short, natural welcome message (max 200 chars) to a new follower on {platform}.
Business context: {branch_context}
Follower info: @{username}
Language: Turkish
Tone: Warm, professional, not salesy
Do NOT use: all caps, excessive punctuation, emojis, hashtags, links, promotional language.
Output only the message text.""",

    "campaign_suggestion": """You are a helpful assistant for a Turkish business.
Write a short, natural message (max 250 chars) suggesting a relevant campaign to a follower.
Business context: {branch_context}
Follower info: @{username}, interests: {interests}
Language: Turkish
Tone: Helpful, conversational, not pushy
Do NOT use: aggressive sales language, all caps, excessive punctuation, spam patterns.
Output only the message text.""",

    "reengagement_for_low": """You are a warm, friendly assistant for a Turkish business.
Write a short, natural re-engagement message (max 250 chars) to an inactive follower.
Business context: {branch_context}
Follower info: @{username}, last engagement: {days} days ago
Language: Turkish
Tone: Warm, inviting, not desperate
Do NOT use: guilt-tripping, aggressive language, all caps, excessive punctuation.
Output only the message text.""",

    "win_back_unfollow": """You are a professional assistant for a Turkish business.
Write a short, natural win-back message (max 250 chars) to someone who stopped following.
Business context: {branch_context}
Follower info: @{username}
Language: Turkish
Tone: Respectful, inviting, not pushy
Do NOT use: begging, guilt, aggressive offers, all caps.
Output only the message text.""",

    "dm_follow_up": """You are a helpful assistant for a Turkish business.
Write a short, natural follow-up message (max 200 chars) continuing a previous conversation.
Business context: {branch_context}
Follower info: @{username}
Previous context: {conversation_context}
Language: Turkish
Tone: Helpful, conversational
Do NOT use: sales pitch, all caps, excessive punctuation.
Output only the message text.""",

    "local_branch_campaign": """You are a helpful assistant for a Turkish business.
Write a short, natural message (max 250 chars) about a local branch campaign.
Branch: {branch_name}, Location: {branch_location}
Campaign: {campaign_name}
Language: Turkish
Tone: Helpful, local, inviting
Do NOT use: aggressive marketing, all caps, excessive punctuation.
Output only the message text.""",

    "engagement_reward": """You are a warm assistant for a Turkish business.
Write a short, natural thank-you message (max 200 chars) for an engaged follower.
Business context: {branch_context}
Follower info: @{username}
Language: Turkish
Tone: Warm, appreciative
Do NOT use: promotional language, all caps, excessive punctuation.
Output only the message text.""",
}

# Spam/unsafe pattern checks
UNSAFE_PATTERNS = [
    "WIN", "FREE", "CLICK HERE", "ACT NOW", "LIMITED TIME",
    "$$$$", "%%%%", "!!!!!!", "???", "BUY NOW",
    "URGENT", "CONGRATULATIONS YOU WON", "CLAIM YOUR PRIZE",
    "SEND MONEY", "WIRE TRANSFER", "BANK ACCOUNT",
]

AGGRESSIVE_MARKETING = [
    "mutlaka al", "acele et", "son firsat", "kacirma",
    "hemen ara", "sadece bugun", "stoklar tukeniyor",
    "bu firsat kacmaz", "acil", "hemen satin al",
]


class MessageModerator:
    """Moderates AI-generated messages for policy compliance and safety."""

    @staticmethod
    def moderate(message: str, platform: str) -> Dict[str, Any]:
        """Moderate a message for safety and policy compliance.

        Returns:
            Dict with moderation result including:
            - passed: bool
            - score: float (0-1, higher = more safe)
            - flags: list of flagged issues
            - category: compliant, needs_review, violation
        """
        flags = []
        score = 1.0

        # Check unsafe patterns
        msg_upper = message.upper()
        for pattern in UNSAFE_PATTERNS:
            if pattern in msg_upper:
                flags.append(f"unsafe_pattern:{pattern}")
                score -= 0.2

        # Check aggressive marketing (Turkish)
        msg_lower = message.lower()
        for phrase in AGGRESSIVE_MARKETING:
            if phrase in msg_lower:
                flags.append(f"aggressive_marketing:{phrase}")
                score -= 0.15

        # Check excessive caps
        letters = [c for c in message if c.isalpha()]
        if letters:
            caps_ratio = sum(1 for c in letters if c.isupper()) / len(letters)
            if caps_ratio > 0.4:
                flags.append(f"excessive_caps:{caps_ratio:.0%}")
                score -= 0.15

        # Check excessive punctuation
        exclamation_count = message.count("!")
        if exclamation_count > 2:
            flags.append(f"excessive_exclamation:{exclamation_count}")
            score -= 0.1

        # Check message length
        platform_limits = {"instagram": 1000, "facebook": 2000, "tiktok": 500, "whatsapp": 4096, "telegram": 4096}
        max_len = platform_limits.get(platform, 1000)
        if len(message) > max_len:
            flags.append(f"message_too_long:{len(message)}/{max_len}")
            score -= 0.3

        # Check for URLs/links
        if "http" in message.lower() or "www." in message.lower():
            if platform in ["tiktok"]:
                flags.append("external_links_not_allowed")
                score -= 0.2

        # Check for excessive repetition
        words = message.lower().split()
        if len(words) > 3:
            from collections import Counter
            word_counts = Counter(words)
            most_common = word_counts.most_common(1)[0]
            if most_common[1] > 3:
                flags.append(f"word_repetition:{most_common[0]}x{most_common[1]}")
                score -= 0.1

        final_score = max(0.0, min(1.0, score))

        if final_score >= 0.8 and not flags:
            category = "compliant"
        elif final_score >= 0.5:
            category = "needs_review"
        else:
            category = "violation"

        return {
            "passed": final_score >= 0.5,
            "score": round(final_score, 3),
            "flags": flags,
            "category": category,
            "message_length": len(message),
        }


class AIPersonalizedMessaging:
    """AI-powered personalized message generation with safety controls.

    Uses template-based generation for pilot (no live LLM API required).
    Production would integrate with OpenAIService.
    """

    def __init__(self) -> None:
        self.moderator = MessageModerator()

    def generate_personalized_message(
        self,
        message_type: str,
        platform: str,
        username: str,
        branch_context: str = "Turkish retail business",
        branch_name: str = "",
        branch_location: str = "",
        interests: Optional[List[str]] = None,
        days_since_engagement: int = 0,
        conversation_context: str = "",
        campaign_name: str = "",
        follower_quality: str = "medium",
        engagement_history: Optional[List[str]] = None,
    ) -> Dict[str, Any]:
        """Generate a personalized message with safety controls.

        Template-based for pilot. Returns message + confidence + moderation result.
        """
        # Build context from engagement history
        context_parts = [branch_context]
        if engagement_history:
            context_parts.append(f"Recent activity: {', '.join(engagement_history[:3])}")
        if follower_quality == "high_value":
            context_parts.append("This is a high-value follower")
        elif follower_quality == "low_value":
            context_parts.append("This follower has low engagement")

        full_context = "; ".join(context_parts)

        # Generate using template
        message = self._generate_from_template(
            message_type=message_type,
            platform=platform,
            username=username,
            context=full_context,
            branch_name=branch_name or branch_context,
            branch_location=branch_location,
            interests=interests or [],
            days=days_since_engagement,
            conversation_context=conversation_context,
            campaign_name=campaign_name,
        )

        # Moderate
        moderation = self.moderator.moderate(message, platform)

        # Calculate confidence
        confidence = self._calculate_confidence(
            message_type=message_type,
            follower_quality=follower_quality,
            days_since_engagement=days_since_engagement,
            moderation_score=moderation["score"],
            has_history=bool(engagement_history),
        )

        return {
            "message": message,
            "subject": self._get_subject(message_type),
            "platform": platform,
            "confidence_score": round(confidence, 3),
            "moderation": moderation,
            "requires_review": confidence < 0.7 or moderation["category"] != "compliant",
            "personalization_context": {
                "branch": branch_context,
                "follower_quality": follower_quality,
                "engagement_history_count": len(engagement_history) if engagement_history else 0,
                "days_since_engagement": days_since_engagement,
            },
            "generated_at": datetime.now(timezone.utc).isoformat(),
            "note": "Template-based generation (pilot). LLM integration in production.",
        }

    def _generate_from_template(
        self,
        message_type: str,
        platform: str,
        username: str,
        context: str,
        branch_name: str,
        branch_location: str,
        interests: List[str],
        days: int,
        conversation_context: str,
        campaign_name: str,
    ) -> str:
        """Generate message from template."""
        if message_type not in SAFE_PROMPTS:
            message_type = "welcome_new_follower"

        # Simple template substitution (not using LLM for pilot)
        interest_str = ", ".join(interests[:2]) if interests else ""

        templates = {
            "welcome_new_follower": (
                f"Merhaba @{username}! Bizi takip ettiginiz icin tesekkur ederiz. "
                f"{branch_name} olarak yeni icerik ve kampanyalarimizdan haberdar olacaksiniz. "
                f"Bir sorunuz olursa bize ulasmaktan cekinmeyin."
            ),
            "campaign_suggestion": (
                f"Merhaba @{username}! {interest_str} alanindaki ilginizi dikkate alarak "
                f"sizin icin ozel bir kampanyamiz oldugunu dusunduk. "
                f"Detaylari ogrenmek ister misiniz?"
            ) if interests else (
                f"Merhaba @{username}! Yeni kampanyalarimiz basladi. "
                f"Size ozel firsatlari ogrenmek ister misiniz?"
            ),
            "reengagement_for_low": (
                f"Merhaba @{username}! Sizi aramizda ozledik. "
                f"Yeni iceriklerimiz ve kampanyalarimiz var. "
                f"Goz atmak isterseniz bizi takipte kalin."
            ),
            "win_back_unfollow": (
                f"Merhaba @{username}! Daha once bizi takip etmistiniz. "
                f"Yeniden aramiza katilmak isterseniz sizi memnuniyetle karsilariz. "
                f"Yeniliklerimizden haberdar olabilirsiniz."
            ),
            "dm_follow_up": (
                f"Merhaba @{username}! Onceki konusmamiza devam etmek ister misiniz? "
                f"Yardimci olabilecegimiz bir konu var mi?"
            ),
            "local_branch_campaign": (
                f"Merhaba! {branch_name} ({branch_location}) subemizde ozel bir kampanya basladi. "
                f"Yakinizdaysaniz ugramanizi tavsiye ederiz."
            ),
            "engagement_reward": (
                f"Merhaba @{username}! Aktif katiliminiz ve desteginiz icin tesekkur ederiz. "
                f"Sizin gibi degerli takipcilerimiz bizi motive ediyor."
            ),
        }

        return templates.get(message_type, templates["welcome_new_follower"])

    def _get_subject(self, message_type: str) -> str:
        """Get subject line for message type."""
        subjects = {
            "welcome_new_follower": "Hos Geldiniz",
            "campaign_suggestion": "Ozel Kampanya",
            "reengagement_for_low": "Sizi Ozledik",
            "win_back_unfollow": "Tekrar Hos Geldiniz",
            "dm_follow_up": "Takip",
            "local_branch_campaign": "Sube Ozel Kampanya",
            "engagement_reward": "Tesekkur",
        }
        return subjects.get(message_type, "Mesaj")

    def _calculate_confidence(
        self,
        message_type: str,
        follower_quality: str,
        days_since_engagement: int,
        moderation_score: float,
        has_history: bool,
    ) -> float:
        """Calculate generation confidence score."""
        base = 0.65

        # Message type reliability
        type_scores = {
            "welcome_new_follower": 0.1,
            "engagement_reward": 0.05,
            "dm_follow_up": 0.05,
            "campaign_suggestion": 0.0,
            "reengagement_for_low": -0.05,
            "local_branch_campaign": 0.0,
            "win_back_unfollow": -0.1,
        }
        base += type_scores.get(message_type, 0)

        # Follower quality
        quality_scores = {"high_value": 0.1, "medium_value": 0.0, "low_value": -0.1, "new": -0.05, "ghost": -0.15}
        base += quality_scores.get(follower_quality, 0)

        # Recency penalty
        if days_since_engagement > 30:
            base -= 0.1
        elif days_since_engagement > 60:
            base -= 0.2

        # History bonus
        if has_history:
            base += 0.1

        # Moderation score impact
        base += (moderation_score - 0.5) * 0.2

        return max(0.1, min(0.99, base))

    def preview_message(
        self,
        message_type: str,
        platform: str,
        username: str,
        **kwargs: Any,
    ) -> Dict[str, Any]:
        """Generate a preview for approval workflow.

        Returns full context needed for approval decision.
        """
        result = self.generate_personalized_message(
            message_type=message_type,
            platform=platform,
            username=username,
            **kwargs,
        )

        return {
            "preview": {
                "subject": result["subject"],
                "message": result["message"],
                "platform": platform,
                "recipient": username,
            },
            "ai_analysis": {
                "confidence_score": result["confidence_score"],
                "moderation_score": result["moderation"]["score"],
                "moderation_category": result["moderation"]["category"],
                "flags": result["moderation"]["flags"],
            },
            "recommendation": (
                "Approve" if result["confidence_score"] >= 0.75 and not result["requires_review"]
                else "Review" if result["confidence_score"] >= 0.5
                else "Reject"
            ),
            "requires_review": result["requires_review"],
            "personalization_context": result["personalization_context"],
            "note": result["note"],
        }
