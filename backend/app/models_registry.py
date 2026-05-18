"""Import all SQLAlchemy models before mapper configuration.

FollowerSnapshot -> social_accounts FK and similar cross-module references
require all model modules to be imported before SQLAlchemy configures mappers.

Usage:
    from app.models_registry import import_all_models
    import_all_models()
"""

import logging

logger = logging.getLogger(__name__)


def import_all_models():
    """Eagerly import all SQLAlchemy model modules to register them in Base.metadata.

    This ensures cross-module ForeignKeys resolve correctly during mapper
    configuration (e.g. follower_snapshots.account_id -> social_accounts.id).
    """
    # Order matters: target FK tables must be imported BEFORE referencing tables.
    # User references Company/Branch → Company/Branch must come BEFORE app.auth.
    modules = [
        "app.companies.models",     # Company (User.company FK refs this)
        "app.branches.models",      # Branch (User.branch FK refs this)
        "app.social.models",        # SocialAccount (followers FK refs this)
        "app.ai.models",            # AIPrompt, AIConversation, AIMessage
        "app.ads.models",           # AdPlatform, AdCampaign, AdAudience
        "app.billing.models",       # SubscriptionPlan, Invoice
        "app.media.models",         # MediaAsset
        "app.analytics.models",     # AnalyticsSnapshot
        "app.followers.models",     # Follower, FollowerSnapshot
        "app.reports.models",       # ReportTemplate
        "app.governance.models",    # GDPRExportRequest
        "app.support.models",       # SupportTicket
        "app.events.models",        # EventLog
        "app.erp.models",           # ERPConnection
        "app.knowledge.models",     # KnowledgeBaseArticle
        "app.auth.models",          # User (refs Company, Branch) ← MUST be LAST
    ]

    imported = 0
    for mod_name in modules:
        try:
            __import__(mod_name)
            imported += 1
        except Exception as e:
            logger.warning(f"[MODELS] {mod_name}: import skipped ({e})")

    logger.info(f"[MODELS] {imported}/{len(modules)} model modules imported")

    # Explicitly configure mappers so all tables register in metadata
    # BEFORE any query tries to compile SQL with FK references
    try:
        from sqlalchemy.orm import configure_mappers
        configure_mappers()
        logger.info("[MODELS] SQLAlchemy mappers configured successfully")
    except Exception as e:
        logger.exception("[MODELS] configure_mappers FAILED: %s", e)
        raise
