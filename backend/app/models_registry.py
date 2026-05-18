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
    # Order matters: target FK tables must be imported before referencing tables
    modules = [
        "app.auth.models",          # users, roles, permissions
        "app.companies.models",     # companies
        "app.branches.models",      # branches
        "app.social.models",        # social_accounts ← MUST be before followers
        "app.ai.models",            # ai_prompts, ai_conversations, ai_messages
        "app.ads.models",           # ad_platforms, ad_campaigns, ad_audiences
        "app.billing.models",       # subscription_plans, invoices
        "app.media.models",         # media_assets
        "app.analytics.models",     # analytics_snapshots
        "app.followers.models",     # followers, follower_snapshots (refs social_accounts)
        "app.reports.models",       # report_templates
        "app.governance.models",    # gdpr_export_requests
        "app.support.models",       # support_tickets
        "app.events.models",        # event_log
        "app.erp.models",           # erp_connections
        "app.knowledge.models",     # knowledge_base_articles
    ]

    imported = 0
    for mod_name in modules:
        try:
            __import__(mod_name)
            imported += 1
        except Exception as e:
            logger.warning(f"[MODELS] {mod_name}: import skipped ({e})")

    logger.info(f"[MODELS] {imported}/{len(modules)} model modules imported")
