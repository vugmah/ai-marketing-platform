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
    modules = [
        "app.auth.models",
        "app.companies.models",
        "app.branches.models",
        "app.social.models",
        "app.followers.models",
        "app.ai.models",
        "app.ads.models",
        "app.billing.models",
        "app.media.models",
        "app.analytics.models",
        "app.reports.models",
        "app.governance.models",
        "app.support.models",
        "app.realtime.models",
        "app.notifications.models",
        "app.events.models",
        "app.erp.models",
        "app.knowledge.models",
        "app.localization.models",
    ]

    imported = 0
    for mod_name in modules:
        try:
            __import__(mod_name)
            imported += 1
        except Exception as e:
            logger.warning(f"[MODELS] {mod_name}: import skipped ({e})")

    logger.info(f"[MODELS] {imported}/{len(modules)} model modules imported")
