"""Security audit, compliance logging, and monitoring module.

Provides database models, services, middleware, and API endpoints for:
- Audit logging (CRUD operations, API requests)
- Security event monitoring (suspicious activity detection)
- Login attempt tracking (brute force detection)
- API key management (scoped, rotatable)
- Data access logging (GDPR/KVKK compliance)
- Tenant leak detection
- Security headers injection
"""
