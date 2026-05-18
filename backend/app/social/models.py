"""SQLAlchemy models for the social media integration module.

All models include company_id and branch_id for multi-tenant isolation.
All token fields are stored encrypted using AES-256-GCM.
"""

import enum
from datetime import datetime

from sqlalchemy import (
    JSON,
    BigInteger,
    Boolean,
    Column,
    DateTime,
    Enum,
    ForeignKey,
    Index,
    Integer,
    Numeric,
    String,
    Text,
    func,
)
from sqlalchemy.orm import relationship

from app.database import Base


class SocialPlatform(str, enum.Enum):
    """Supported social media platforms."""

    INSTAGRAM = "instagram"
    FACEBOOK = "facebook"
    TIKTOK = "tiktok"
    WHATSAPP = "whatsapp"
    TELEGRAM = "telegram"
    GOOGLE_MAPS = "google_maps"


class AccountStatus(str, enum.Enum):
    """Status of a connected social media account."""

    ACTIVE = "active"
    DISCONNECTED = "disconnected"
    NOT_CONNECTED = "not_connected"
    ERROR = "error"


class PostStatus(str, enum.Enum):
    """Publication status of a social post."""

    DRAFT = "draft"
    SCHEDULED = "scheduled"
    PUBLISHED = "published"
    FAILED = "failed"


class CommentStatus(str, enum.Enum):
    """Status of a comment."""

    NEW = "new"
    READ = "read"
    REPLIED = "replied"


class CommentSentiment(str, enum.Enum):
    """Sentiment classification for comments."""

    POSITIVE = "positive"
    NEGATIVE = "negative"
    NEUTRAL = "neutral"


class MessageDirection(str, enum.Enum):
    """Direction of a message."""

    INBOUND = "inbound"
    OUTBOUND = "outbound"


class MessageStatus(str, enum.Enum):
    """Status of a message."""

    NEW = "new"
    READ = "read"
    REPLIED = "replied"


class MessageSentiment(str, enum.Enum):
    """Sentiment classification for messages."""

    POSITIVE = "positive"
    NEGATIVE = "negative"
    NEUTRAL = "neutral"


class SocialAccount(Base):
    """Connected social media account credentials and metadata.

    Attributes:
        id: Primary key.
        company_id: Tenant company ID.
        branch_id: Optional branch ID.
        platform: Social platform enum.
        account_name: Display name of the account.
        account_id: Platform-specific account/page ID.
        access_token: Encrypted OAuth access token.
        refresh_token: Encrypted OAuth refresh token.
        token_expires_at: Token expiration timestamp.
        profile_url: Public profile URL.
        follower_count: Cached follower count.
        status: Account connection status.
        last_sync_at: Last data sync timestamp.
        webhook_url: Platform webhook URL.
        settings: JSON settings per platform.
        created_at: Record creation timestamp.
        updated_at: Last update timestamp.
    """

    __tablename__ = "social_accounts"
    __table_args__ = (
        Index("ix_social_accounts_company_platform", "company_id", "platform"),
        Index("ix_social_accounts_branch", "branch_id", "company_id"),
        {"schema": None},
    )

    id = Column(Integer, primary_key=True, autoincrement=True)
    company_id = Column(
        Integer,
        ForeignKey("companies.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    branch_id = Column(
        Integer,
        ForeignKey("branches.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )
    platform = Column(
        Enum(SocialPlatform, name="socialplatform", create_type=True),
        nullable=False,
    )
    account_name = Column(String(255), nullable=False)
    account_id = Column(String(255), nullable=False)
    access_token = Column(Text, nullable=True)
    refresh_token = Column(Text, nullable=True)
    token_expires_at = Column(DateTime, nullable=True)
    profile_url = Column(String(500), nullable=True)
    follower_count = Column(Integer, default=0, nullable=False)
    status = Column(
        Enum(AccountStatus, name="accountstatus", create_type=True),
        default=AccountStatus.ACTIVE,
        nullable=False,
    )
    last_sync_at = Column(DateTime, nullable=True)
    webhook_url = Column(String(500), nullable=True)
    settings = Column(JSON, default=dict, nullable=False)
    created_at = Column(DateTime, server_default=func.now(), nullable=False)
    updated_at = Column(
        DateTime,
        server_default=func.now(),
        onupdate=func.now(),
        nullable=False,
    )

    # Relationships
    posts = relationship("SocialPost", back_populates="account", cascade="all, delete-orphan")
    comments = relationship("SocialComment", back_populates="account", cascade="all, delete-orphan")
    messages = relationship("SocialMessage", back_populates="account", cascade="all, delete-orphan")
    analytics = relationship("SocialAnalytic", back_populates="account", cascade="all, delete-orphan")

    # Follower Intelligence relationships
    follower_snapshots = relationship(
        "app.followers.models.FollowerSnapshot",
        back_populates="account",
        cascade="all, delete-orphan",
        lazy="selectin",
    )
    bot_patterns = relationship(
        "app.followers.models.BotPattern",
        back_populates="account",
        cascade="all, delete-orphan",
        lazy="selectin",
    )
    suspicious_activities = relationship(
        "app.followers.models.SuspiciousActivity",
        back_populates="account",
        cascade="all, delete-orphan",
        lazy="selectin",
    )
    audience_demographics = relationship(
        "app.followers.models.AudienceDemographics",
        back_populates="account",
        cascade="all, delete-orphan",
        lazy="selectin",
    )
    engagement_qualities = relationship(
        "app.followers.models.EngagementQuality",
        back_populates="account",
        cascade="all, delete-orphan",
        lazy="selectin",
    )
    follower_health_scores = relationship(
        "app.followers.models.FollowerHealthScore",
        back_populates="account",
        cascade="all, delete-orphan",
        lazy="selectin",
    )
    follower_insights = relationship(
        "app.followers.models.FollowerInsight",
        back_populates="account",
        cascade="all, delete-orphan",
        lazy="selectin",
    )
    ai_recommendations = relationship(
        "app.followers.models.AIAudienceRecommendation",
        back_populates="account",
        cascade="all, delete-orphan",
        lazy="selectin",
    )

    def __repr__(self) -> str:
        return f"<SocialAccount(id={self.id}, platform='{self.platform}', name='{self.account_name}')>"


class SocialPost(Base):
    """Social media post content and scheduling.

    Attributes:
        id: Primary key.
        company_id: Tenant company ID.
        branch_id: Optional branch ID.
        account_id: Linked social account.
        platform: Target platform.
        external_post_id: Platform-assigned post ID.
        content: Post text content.
        media_urls: JSON array of media file URLs.
        hashtags: Hashtags string.
        status: Publication status.
        scheduled_at: Scheduled publish time.
        published_at: Actual publish time.
        engagement_stats: JSON engagement metrics.
        ai_generated: Whether content was AI-generated.
        created_at: Record creation timestamp.
        updated_at: Last update timestamp.
    """

    __tablename__ = "social_posts"
    __table_args__ = (
        Index("ix_social_posts_company_status", "company_id", "status"),
        Index("ix_social_posts_account", "account_id", "status"),
        {"schema": None},
    )

    id = Column(Integer, primary_key=True, autoincrement=True)
    company_id = Column(
        Integer,
        ForeignKey("companies.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    branch_id = Column(
        Integer,
        ForeignKey("branches.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )
    account_id = Column(
        Integer,
        ForeignKey("social_accounts.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    platform = Column(
        Enum(SocialPlatform, name="socialplatform_posts", create_type=False),
        nullable=False,
    )
    external_post_id = Column(String(255), nullable=True, index=True)
    content = Column(Text, nullable=False)
    media_urls = Column(JSON, default=list, nullable=False)
    hashtags = Column(String(500), nullable=True)
    status = Column(
        Enum(PostStatus, name="poststatus", create_type=True),
        default=PostStatus.DRAFT,
        nullable=False,
    )
    scheduled_at = Column(DateTime, nullable=True, index=True)
    published_at = Column(DateTime, nullable=True)
    engagement_stats = Column(
        JSON,
        default=lambda: {
            "likes": 0,
            "shares": 0,
            "comments": 0,
            "clicks": 0,
            "impressions": 0,
            "reach": 0,
        },
        nullable=False,
    )
    ai_generated = Column(Boolean, default=False, nullable=False)
    created_at = Column(DateTime, server_default=func.now(), nullable=False)
    updated_at = Column(
        DateTime,
        server_default=func.now(),
        onupdate=func.now(),
        nullable=False,
    )

    # Relationships
    account = relationship("SocialAccount", back_populates="posts")
    comments = relationship("SocialComment", back_populates="post", cascade="all, delete-orphan")

    def __repr__(self) -> str:
        return f"<SocialPost(id={self.id}, platform='{self.platform}', status='{self.status}')>"


class SocialComment(Base):
    """Comments on social media posts.

    Attributes:
        id: Primary key.
        company_id: Tenant company ID.
        branch_id: Optional branch ID.
        account_id: Linked social account.
        post_id: Linked social post.
        external_comment_id: Platform-assigned comment ID.
        parent_comment_id: For threaded replies.
        author_name: Comment author's display name.
        author_id: Platform-assigned author ID.
        content: Comment text.
        sentiment: AI-analyzed sentiment.
        status: Comment status.
        replied_content: Our reply text.
        created_at: Record creation timestamp.
        updated_at: Last update timestamp.
    """

    __tablename__ = "social_comments"
    __table_args__ = (
        Index("ix_social_comments_company_status", "company_id", "status"),
        Index("ix_social_comments_post", "post_id", "created_at"),
        {"schema": None},
    )

    id = Column(Integer, primary_key=True, autoincrement=True)
    company_id = Column(
        Integer,
        ForeignKey("companies.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    branch_id = Column(
        Integer,
        ForeignKey("branches.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )
    account_id = Column(
        Integer,
        ForeignKey("social_accounts.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    post_id = Column(
        Integer,
        ForeignKey("social_posts.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    external_comment_id = Column(String(255), nullable=True, index=True)
    parent_comment_id = Column(String(255), nullable=True)
    author_name = Column(String(255), nullable=False)
    author_id = Column(String(255), nullable=True)
    content = Column(Text, nullable=False)
    sentiment = Column(
        Enum(CommentSentiment, name="commentsentiment", create_type=True),
        nullable=True,
    )
    status = Column(
        Enum(CommentStatus, name="commentstatus", create_type=True),
        default=CommentStatus.NEW,
        nullable=False,
    )
    replied_content = Column(Text, nullable=True)
    created_at = Column(DateTime, server_default=func.now(), nullable=False)
    updated_at = Column(
        DateTime,
        server_default=func.now(),
        onupdate=func.now(),
        nullable=False,
    )

    # Relationships
    account = relationship("SocialAccount", back_populates="comments")
    post = relationship("SocialPost", back_populates="comments")

    def __repr__(self) -> str:
        return f"<SocialComment(id={self.id}, post_id={self.post_id}, status='{self.status}')>"


class SocialMessage(Base):
    """Direct/conversation messages from social platforms.

    Attributes:
        id: Primary key.
        company_id: Tenant company ID.
        branch_id: Optional branch ID.
        account_id: Linked social account.
        platform: Source platform.
        external_conversation_id: Platform conversation/thread ID.
        external_message_id: Platform message ID.
        sender_name: Sender display name.
        sender_id: Platform sender ID.
        content: Message text.
        direction: Inbound or outbound.
        status: Message status.
        created_at: Record creation timestamp.
        updated_at: Last update timestamp.
    """

    __tablename__ = "social_messages"
    __table_args__ = (
        Index("ix_social_messages_company_conv", "company_id", "external_conversation_id"),
        Index("ix_social_messages_account", "account_id", "created_at"),
        {"schema": None},
    )

    id = Column(Integer, primary_key=True, autoincrement=True)
    company_id = Column(
        Integer,
        ForeignKey("companies.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    branch_id = Column(
        Integer,
        ForeignKey("branches.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )
    account_id = Column(
        Integer,
        ForeignKey("social_accounts.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    platform = Column(
        Enum(SocialPlatform, name="socialplatform_messages", create_type=False),
        nullable=False,
    )
    external_conversation_id = Column(String(255), nullable=False, index=True)
    external_message_id = Column(String(255), nullable=True, index=True)
    sender_name = Column(String(255), nullable=False)
    sender_id = Column(String(255), nullable=True)
    content = Column(Text, nullable=False)
    direction = Column(
        Enum(MessageDirection, name="messagedirection", create_type=True),
        nullable=False,
    )
    status = Column(
        Enum(MessageStatus, name="messagestatus", create_type=True),
        default=MessageStatus.NEW,
        nullable=False,
    )
    sentiment = Column(
        Enum(MessageSentiment, name="messagesentiment", create_type=True),
        nullable=True,
    )
    ai_suggested_reply = Column(Text, nullable=True)
    ai_auto_reply_sent = Column(Boolean, default=False, nullable=False)
    created_at = Column(DateTime, server_default=func.now(), nullable=False)
    updated_at = Column(
        DateTime,
        server_default=func.now(),
        onupdate=func.now(),
        nullable=False,
    )

    # Relationships
    account = relationship("SocialAccount", back_populates="messages")

    def __repr__(self) -> str:
        return (
            f"<SocialMessage(id={self.id}, platform='{self.platform}', "
            f"direction='{self.direction}')>"
        )


    conversation = relationship(
        "app.ai.models.AIConversation",
        back_populates="messages",
        lazy="selectin",
    )

class SocialAnalytic(Base):
    """Daily social media analytics snapshots.

    Attributes:
        id: Primary key.
        company_id: Tenant company ID.
        branch_id: Optional branch ID.
        account_id: Linked social account.
        platform: Source platform.
        metric_date: Date of the metrics.
        impressions: Total impressions.
        reach: Unique reach.
        engagement: Total engagements.
        clicks: Link clicks.
        shares: Share count.
        comments: Comment count.
        likes: Like count.
        followers_gained: New followers.
        followers_lost: Lost followers.
        raw_data: Full platform response JSON.
        created_at: Record creation timestamp.
    """

    __tablename__ = "social_analytics"
    __table_args__ = (
        Index("ix_social_analytics_account_date", "account_id", "metric_date"),
        Index("ix_social_analytics_company_date", "company_id", "metric_date"),
        {"schema": None},
    )

    id = Column(Integer, primary_key=True, autoincrement=True)
    company_id = Column(
        Integer,
        ForeignKey("companies.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    branch_id = Column(
        Integer,
        ForeignKey("branches.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )
    account_id = Column(
        Integer,
        ForeignKey("social_accounts.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    platform = Column(
        Enum(SocialPlatform, name="socialplatform_analytics", create_type=False),
        nullable=False,
    )
    metric_date = Column(DateTime, nullable=False)
    impressions = Column(BigInteger, default=0, nullable=False)
    reach = Column(BigInteger, default=0, nullable=False)
    engagement = Column(BigInteger, default=0, nullable=False)
    clicks = Column(BigInteger, default=0, nullable=False)
    shares = Column(BigInteger, default=0, nullable=False)
    comments = Column(BigInteger, default=0, nullable=False)
    likes = Column(BigInteger, default=0, nullable=False)
    followers_gained = Column(Integer, default=0, nullable=False)
    followers_lost = Column(Integer, default=0, nullable=False)
    raw_data = Column(JSON, default=dict, nullable=False)
    created_at = Column(DateTime, server_default=func.now(), nullable=False)

    # Relationships
    account = relationship("SocialAccount", back_populates="analytics")

    def __repr__(self) -> str:
        return f"<SocialAnalytic(id={self.id}, account_id={self.account_id}, date='{self.metric_date}')>"


    media = relationship(
        "app.media.models.MediaAsset",
        back_populates="analytics",
        lazy="selectin",
    )

class SocialCompetitor(Base):
    """Tracked competitor accounts for competitive analysis.

    Attributes:
        id: Primary key.
        company_id: Tenant company ID.
        branch_id: Optional branch ID.
        platform: Competitor's platform.
        competitor_name: Display name.
        competitor_account_id: Platform account ID.
        follower_count: Cached follower count.
        post_count: Cached post count.
        avg_engagement: Average engagement rate.
        last_analyzed_at: Last analysis timestamp.
        metrics_history: JSON historical data.
        created_at: Record creation timestamp.
        updated_at: Last update timestamp.
    """

    __tablename__ = "social_competitors"
    __table_args__ = (
        Index("ix_social_competitors_company", "company_id", "platform"),
        {"schema": None},
    )

    id = Column(Integer, primary_key=True, autoincrement=True)
    company_id = Column(
        Integer,
        ForeignKey("companies.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    branch_id = Column(
        Integer,
        ForeignKey("branches.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )
    platform = Column(
        Enum(SocialPlatform, name="socialplatform_competitors", create_type=False),
        nullable=False,
    )
    competitor_name = Column(String(255), nullable=False)
    competitor_account_id = Column(String(255), nullable=False)
    follower_count = Column(Integer, nullable=True)
    post_count = Column(Integer, nullable=True)
    avg_engagement = Column(Numeric(10, 4), nullable=True)
    last_analyzed_at = Column(DateTime, nullable=True)
    metrics_history = Column(JSON, default=list, nullable=False)
    created_at = Column(DateTime, server_default=func.now(), nullable=False)
    updated_at = Column(
        DateTime,
        server_default=func.now(),
        onupdate=func.now(),
        nullable=False,
    )

    def __repr__(self) -> str:
        return (
            f"<SocialCompetitor(id={self.id}, platform='{self.platform}', "
            f"name='{self.competitor_name}')>"
        )


class QueueStatus(str, enum.Enum):
    """Status of a publishing queue item."""

    PENDING = "pending"
    PROCESSING = "processing"
    PUBLISHED = "published"
    FAILED = "failed"
    CANCELLED = "cancelled"


class PublishingQueue(Base):
    """Sequential publishing queue with rate limit control.

    Attributes:
        id: Primary key.
        company_id: Tenant company ID.
        branch_id: Optional branch ID.
        account_id: Target social account.
        post_id: Linked social post.
        platform: Target platform.
        sequence_order: Publishing order within the queue.
        status: Queue item status.
        scheduled_at: Planned publish time.
        published_at: Actual publish time.
        retry_count: Number of publish attempts.
        last_error: Last error message if failed.
        rate_limit_delay: Delay in seconds between this and next publish.
        created_at: Record creation timestamp.
        updated_at: Last update timestamp.
    """

    __tablename__ = "social_publishing_queue"
    __table_args__ = (
        Index("ix_publishing_queue_company_status", "company_id", "status"),
        Index("ix_publishing_queue_scheduled", "scheduled_at", "status"),
        {"schema": None},
    )

    id = Column(Integer, primary_key=True, autoincrement=True)
    company_id = Column(
        Integer,
        ForeignKey("companies.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    branch_id = Column(
        Integer,
        ForeignKey("branches.id", ondelete="SET NULL"),
        nullable=True,
    )
    account_id = Column(
        Integer,
        ForeignKey("social_accounts.id", ondelete="CASCADE"),
        nullable=False,
    )
    post_id = Column(
        Integer,
        ForeignKey("social_posts.id", ondelete="CASCADE"),
        nullable=False,
    )
    platform = Column(
        Enum(SocialPlatform, name="socialplatform_queue", create_type=False),
        nullable=False,
    )
    sequence_order = Column(Integer, default=0, nullable=False)
    status = Column(
        Enum(QueueStatus, name="queuestatus", create_type=True),
        default=QueueStatus.PENDING,
        nullable=False,
    )
    scheduled_at = Column(DateTime, nullable=True, index=True)
    published_at = Column(DateTime, nullable=True)
    retry_count = Column(Integer, default=0, nullable=False)
    last_error = Column(Text, nullable=True)
    rate_limit_delay = Column(Integer, default=60, nullable=False)
    created_at = Column(DateTime, server_default=func.now(), nullable=False)
    updated_at = Column(
        DateTime,
        server_default=func.now(),
        onupdate=func.now(),
        nullable=False,
    )

    def __repr__(self) -> str:
        return (
            f"<PublishingQueue(id={self.id}, post_id={self.post_id}, "
            f"status='{self.status}', seq={self.sequence_order})>"
        )


class SocialListening(Base):
    """Social listening entries for hashtag/mention tracking.

    Attributes:
        id: Primary key.
        company_id: Tenant company ID.
        branch_id: Optional branch ID.
        platform: Platform to monitor.
        listen_type: Type of listening (hashtag, mention, keyword).
        target: The hashtag, username, or keyword to track.
        is_active: Whether this listening entry is active.
        last_result_count: Count of results from last check.
        last_checked_at: Last check timestamp.
        results_summary: JSON summary of latest results.
        settings: Additional settings.
        created_at: Record creation timestamp.
        updated_at: Last update timestamp.
    """

    __tablename__ = "social_listening"
    __table_args__ = (
        Index("ix_social_listening_company", "company_id", "is_active"),
        Index("ix_social_listening_target", "platform", "listen_type", "target"),
        {"schema": None},
    )

    id = Column(Integer, primary_key=True, autoincrement=True)
    company_id = Column(
        Integer,
        ForeignKey("companies.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    branch_id = Column(
        Integer,
        ForeignKey("branches.id", ondelete="SET NULL"),
        nullable=True,
    )
    platform = Column(
        Enum(SocialPlatform, name="socialplatform_listening", create_type=False),
        nullable=False,
    )
    listen_type = Column(String(50), nullable=False)
    target = Column(String(255), nullable=False)
    is_active = Column(Boolean, default=True, nullable=False, index=True)
    last_result_count = Column(Integer, default=0, nullable=False)
    last_checked_at = Column(DateTime, nullable=True)
    results_summary = Column(JSON, default=list, nullable=False)
    settings = Column(JSON, default=dict, nullable=False)
    created_at = Column(DateTime, server_default=func.now(), nullable=False)
    updated_at = Column(
        DateTime,
        server_default=func.now(),
        onupdate=func.now(),
        nullable=False,
    )

    def __repr__(self) -> str:
        return (
            f"<SocialListening(id={self.id}, platform='{self.platform}', "
            f"type='{self.listen_type}', target='{self.target}')>"
        )


class HashtagIntelligence(Base):
    """Popular hashtag intelligence and recommendations.

    Attributes:
        id: Primary key.
        company_id: Tenant company ID.
        branch_id: Optional branch ID.
        platform: Platform for the hashtag.
        hashtag: The hashtag string (without #).
        post_count: Number of posts using this hashtag.
        engagement_avg: Average engagement rate for posts with this hashtag.
        trend_direction: Trending direction (up, down, stable).
        related_hashtags: JSON list of related hashtags.
        suggested_for: JSON list of company post categories.
        last_analyzed_at: Last analysis timestamp.
        created_at: Record creation timestamp.
        updated_at: Last update timestamp.
    """

    __tablename__ = "social_hashtag_intelligence"
    __table_args__ = (
        Index("ix_hashtag_intel_company", "company_id", "platform"),
        Index("ix_hashtag_intel_trend", "trend_direction", "engagement_avg"),
        {"schema": None},
    )

    id = Column(Integer, primary_key=True, autoincrement=True)
    company_id = Column(
        Integer,
        ForeignKey("companies.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    branch_id = Column(
        Integer,
        ForeignKey("branches.id", ondelete="SET NULL"),
        nullable=True,
    )
    platform = Column(
        Enum(SocialPlatform, name="socialplatform_hashtags", create_type=False),
        nullable=False,
    )
    hashtag = Column(String(100), nullable=False)
    post_count = Column(BigInteger, default=0, nullable=False)
    engagement_avg = Column(Numeric(10, 4), default=0, nullable=False)
    trend_direction = Column(String(20), default="stable", nullable=False)
    related_hashtags = Column(JSON, default=list, nullable=False)
    suggested_for = Column(JSON, default=list, nullable=False)
    last_analyzed_at = Column(DateTime, nullable=True)
    created_at = Column(DateTime, server_default=func.now(), nullable=False)
    updated_at = Column(
        DateTime,
        server_default=func.now(),
        onupdate=func.now(),
        nullable=False,
    )

    def __repr__(self) -> str:
        return (
            f"<HashtagIntelligence(id={self.id}, hashtag='{self.hashtag}', "
            f"platform='{self.platform}', trend='{self.trend_direction}')>"
        )


class SocialWebhook(Base):
    """Received webhook events from social media platforms.

    Attributes:
        id: Primary key.
        company_id: Tenant company ID.
        account_id: Linked social account.
        platform: Source platform.
        event_type: Platform event type.
        payload: Full webhook payload JSON.
        processed: Whether the event was processed.
        processed_at: Processing timestamp.
        error_message: Error if processing failed.
        signature_verified: Whether the webhook signature was verified.
        created_at: Record creation timestamp.
    """

    __tablename__ = "social_webhooks"
    __table_args__ = (
        Index("ix_social_webhooks_company", "company_id", "processed"),
        Index("ix_social_webhooks_platform_event", "platform", "event_type"),
        {"schema": None},
    )

    id = Column(Integer, primary_key=True, autoincrement=True)
    company_id = Column(
        Integer,
        ForeignKey("companies.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    account_id = Column(
        Integer,
        ForeignKey("social_accounts.id", ondelete="CASCADE"),
        nullable=True,
        index=True,
    )
    platform = Column(
        Enum(SocialPlatform, name="socialplatform_webhooks", create_type=False),
        nullable=False,
    )
    event_type = Column(String(100), nullable=False)
    payload = Column(JSON, default=dict, nullable=False)
    processed = Column(Boolean, default=False, nullable=False, index=True)
    processed_at = Column(DateTime, nullable=True)
    error_message = Column(Text, nullable=True)
    signature_verified = Column(Boolean, default=False, nullable=False)
    created_at = Column(DateTime, server_default=func.now(), nullable=False)

    def __repr__(self) -> str:
        return (
            f"<SocialWebhook(id={self.id}, platform='{self.platform}', "
            f"event='{self.event_type}', processed={self.processed})>"
        )
