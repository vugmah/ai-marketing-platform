"""Constants and configuration for the AI Customer Support module."""

# ---------------------------------------------------------------------------
# AI Auto-Reply Configuration
# ---------------------------------------------------------------------------

# Minimum confidence score (0.0-1.0) for AI auto-replies to be sent automatically
AI_AUTO_REPLY_CONFIDENCE_THRESHOLD: float = 0.7

# Minimum confidence score to suggest an AI reply (below auto-send threshold)
AI_SUGGESTION_CONFIDENCE_THRESHOLD: float = 0.5

# Maximum character length for AI auto-replies
AI_REPLY_MAX_LENGTH: int = 2000

# ---------------------------------------------------------------------------
# Human Takeover Triggers
# ---------------------------------------------------------------------------

# Confidence score below this triggers automatic human takeover
HUMAN_TAKEOVER_CONFIDENCE_THRESHOLD: float = 0.4

# Sentiment score below this (negative) triggers human takeover
HUMAN_TAKEOVER_SENTIMENT_THRESHOLD: str = "negative"

# Keywords that trigger immediate human takeover
HUMAN_TAKEOVER_KEYWORDS: list[str] = [
    "human",
    "agent",
    "representative",
    "supervisor",
    "manager",
    "speak to a person",
    "real person",
    "not a robot",
    "frustrated",
    "angry",
    "cancel account",
    "lawsuit",
    "lawyer",
    "escalate",
    "complaint",
    "terrible service",
    "worst",
    "refund now",
    "chargeback",
]

# Number of consecutive low-confidence responses before human takeover
HUMAN_TAKEOVER_CONSECUTIVE_LOW_CONFIDENCE: int = 3

# ---------------------------------------------------------------------------
# SLA Targets (in minutes)
# ---------------------------------------------------------------------------

SLA_RESPONSE_TIME_MINUTES: dict[str, int] = {
    "low": 240,      # 4 hours
    "medium": 120,   # 2 hours
    "high": 30,      # 30 minutes
    "urgent": 15,    # 15 minutes
}

SLA_RESOLUTION_TIME_MINUTES: dict[str, int] = {
    "low": 2880,     # 48 hours
    "medium": 1440,  # 24 hours
    "high": 480,     # 8 hours
    "urgent": 120,   # 2 hours
}

# ---------------------------------------------------------------------------
# Sentiment Configuration
# ---------------------------------------------------------------------------

SENTIMENT_THRESHOLD_NEGATIVE: float = -0.3
SENTIMENT_THRESHOLD_POSITIVE: float = 0.3
SENTIMENT_LABELS: list[str] = ["positive", "negative", "neutral"]

# ---------------------------------------------------------------------------
# RAG (Retrieval-Augmented Generation) Configuration
# ---------------------------------------------------------------------------

RAG_TOP_K_RESULTS: int = 5
RAG_MIN_RELEVANCE_SCORE: float = 0.6
RAG_MAX_CONTEXT_TOKENS: int = 3000
RAG_CONTEXT_TEMPLATE: str = """Relevant knowledge base articles:

{context}

---
Use the above knowledge base articles to help answer the customer's question.
If the articles don't contain relevant information, use your general knowledge
but indicate that the information may not be from our official documentation.
"""

# ---------------------------------------------------------------------------
# Escalation Configuration
# ---------------------------------------------------------------------------

ESCALATION_NOTIFY_CHANNELS: list[str] = ["email", "in_app", "push"]
ESCALATION_MAX_ESCALATION_LEVELS: int = 3

# ---------------------------------------------------------------------------
# Ticket Status Workflow
# ---------------------------------------------------------------------------

VALID_TICKET_STATUS_TRANSITIONS: dict[str, list[str]] = {
    "open": ["pending", "resolved", "closed"],
    "pending": ["open", "resolved", "closed"],
    "resolved": ["open", "closed"],
    "closed": ["open"],
}

# ---------------------------------------------------------------------------
# Ticket Sources
# ---------------------------------------------------------------------------

TICKET_SOURCES: list[str] = [
    "whatsapp",
    "telegram",
    "instagram",
    "facebook",
    "email",
    "web",
]

# ---------------------------------------------------------------------------
# Ticket Priorities
# ---------------------------------------------------------------------------

TICKET_PRIORITIES: list[str] = ["low", "medium", "high", "urgent"]

# ---------------------------------------------------------------------------
# Ticket Categories
# ---------------------------------------------------------------------------

TICKET_CATEGORIES: list[str] = ["billing", "technical", "sales", "general"]

# ---------------------------------------------------------------------------
# KB Article Configuration
# ---------------------------------------------------------------------------

KB_ARTICLE_STATUSES: list[str] = ["draft", "published", "archived"]
KB_ARTICLE_SOURCES: list[str] = ["manual", "ai_generated"]

# ---------------------------------------------------------------------------
# Analytics Configuration
# ---------------------------------------------------------------------------

ANALYTICS_AGGREGATION_DAYS: int = 30
CUSTOMER_SATISFACTION_SCALE: int = 5

# ---------------------------------------------------------------------------
# Conversation Configuration
# ---------------------------------------------------------------------------

CONVERSATION_SOURCES: list[str] = [
    "whatsapp",
    "telegram",
    "instagram",
    "facebook",
    "email",
    "web",
]

# ---------------------------------------------------------------------------
# Forbidden Response Filters
# ---------------------------------------------------------------------------

# Yasakli kelimeler - AI cevabinda bunlar gecerse otomatik red
FORBIDDEN_KEYWORDS: list[str] = [
    "password",
    "credit card",
    "cvv",
    "social security",
    "ssn",
    "bank account",
    "iban",
    "kimlik numarasi",
    "kredi karti",
    "sifre",
]

# Yasakli cevap sablonlari - AI'in "uydurma" cevap vermesini engel
FORBIDDEN_RESPONSE_PATTERNS: list[str] = [
    "I don't have access to",
    "I cannot access",
    "I don't know your",
    "I cannot see your",
    "I don't have information about your account",
    "I'm not sure about the specific details",
    "I don't have real-time access",
    "I don't have the ability to",
    "I cannot verify",
    "I don't have up-to-date information",
]

# AI'in ASLA soylememesi gereken seyler
FORBIDDEN_RESPONSE_DENYLIST: list[str] = [
    "I am an AI language model",
    "As an AI",
    "I don't have feelings",
    "I don't have personal experiences",
    "I don't have opinions",
    "I don't have access to your data",
    "I don't have access to our database",
    "I cannot check your account",
    "I don't have real-time data",
    "I cannot see your previous orders",
    "I don't have access to your order history",
    "I cannot verify your payment",
    "I don't have access to your payment information",
    "I'm just an AI",
    "I don't have the capability",
    "I cannot process refunds",
    "I cannot access the system",
    "I don't have system access",
]

# ---------------------------------------------------------------------------
# Audit Log Configuration
# ---------------------------------------------------------------------------

AUDIT_LOG_RETENTION_DAYS: int = 90

# ---------------------------------------------------------------------------
# AI Prompt Templates for Support
# ---------------------------------------------------------------------------

AI_CATEGORIZATION_SYSTEM_PROMPT: str = (
    "You are a customer support ticket categorization assistant. "
    "Analyze the ticket content and classify it into exactly one category: "
    "billing, technical, sales, or general. "
    "Respond with ONLY the category name, nothing else."
)

AI_SENTIMENT_SYSTEM_PROMPT: str = (
    "You are a sentiment analysis assistant. "
    "Analyze the emotional tone of the message and classify it as: "
    "positive, negative, or neutral. "
    "Respond with ONLY the sentiment label, nothing else."
)

AI_REPLY_SYSTEM_PROMPT: str = (
    "You are a professional customer support agent. "
    "Provide helpful, accurate, and friendly responses. "
    "Use the provided knowledge base context when relevant. "
    "If you cannot fully answer the question, suggest escalating to a human agent. "
    "Keep responses concise but complete. Always be empathetic and professional."
)

AI_REPLY_CONFIDENCE_SYSTEM_PROMPT: str = (
    "You are a confidence scoring assistant. "
    "Rate how confident you are that the provided AI response fully and accurately "
    "answers the customer's question. Return ONLY a float between 0.0 and 1.0, "
    "where 1.0 means completely confident and 0.0 means not confident at all. "
    "Respond with ONLY the numeric score, nothing else."
)

# ---------------------------------------------------------------------------
# Cache Configuration
# ---------------------------------------------------------------------------

SUPPORT_CACHE_PREFIX: str = "support"
KB_SEARCH_CACHE_TTL_SECONDS: int = 300  # 5 minutes
TICKET_LIST_CACHE_TTL_SECONDS: int = 60  # 1 minute
ANALYTICS_CACHE_TTL_SECONDS: int = 600  # 10 minutes
