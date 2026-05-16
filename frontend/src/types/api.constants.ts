// ============================================
// AI Marketing Platform - API Constants
// Auto-generated from OpenAPI Schema
// ============================================

// ============================================
// HTTP Status Codes
// ============================================

export const HttpStatus = {
  OK: 200,
  CREATED: 201,
  ACCEPTED: 202,
  NO_CONTENT: 204,
  BAD_REQUEST: 400,
  UNAUTHORIZED: 401,
  FORBIDDEN: 403,
  NOT_FOUND: 404,
  CONFLICT: 409,
  UNPROCESSABLE: 422,
  TOO_MANY_REQUESTS: 429,
  INTERNAL_ERROR: 500,
  SERVICE_UNAVAILABLE: 503,
} as const;

export type HttpStatusCode = typeof HttpStatus[keyof typeof HttpStatus];

// ============================================
// API Version
// ============================================

export const API_VERSION = 'v2';
export const API_BASE_PATH = '/api/v2';

// ============================================
// Module Paths
// ============================================

export const ApiPaths = {
  auth: '/api/v2/auth',
  companies: '/api/v2/companies',
  branches: '/api/v2/branches',
  dashboard: '/api/v2/dashboard',
  analytics: '/api/v2/analytics',
  notifications: '/api/v2/notifications',
  erp: '/api/v2/erp',
  ai: '/api/v2/ai',
  social: '/api/v2/social',
  media: '/api/v2/media',
  events: '/api/v2/events',
  billing: '/api/v2/billing',
  audit: '/api/v2/audit',
  health: '/api/v2/health',
  ads: '/api/v2/ads',
  support: '/api/v2/support',
} as const;

export type ApiModule = keyof typeof ApiPaths;

// ============================================
// Module Tags (FastAPI tags)
// ============================================

export const ApiTags = {
  auth: 'Authentication',
  companies: 'Companies',
  branches: 'Branches',
  dashboard: 'Dashboard',
  analytics: 'Analytics',
  notifications: 'Notifications',
  erp: 'ERP Integration',
  ai: 'AI Architecture',
  social: 'Social Media',
  media: 'Creative Studio',
  events: 'Events',
  billing: 'Billing',
  audit: 'Audit & Security',
  health: 'Health',
  ads: 'Ads Intelligence',
  support: 'AI Support',
} as const;

// ============================================
// Error Types
// ============================================

export const ErrorTypes = {
  VALIDATION: 'validation_error',
  AUTHENTICATION: 'authentication_error',
  AUTHORIZATION: 'authorization_error',
  NOT_FOUND: 'not_found',
  CONFLICT: 'conflict',
  RATE_LIMIT: 'rate_limit',
  INTERNAL: 'internal_error',
  SERVICE_UNAVAILABLE: 'service_unavailable',
  TENANT_ISOLATION: 'tenant_isolation_error',
} as const;

export type ErrorType = keyof typeof ErrorTypes;

// ============================================
// Pagination Defaults
// ============================================

export const PaginationDefaults = {
  page: 1,
  pageSize: 20,
  maxPageSize: 100,
} as const;

// ============================================
// HTTP Methods
// ============================================

export const HttpMethods = {
  GET: 'GET',
  POST: 'POST',
  PUT: 'PUT',
  PATCH: 'PATCH',
  DELETE: 'DELETE',
} as const;

export type HttpMethod = keyof typeof HttpMethods;

// ============================================
// Content Types
// ============================================

export const ContentType = {
  JSON: 'application/json',
  FORM_DATA: 'multipart/form-data',
  FORM_URLENCODED: 'application/x-www-form-urlencoded',
  TEXT_PLAIN: 'text/plain',
  OCTET_STREAM: 'application/octet-stream',
} as const;

// ============================================
// Cache TTL (seconds)
// ============================================

export const CacheTTL = {
  SHORT: 60,       // 1 minute
  MEDIUM: 300,     // 5 minutes
  LONG: 900,       // 15 minutes
  VERY_LONG: 3600, // 1 hour
} as const;

// ============================================
// Date Formats
// ============================================

export const DateFormat = {
  ISO: 'YYYY-MM-DDTHH:mm:ss.sssZ',
  DATE: 'YYYY-MM-DD',
  DATETIME: 'YYYY-MM-DD HH:mm:ss',
  DISPLAY: 'DD/MM/YYYY HH:mm',
} as const;

// ============================================
// Ad Platforms
// ============================================

export const AdPlatforms = {
  GOOGLE_ADS: 'google_ads',
  META_ADS: 'meta_ads',
  TIKTOK_ADS: 'tiktok_ads',
  LINKEDIN_ADS: 'linkedin_ads',
  TWITTER_ADS: 'twitter_ads',
} as const;

export type AdPlatform = typeof AdPlatforms[keyof typeof AdPlatforms];

// ============================================
// Social Platforms
// ============================================

export const SocialPlatforms = {
  FACEBOOK: 'facebook',
  INSTAGRAM: 'instagram',
  TWITTER: 'twitter',
  LINKEDIN: 'linkedin',
  TIKTOK: 'tiktok',
  YOUTUBE: 'youtube',
  PINTEREST: 'pinterest',
} as const;

export type SocialPlatform = typeof SocialPlatforms[keyof typeof SocialPlatforms];

// ============================================
// ERP Providers
// ============================================

export const ErpProviders = {
  SAP: 'sap',
  ORACLE: 'oracle',
  NETSUITE: 'netsuite',
  DYNAMICS: 'dynamics',
  SAGE: 'sage',
  ODOO: 'odoo',
  CUSTOM: 'custom',
} as const;

export type ErpProvider = typeof ErpProviders[keyof typeof ErpProviders];

// ============================================
// Media Asset Types
// ============================================

export const MediaAssetTypes = {
  IMAGE: 'image',
  VIDEO: 'video',
  AUDIO: 'audio',
  DOCUMENT: 'document',
  TEMPLATE: 'template',
  OTHER: 'other',
} as const;

export type MediaAssetType = typeof MediaAssetTypes[keyof typeof MediaAssetTypes];

// ============================================
// Ticket Status
// ============================================

export const TicketStatuses = {
  OPEN: 'open',
  PENDING: 'pending',
  RESOLVED: 'resolved',
  CLOSED: 'closed',
  ESCALATED: 'escalated',
} as const;

export type TicketStatus = typeof TicketStatuses[keyof typeof TicketStatuses];

// ============================================
// Ticket Priority
// ============================================

export const TicketPriorities = {
  LOW: 'low',
  MEDIUM: 'medium',
  HIGH: 'high',
  URGENT: 'urgent',
} as const;

export type TicketPriority = typeof TicketPriorities[keyof typeof TicketPriorities];

// ============================================
// Subscription Status
// ============================================

export const SubscriptionStatuses = {
  ACTIVE: 'active',
  CANCELLED: 'cancelled',
  PAST_DUE: 'past_due',
  TRIALING: 'trialing',
} as const;

export type SubscriptionStatus = typeof SubscriptionStatuses[keyof typeof SubscriptionStatuses];

// ============================================
// Billing Cycle
// ============================================

export const BillingCycles = {
  MONTHLY: 'monthly',
  YEARLY: 'yearly',
} as const;

export type BillingCycle = typeof BillingCycles[keyof typeof BillingCycles];

// ============================================
// Security Event Severity
// ============================================

export const SecurityEventSeverities = {
  INFO: 'info',
  WARNING: 'warning',
  CRITICAL: 'critical',
} as const;

export type SecurityEventSeverity = typeof SecurityEventSeverities[keyof typeof SecurityEventSeverities];

// ============================================
// Audit Actions
// ============================================

export const AuditActions = {
  CREATE: 'create',
  READ: 'read',
  UPDATE: 'update',
  DELETE: 'delete',
  LOGIN: 'login',
  LOGOUT: 'logout',
  EXPORT: 'export',
  IMPORT: 'import',
  SYNC: 'sync',
  OTHER: 'other',
} as const;

export type AuditAction = typeof AuditActions[keyof typeof AuditActions];

// ============================================
// Notification Types
// ============================================

export const NotificationTypes = {
  INFO: 'info',
  SUCCESS: 'success',
  WARNING: 'warning',
  ERROR: 'error',
} as const;

export type NotificationType = typeof NotificationTypes[keyof typeof NotificationTypes];

// ============================================
// Notification Channels
// ============================================

export const NotificationChannels = {
  IN_APP: 'in_app',
  EMAIL: 'email',
  PUSH: 'push',
  SMS: 'sms',
} as const;

export type NotificationChannel = typeof NotificationChannels[keyof typeof NotificationChannels];

// ============================================
// Health Status
// ============================================

export const HealthStatuses = {
  HEALTHY: 'healthy',
  DEGRADED: 'degraded',
  UNHEALTHY: 'unhealthy',
} as const;

export type HealthStatus = typeof HealthStatuses[keyof typeof HealthStatuses];

// ============================================
// Export Formats
// ============================================

export const ExportFormats = {
  JSON: 'json',
  CSV: 'csv',
  XLSX: 'xlsx',
  PDF: 'pdf',
} as const;

export type ExportFormat = typeof ExportFormats[keyof typeof ExportFormats];

// ============================================
// API Statistics
// ============================================

export const APIStats = {
  totalModules: 16,
  totalEndpoints: 250,
  totalSchemas: 440,
  apiPrefix: '/api/v2',
  version: '2.0.0',
} as const;
