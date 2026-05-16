"""Social Media Integration module for AI Marketing Platform.

Provides unified management of social media accounts across Instagram, Facebook,
TikTok, WhatsApp, Telegram, and Google Maps. Includes posting, analytics,
comment management, messaging, competitor tracking, and webhook processing.
"""

# Import Celery tasks for autodiscovery
from app.social import tasks as social_tasks
