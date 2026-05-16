// ============================================
// AI Marketing Platform - Auto-generated TypeScript Types
// Source: OpenAPI 3.0 Schema
// Generated: Do NOT edit manually
// ============================================

// ============================================
// Primitive Type Aliases
// ============================================

export type UUID = string;
export type ISODateTime = string;
export type ISODate = string;
export type Email = string;
export type URLString = string;

// ============================================
// Authentication Types
// ============================================

export interface JWTPayload {
  sub: string; // User ID
  email: string;
  role: string;
  company_id?: string | null; // Tenant ID
  branch_id?: string | null;
  exp?: ISODateTime; // Expiration
  iat?: ISODateTime; // Issued at
  type: 'access' | 'refresh';
}

export interface UserRegister {
  email: Email;
  password: string; // min 8, max 128
  first_name: string;
  last_name: string;
  company_name?: string;
  phone?: string;
}

export interface UserLogin {
  email: Email;
  password: string;
}

export interface PasswordReset {
  email: Email;
}

export interface PasswordChange {
  current_password: string;
  new_password: string; // min 8, max 128
}

export interface TokenResponse {
  access_token: string;
  refresh_token: string;
  token_type: string;
  expires_in: number;
  refresh_expires_in: number;
}

export interface UserResponse {
  id: string;
  email: string;
  first_name?: string | null;
  last_name?: string | null;
  role: string;
  company_id?: string | null;
  branch_id?: string | null;
  is_active: boolean;
  created_at?: ISODateTime | null;
}

export interface LogoutRequest {
  refresh_token?: string | null;
}

// ============================================
// Company Types
// ============================================

export interface CompanyBase {
  name: string;
  slug: string;
  description?: string | null;
  industry?: string | null;
  website?: string | null;
  timezone: string;
  locale: string;
}

export interface CompanyCreate extends CompanyBase {}

export interface CompanyUpdate {
  name?: string;
  description?: string | null;
  industry?: string | null;
  website?: string | null;
  timezone?: string;
  locale?: string;
}

export interface CompanyResponse extends CompanyBase {
  id: string;
  created_at: ISODateTime;
  updated_at: ISODateTime;
}

export interface CompanyListResponse {
  items: CompanyResponse[];
  total: number;
  page: number;
  page_size: number;
}

// ============================================
// Branch Types
// ============================================

export interface BranchBase {
  name: string;
  code: string;
  address?: string | null;
  city?: string | null;
  country?: string | null;
  phone?: string | null;
  email?: Email | null;
  manager_name?: string | null;
  latitude?: number | null;
  longitude?: number | null;
}

export interface BranchCreate extends BranchBase {}

export interface BranchUpdate {
  name?: string;
  code?: string;
  address?: string | null;
  city?: string | null;
  country?: string | null;
  phone?: string | null;
  email?: Email | null;
  manager_name?: string | null;
}

export interface BranchResponse extends BranchBase {
  id: string;
  company_id: string;
  created_at: ISODateTime;
  updated_at: ISODateTime;
}

export interface BranchListResponse {
  items: BranchResponse[];
  total: number;
  page: number;
  page_size: number;
}

export interface BranchConfigBase {
  key: string;
  value: string;
  description?: string | null;
}

export interface BranchConfigCreate extends BranchConfigBase {}

export interface BranchConfigUpdate {
  value?: string;
  description?: string | null;
}

export interface BranchConfigResponse extends BranchConfigBase {
  id: string;
  branch_id: string;
  created_at: ISODateTime;
}

// ============================================
// Billing Types
// ============================================

export interface PlanBase {
  name: string;
  code: string;
  description?: string | null;
  price_monthly: number;
  price_yearly: number;
  currency: string;
  features: Record<string, unknown>;
  limits: Record<string, unknown>;
}

export interface PlanCreate extends PlanBase {}

export interface PlanUpdate {
  name?: string;
  description?: string | null;
  price_monthly?: number;
  price_yearly?: number;
  features?: Record<string, unknown>;
  limits?: Record<string, unknown>;
}

export interface PlanResponse extends PlanBase {
  id: string;
  is_active: boolean;
  created_at: ISODateTime;
}

export interface PlanListResponse {
  items: PlanResponse[];
  total: number;
}

export interface SubscriptionBase {
  plan_id: string;
  billing_cycle: 'monthly' | 'yearly';
}

export interface SubscriptionResponse {
  id: string;
  company_id: string;
  plan_id: string;
  plan_name: string;
  status: 'active' | 'cancelled' | 'past_due' | 'trialing';
  billing_cycle: string;
  current_period_start: ISODateTime;
  current_period_end: ISODateTime;
  cancel_at_period_end: boolean;
  created_at: ISODateTime;
}

export interface SubscribeRequest {
  plan_id: string;
  billing_cycle: 'monthly' | 'yearly';
  payment_method_id?: string;
}

export interface SubscriptionUpdate {
  billing_cycle?: 'monthly' | 'yearly';
}

export interface SubscriptionCancelRequest {
  reason?: string | null;
  immediate?: boolean;
}

export interface UsageRecordBase {
  company_id: string;
  feature_code: string;
  quantity: number;
  unit: string;
  metadata?: Record<string, unknown> | null;
}

export interface UsageRecordResponse extends UsageRecordBase {
  id: string;
  recorded_at: ISODateTime;
}

export interface UsageSummaryResponse {
  company_id: string;
  period_start: ISODateTime;
  period_end: ISODateTime;
  usages: UsageRecordResponse[];
  total_cost: number;
  currency: string;
}

export interface QuotaResponse {
  id: string;
  company_id: string;
  feature_code: string;
  limit: number;
  used: number;
  reset_date: ISODateTime;
}

export interface QuotaCheckResponse {
  feature_code: string;
  allowed: boolean;
  limit: number;
  used: number;
  remaining: number;
}

export interface InvoiceLineItem {
  description: string;
  quantity: number;
  unit_price: number;
  total: number;
}

export interface InvoiceResponse {
  id: string;
  company_id: string;
  invoice_number: string;
  status: 'draft' | 'open' | 'paid' | 'void' | 'uncollectible';
  amount_due: number;
  amount_paid: number;
  currency: string;
  line_items: InvoiceLineItem[];
  period_start: ISODateTime;
  period_end: ISODateTime;
  due_date: ISODateTime;
  created_at: ISODateTime;
}

export interface InvoiceListResponse {
  items: InvoiceResponse[];
  total: number;
  page: number;
  page_size: number;
}

export interface BillingStatsResponse {
  total_revenue: number;
  total_customers: number;
  active_subscriptions: number;
  churn_rate: number;
  mrr: number;
  arr: number;
}

export interface CompanyBillingSummary {
  company_id: string;
  subscription_status: string;
  current_plan: string;
  mrr: number;
  total_invoices: number;
  total_paid: number;
  currency: string;
}


// ============================================
// Dashboard Types
// ============================================

export interface DashboardStatsData {
  total_branches: number;
  total_campaigns: number;
  total_leads: number;
  conversion_rate: number;
  revenue_this_month: number;
  active_campaigns: number;
  avg_cost_per_lead: number;
  total_appointments: number;
}

export interface DashboardStatsResponse {
  data: DashboardStatsData;
  period: string;
  generated_at: ISODateTime;
}

export interface DashboardChartData {
  labels: string[];
  datasets: Array<{
    label: string;
    data: number[];
    color?: string;
  }>;
}

export interface DashboardChartResponse {
  chart: DashboardChartData;
  chart_type: string;
  period: string;
}

export interface DashboardAlertItem {
  id: string;
  severity: 'info' | 'warning' | 'critical';
  title: string;
  message: string;
  source: string;
  created_at: ISODateTime;
  acknowledged: boolean;
}

export interface DashboardAlertsResponse {
  alerts: DashboardAlertItem[];
  total: number;
  unacknowledged: number;
}

export interface ExecutiveSummaryData {
  revenue_summary: {
    current_month: number;
    previous_month: number;
    change_percent: number;
  };
  lead_summary: {
    current_month: number;
    previous_month: number;
    change_percent: number;
  };
  top_performing_branches: Array<{
    branch_id: string;
    branch_name: string;
    revenue: number;
    leads: number;
  }>;
  insights: string[];
}

export interface ExecutiveSummaryResponse {
  data: ExecutiveSummaryData;
  period: string;
}

export interface BranchDashboardData {
  branch_id: string;
  branch_name: string;
  stats: DashboardStatsData;
  recent_campaigns: Array<{
    id: string;
    name: string;
    status: string;
    performance_score: number;
  }>;
  recent_leads: Array<{
    id: string;
    name: string;
    source: string;
    status: string;
    created_at: ISODateTime;
  }>;
}

export interface BranchDashboardResponse {
  data: BranchDashboardData;
  generated_at: ISODateTime;
}

// ============================================
// Analytics Types
// ============================================

export interface AnalyticsOverviewData {
  total_views: number;
  total_clicks: number;
  total_conversions: number;
  total_spend: number;
  avg_cpc: number;
  avg_ctr: number;
  avg_conversion_rate: number;
  roas: number;
}

export interface AnalyticsOverviewResponse {
  data: AnalyticsOverviewData;
  period: string;
  comparison_period?: string | null;
  change_percent: Record<string, number>;
}

export interface TrafficData {
  source: string;
  medium: string;
  campaign?: string | null;
  sessions: number;
  users: number;
  bounce_rate: number;
  avg_session_duration: number;
  conversions: number;
}

export interface TrafficResponse {
  data: TrafficData[];
  total_sessions: number;
  total_users: number;
  period: string;
}

export interface AudienceData {
  age_range: string;
  gender: string;
  location: string;
  interests: string[];
  count: number;
  engagement_rate: number;
}

export interface AudienceResponse {
  data: AudienceData[];
  total_audience: number;
  period: string;
}

export interface KpiMetricsData {
  cpl: number; // cost per lead
  cpa: number; // cost per acquisition
  roas: number;
  ctr: number;
  conversion_rate: number;
  lead_to_customer_rate: number;
  avg_deal_size: number;
  customer_lifetime_value: number;
}

export interface KpiMetricsResponse {
  data: KpiMetricsData;
  period: string;
  benchmarks: Record<string, number>;
}

export interface BranchComparisonItem {
  branch_id: string;
  branch_name: string;
  revenue: number;
  leads: number;
  conversions: number;
  spend: number;
  roas: number;
  score: number;
}

export interface BranchComparisonResponse {
  data: BranchComparisonItem[];
  period: string;
  best_performing: string;
}

export interface ConversionAnalyticsResponse {
  total_conversions: number;
  conversion_rate: number;
  by_source: Record<string, number>;
  by_campaign: Record<string, number>;
  period: string;
}

export interface CampaignAnalyticsResponse {
  campaigns: Array<{
    campaign_id: string;
    campaign_name: string;
    impressions: number;
    clicks: number;
    conversions: number;
    spend: number;
    revenue: number;
    roas: number;
  }>;
  period: string;
}

export interface AIInsightsData {
  insights: Array<{
    type: string;
    title: string;
    description: string;
    confidence: number;
    actionable: boolean;
    suggested_action?: string | null;
  }>;
  generated_at: ISODateTime;
}

export interface AIInsightsResponse {
  data: AIInsightsData;
  period: string;
}

export interface GrowthMetricsData {
  current_period_revenue: number;
  previous_period_revenue: number;
  revenue_growth_percent: number;
  current_period_leads: number;
  previous_period_leads: number;
  lead_growth_percent: number;
  current_period_customers: number;
  previous_period_customers: number;
  customer_growth_percent: number;
}

export interface GrowthMetricsResponse {
  data: GrowthMetricsData;
  period: string;
  trend: 'up' | 'down' | 'stable';
}

// ============================================
// AI Types
// ============================================

export interface AIPromptCreate {
  name: string;
  description?: string | null;
  system_prompt: string;
  user_prompt_template: string;
  model: string;
  temperature?: number;
  max_tokens?: number;
  variables?: string[];
  tags?: string[];
}

export interface AIPromptUpdate {
  name?: string;
  description?: string | null;
  system_prompt?: string;
  user_prompt_template?: string;
  model?: string;
  temperature?: number;
  max_tokens?: number;
  variables?: string[];
  tags?: string[];
  is_active?: boolean;
}

export interface AIPromptResponse {
  id: string;
  name: string;
  description?: string | null;
  system_prompt: string;
  user_prompt_template: string;
  model: string;
  temperature: number;
  max_tokens: number;
  variables: string[];
  tags: string[];
  is_active: boolean;
  created_at: ISODateTime;
  updated_at: ISODateTime;
}

export interface AIPromptListResponse {
  items: AIPromptResponse[];
  total: number;
  page: number;
  page_size: number;
}

export interface AIGenerateRequest {
  prompt_id?: string | null;
  system_prompt?: string | null;
  user_prompt: string;
  model?: string;
  temperature?: number;
  max_tokens?: number;
  stream?: boolean;
  variables?: Record<string, string>;
}

export interface AIGenerateResponse {
  content: string;
  model: string;
  tokens_used: number;
  prompt_tokens: number;
  completion_tokens: number;
  finish_reason: string;
  generated_at: ISODateTime;
}

export interface AISuggestionCreate {
  context: string;
  prompt_id?: string | null;
  model?: string;
  max_suggestions?: number;
}

export interface AISuggestionFeedback {
  suggestion_id: string;
  rating: number; // 1-5
  comment?: string | null;
  applied: boolean;
}

export interface AISuggestionResponse {
  id: string;
  title: string;
  description: string;
  category: string;
  confidence: number;
  actionable: boolean;
  suggested_action?: string | null;
  metadata?: Record<string, unknown> | null;
  created_at: ISODateTime;
}

export interface AISuggestionListResponse {
  items: AISuggestionResponse[];
  total: number;
  page: number;
}

export interface AIRecommendationCreate {
  context: string;
  category?: string | null;
  limit?: number;
}

export interface AIRecommendationResponse {
  id: string;
  title: string;
  description: string;
  category: string;
  priority: 'low' | 'medium' | 'high' | 'critical';
  impact_score: number;
  effort_score: number;
  status: 'pending' | 'applied' | 'dismissed';
  metadata?: Record<string, unknown> | null;
  created_at: ISODateTime;
}

export interface AIRecommendationListResponse {
  items: AIRecommendationResponse[];
  total: number;
  page: number;
}

export interface AIConversationResponse {
  id: string;
  title: string;
  model: string;
  message_count: number;
  created_at: ISODateTime;
  updated_at: ISODateTime;
}

export interface AIConversationListResponse {
  items: AIConversationResponse[];
  total: number;
  page: number;
}

export interface AIConversationCreate {
  title?: string;
  model?: string;
}

export interface AIMessageResponse {
  id: string;
  conversation_id: string;
  role: 'system' | 'user' | 'assistant';
  content: string;
  tokens_used?: number;
  created_at: ISODateTime;
}

export interface AISendMessageRequest {
  content: string;
  stream?: boolean;
}

export interface AISendMessageResponse {
  message: AIMessageResponse;
  assistant_reply: AIMessageResponse;
  conversation_id: string;
}

export interface AIUsageResponse {
  company_id: string;
  date: ISODate;
  prompt_tokens: number;
  completion_tokens: number;
  total_tokens: number;
  request_count: number;
  estimated_cost: number;
  currency: string;
}

export interface AIUsageListResponse {
  items: AIUsageResponse[];
  total: number;
  page: number;
}

export interface AIUsageSummary {
  total_tokens: number;
  total_requests: number;
  total_cost: number;
  currency: string;
  period: string;
}

export interface AICacheResponse {
  key: string;
  hit: boolean;
  value?: string | null;
  ttl?: number;
}

export interface AICacheStats {
  total_keys: number;
  memory_usage_mb: number;
  hit_rate: number;
  miss_rate: number;
  avg_ttl_seconds: number;
}

export interface AIErrorResponse {
  error: string;
  error_code: string;
  detail?: string | null;
  retry_after?: number;
}


// ============================================
// Ads Intelligence Types
// ============================================

export type AdPlatform = 'google_ads' | 'meta_ads' | 'tiktok_ads' | 'linkedin_ads' | 'twitter_ads';

export interface AdPlatformCredentials {
  developer_token?: string;
  client_id?: string;
  client_secret?: string;
  refresh_token?: string;
  account_id?: string;
}

export interface AdPlatformBase {
  platform: AdPlatform;
  name: string;
  account_id: string;
  credentials: AdPlatformCredentials;
  timezone?: string;
  currency?: string;
}

export interface AdPlatformCreate extends AdPlatformBase {}

export interface AdPlatformUpdate {
  name?: string;
  credentials?: Partial<AdPlatformCredentials>;
  is_active?: boolean;
}

export interface AdPlatformResponse extends AdPlatformBase {
  id: string;
  company_id: string;
  status: 'active' | 'paused' | 'disconnected' | 'error';
  is_active: boolean;
  last_sync_at?: ISODateTime | null;
  created_at: ISODateTime;
}

export interface AdPlatformListResponse {
  items: AdPlatformResponse[];
  total: number;
  page: number;
  page_size: number;
}

export interface AdCampaignBase {
  name: string;
  platform_id: string;
  platform_campaign_id?: string | null;
  objective: string;
  status: 'active' | 'paused' | 'archived' | 'deleted';
  budget_amount: number;
  budget_type: 'daily' | 'lifetime';
  start_date: ISODate;
  end_date?: ISODate | null;
  targeting?: Record<string, unknown> | null;
}

export interface AdCampaignCreate extends AdCampaignBase {}

export interface AdCampaignUpdate {
  name?: string;
  objective?: string;
  status?: 'active' | 'paused' | 'archived';
  budget_amount?: number;
  budget_type?: 'daily' | 'lifetime';
  start_date?: ISODate;
  end_date?: ISODate | null;
  targeting?: Record<string, unknown> | null;
}

export interface AdCampaignResponse extends AdCampaignBase {
  id: string;
  company_id: string;
  created_at: ISODateTime;
  updated_at: ISODateTime;
}

export interface AdCampaignListResponse {
  items: AdCampaignResponse[];
  total: number;
  page: number;
  page_size: number;
}

export interface AdCampaignMetricsResponse {
  campaign_id: string;
  impressions: number;
  clicks: number;
  conversions: number;
  spend: number;
  revenue: number;
  roas: number;
  cpc: number;
  ctr: number;
  conversion_rate: number;
  cpa: number;
  period: string;
}

export interface AdCreativeBase {
  campaign_id: string;
  name: string;
  type: 'image' | 'video' | 'carousel' | 'collection' | 'text';
  platform_creative_id?: string | null;
  title?: string | null;
  description?: string | null;
  call_to_action?: string | null;
  image_url?: string | null;
  video_url?: string | null;
  landing_page_url?: string | null;
}

export interface AdCreativeCreate extends AdCreativeBase {}

export interface AdCreativeUpdate {
  name?: string;
  title?: string | null;
  description?: string | null;
  call_to_action?: string | null;
  image_url?: string | null;
  video_url?: string | null;
  landing_page_url?: string | null;
}

export interface AdCreativeResponse extends AdCreativeBase {
  id: string;
  company_id: string;
  created_at: ISODateTime;
  updated_at: ISODateTime;
}

export interface AdCreativeListResponse {
  items: AdCreativeResponse[];
  total: number;
  page: number;
  page_size: number;
}

export interface AdAudienceBase {
  name: string;
  description?: string | null;
  platform_id: string;
  platform_audience_id?: string | null;
  audience_type: 'custom' | 'lookalike' | 'saved' | 'retargeting';
  criteria: Record<string, unknown>;
  estimated_size?: number | null;
}

export interface AdAudienceCreate extends AdAudienceBase {}

export interface AdAudienceUpdate {
  name?: string;
  description?: string | null;
  criteria?: Record<string, unknown>;
  is_active?: boolean;
}

export interface AdAudienceResponse extends AdAudienceBase {
  id: string;
  company_id: string;
  is_active: boolean;
  created_at: ISODateTime;
}

export interface AdAudienceListResponse {
  items: AdAudienceResponse[];
  total: number;
  page: number;
  page_size: number;
}

export interface AdMetricBase {
  platform_id: string;
  campaign_id?: string | null;
  creative_id?: string | null;
  metric_date: ISODate;
  impressions: number;
  clicks: number;
  conversions: number;
  spend: number;
  revenue: number;
  reach: number;
  frequency: number;
  engagement: number;
  video_views?: number | null;
  video_p25?: number | null;
  video_p50?: number | null;
  video_p75?: number | null;
  video_p100?: number | null;
}

export interface AdMetricResponse extends AdMetricBase {
  id: string;
  company_id: string;
  created_at: ISODateTime;
}

export interface AdMetricListResponse {
  items: AdMetricResponse[];
  total: number;
  page: number;
}

export interface AggregatedMetricsResponse {
  total_impressions: number;
  total_clicks: number;
  total_conversions: number;
  total_spend: number;
  total_revenue: number;
  roas: number;
  cpc: number;
  ctr: number;
  conversion_rate: number;
  cpa: number;
  period: string;
  breakdown_by_platform: Record<string, Record<string, number>>;
}

export interface PerformanceDashboardResponse {
  summary: AggregatedMetricsResponse;
  top_campaigns: Array<{
    campaign_id: string;
    campaign_name: string;
    impressions: number;
    clicks: number;
    conversions: number;
    spend: number;
    revenue: number;
    roas: number;
  }>;
  top_creatives: Array<{
    creative_id: string;
    creative_name: string;
    impressions: number;
    clicks: number;
    conversions: number;
  }>;
  daily_trend: Array<{
    date: ISODate;
    impressions: number;
    clicks: number;
    conversions: number;
    spend: number;
  }>;
  period: string;
}

export interface ROASAnalysisResponse {
  overall_roas: number;
  roas_by_campaign: Array<{
    campaign_id: string;
    campaign_name: string;
    roas: number;
    revenue: number;
    spend: number;
  }>;
  roas_by_platform: Record<string, number>;
  roas_trend: Array<{
    date: ISODate;
    roas: number;
  }>;
  recommendations: string[];
  period: string;
}

export interface CPAAnalysisResponse {
  overall_cpa: number;
  cpa_by_campaign: Array<{
    campaign_id: string;
    campaign_name: string;
    cpa: number;
    conversions: number;
    spend: number;
  }>;
  cpa_by_platform: Record<string, number>;
  cpa_trend: Array<{
    date: ISODate;
    cpa: number;
  }>;
  recommendations: string[];
  period: string;
}

export interface CreativeFatigueResponse {
  creative_id: string;
  fatigue_score: number;
  fatigue_level: 'low' | 'medium' | 'high' | 'critical';
  days_running: number;
  impressions_change_percent: number;
  ctr_change_percent: number;
  frequency: number;
  recommendation: string;
}

export interface AudienceOverlapResponse {
  audience_a_id: string;
  audience_b_id: string;
  overlap_percent: number;
  overlap_count: number;
  recommendation: string;
}

export interface AdBudgetRecommendationBase {
  campaign_id: string;
  current_budget: number;
  recommended_budget: number;
  budget_change_percent: number;
  confidence: number;
  reasoning: string;
}

export interface AdBudgetRecommendationResponse extends AdBudgetRecommendationBase {
  id: string;
  company_id: string;
  status: 'pending' | 'applied' | 'dismissed';
  created_at: ISODateTime;
}

export interface AdBudgetRecommendationListResponse {
  items: AdBudgetRecommendationResponse[];
  total: number;
  page: number;
}

export interface LocalRecommendationsResponse {
  recommendations: Array<{
    id: string;
    title: string;
    description: string;
    category: string;
    priority: 'low' | 'medium' | 'high';
    estimated_impact: number;
    action_items: string[];
  }>;
  period: string;
}

export interface SyncRequest {
  start_date?: ISODate | null;
  end_date?: ISODate | null;
  sync_type?: 'full' | 'incremental';
  entity_types?: string[];
}

export interface SyncResponse {
  sync_id: string;
  status: 'queued' | 'running' | 'completed' | 'failed';
  platform: AdPlatform;
  started_at?: ISODateTime | null;
  completed_at?: ISODateTime | null;
  records_synced: number;
  errors: string[];
}

export interface ABTestResultResponse {
  test_id: string;
  control_id: string;
  variant_id: string;
  control_name: string;
  variant_name: string;
  confidence_level: number;
  is_statistically_significant: boolean;
  winner_id: string;
  metrics_comparison: Record<string, {
    control_value: number;
    variant_value: number;
    lift_percent: number;
  }>;
}

export interface DateRangeFilter {
  start_date: ISODate;
  end_date: ISODate;
}

// ============================================
// Social Media Types
// ============================================

export type SocialPlatform = 'facebook' | 'instagram' | 'twitter' | 'linkedin' | 'tiktok' | 'youtube' | 'pinterest';

export interface SocialAccountBase {
  platform: SocialPlatform;
  account_name: string;
  platform_account_id: string;
  account_type: 'business' | 'creator' | 'personal';
  page_id?: string | null;
  profile_url?: string | null;
  follower_count?: number;
}

export interface SocialAccountCreate extends SocialAccountBase {}

export interface SocialAccountResponse extends SocialAccountBase {
  id: string;
  company_id: string;
  status: 'active' | 'disconnected' | 'error';
  last_sync_at?: ISODateTime | null;
  created_at: ISODateTime;
}

export interface SocialPostBase {
  account_id: string;
  content: string;
  media_urls?: string[];
  post_type: 'text' | 'image' | 'video' | 'carousel' | 'reel' | 'story';
  scheduled_at?: ISODateTime | null;
  platforms?: SocialPlatform[];
}

export interface SocialPostCreate extends SocialPostBase {}

export interface SocialPostResponse extends SocialPostBase {
  id: string;
  company_id: string;
  platform_post_ids: Record<string, string>;
  status: 'draft' | 'scheduled' | 'published' | 'failed';
  published_at?: ISODateTime | null;
  metrics?: {
    impressions: number;
    reach: number;
    engagement: number;
    likes: number;
    comments: number;
    shares: number;
  } | null;
  created_at: ISODateTime;
  updated_at: ISODateTime;
}

export interface SocialPostListResponse {
  items: SocialPostResponse[];
  total: number;
  page: number;
  page_size: number;
}

export interface SocialPostUpdate {
  content?: string;
  media_urls?: string[];
  scheduled_at?: ISODateTime | null;
}

export interface SocialCompetitorBase {
  platform: SocialPlatform;
  competitor_name: string;
  platform_handle: string;
  profile_url?: string | null;
  notes?: string | null;
}

export interface SocialCompetitorCreate extends SocialCompetitorBase {}

export interface SocialCompetitorResponse extends SocialCompetitorBase {
  id: string;
  company_id: string;
  follower_count?: number | null;
  post_count?: number | null;
  avg_engagement_rate?: number | null;
  last_analyzed_at?: ISODateTime | null;
  created_at: ISODateTime;
}

export interface SocialAnalyticsResponse {
  period: string;
  accounts: Array<{
    account_id: string;
    platform: SocialPlatform;
    followers: number;
    followers_change: number;
    posts: number;
    engagement_rate: number;
    impressions: number;
    reach: number;
  }>;
  top_posts: Array<{
    post_id: string;
    content: string;
    platform: SocialPlatform;
    likes: number;
    comments: number;
    shares: number;
    engagement_rate: number;
  }>;
  competitor_comparison?: Array<{
    competitor_id: string;
    competitor_name: string;
    follower_gap: number;
    engagement_rate_diff: number;
  }> | null;
}

export interface SocialScheduleResponse {
  id: string;
  post_id: string;
  account_id: string;
  scheduled_at: ISODateTime;
  status: 'pending' | 'published' | 'failed';
  published_at?: ISODateTime | null;
  error_message?: string | null;
}

export interface SocialEngagementResponse {
  id: string;
  post_id: string;
  account_id: string;
  platform: SocialPlatform;
  engagement_type: 'like' | 'comment' | 'share' | 'save' | 'click';
  count: number;
  date: ISODate;
}

// ============================================
// Media Types
// ============================================

export type MediaAssetType = 'image' | 'video' | 'audio' | 'document' | 'template' | 'other';
export type MediaAssetStatus = 'uploading' | 'processing' | 'ready' | 'error' | 'archived';

export interface MediaAssetBase {
  title: string;
  description?: string | null;
  type: MediaAssetType;
  tags?: string[];
  folder?: string | null;
  metadata?: Record<string, unknown> | null;
}

export interface MediaAssetCreate extends MediaAssetBase {}

export interface MediaAssetUpdate {
  title?: string;
  description?: string | null;
  tags?: string[];
  folder?: string | null;
  metadata?: Record<string, unknown> | null;
}

export interface MediaAssetResponse extends MediaAssetBase {
  id: string;
  company_id: string;
  original_url: string;
  thumbnail_url?: string | null;
  file_size: number;
  mime_type: string;
  width?: number | null;
  height?: number | null;
  duration?: number | null;
  status: MediaAssetStatus;
  created_at: ISODateTime;
  updated_at: ISODateTime;
}

export interface MediaAssetListItem {
  id: string;
  title: string;
  type: MediaAssetType;
  thumbnail_url?: string | null;
  file_size: number;
  status: MediaAssetStatus;
  created_at: ISODateTime;
}

export interface MediaAssetListResponse {
  items: MediaAssetListItem[];
  total: number;
  page: number;
  page_size: number;
}

export interface MediaAssetFilter {
  type?: MediaAssetType | null;
  status?: MediaAssetStatus | null;
  tags?: string[];
  folder?: string | null;
  search?: string | null;
}

export interface MediaCollectionBase {
  name: string;
  description?: string | null;
  folder?: string | null;
}

export interface MediaCollectionCreate extends MediaCollectionBase {}

export interface MediaCollectionUpdate {
  name?: string;
  description?: string | null;
  folder?: string | null;
}

export interface MediaCollectionResponse extends MediaCollectionBase {
  id: string;
  company_id: string;
  asset_count: number;
  assets: MediaAssetListItem[];
  created_at: ISODateTime;
  updated_at: ISODateTime;
}

export interface MediaCollectionListResponse {
  items: MediaCollectionResponse[];
  total: number;
  page: number;
}

export interface MediaCollectionItemAdd {
  asset_ids: string[];
}

export interface MediaTagCreate {
  name: string;
  color?: string | null;
}

export interface MediaTagResponse {
  id: string;
  company_id: string;
  name: string;
  color?: string | null;
  asset_count: number;
  created_at: ISODateTime;
}

export interface MediaTagUpdate {
  name?: string;
  color?: string | null;
}

export interface MediaStatsResponse {
  total_assets: number;
  total_size_bytes: number;
  by_type: Record<MediaAssetType, number>;
  by_status: Record<MediaAssetStatus, number>;
  recent_uploads: number;
  storage_used_gb: number;
}

export interface UploadResponse {
  asset_id: string;
  status: MediaAssetStatus;
  url: string;
  thumbnail_url?: string | null;
}

export interface UploadInitiateRequest {
  filename: string;
  content_type: string;
  file_size: number;
  title?: string;
  type?: MediaAssetType;
}

export interface UploadCompleteRequest {
  upload_id: string;
  parts?: Array<{ etag: string; part_number: number }>;
}

export interface SignedUrlResponse {
  url: string;
  expires_at: ISODateTime;
  method: string;
}

export interface PresignedUploadUrlResponse {
  upload_url: string;
  fields?: Record<string, string>;
  asset_id: string;
  expires_at: ISODateTime;
}

export interface AIAnalysisRequest {
  analysis_type: 'objects' | 'faces' | 'text' | 'colors' | 'tags' | 'quality';
  confidence_threshold?: number;
}

export interface AIAnalysisResult {
  analysis_type: string;
  results: Array<{
    label: string;
    confidence: number;
    bbox?: [number, number, number, number];
    metadata?: Record<string, unknown>;
  }>;
  processed_at: ISODateTime;
}

export interface AIAnalysisTypesResponse {
  available_types: Array<{
    type: string;
    description: string;
    supported_formats: string[];
  }>;
}

export interface JobStatusResponse {
  job_id: string;
  status: 'queued' | 'processing' | 'completed' | 'failed';
  progress_percent: number;
  result_url?: string | null;
  error_message?: string | null;
  created_at: ISODateTime;
  completed_at?: ISODateTime | null;
}

export interface BulkTagRequest {
  asset_ids: string[];
  tags: string[];
  operation: 'add' | 'remove' | 'set';
}

export interface BulkDeleteRequest {
  asset_ids: string[];
}

export interface BulkOperationResponse {
  processed: number;
  succeeded: number;
  failed: number;
  errors: Array<{ asset_id: string; error: string }>;
}

export interface TagAddRequest {
  tags: string[];
}


// ============================================
// ERP Integration Types
// ============================================

export type ERPProvider = 'sap' | 'oracle' | 'netsuite' | 'dynamics' | 'sage' | 'odoo' | 'custom';

export interface ERPConnectionBase {
  name: string;
  provider: ERPProvider;
  base_url: string;
  api_version?: string | null;
  auth_type: 'basic' | 'oauth2' | 'api_key' | 'token';
  config: Record<string, string>;
  sync_interval_minutes?: number;
  is_active?: boolean;
}

export interface ERPConnectionCreate extends ERPConnectionBase {}

export interface ERPConnectionUpdate {
  name?: string;
  base_url?: string;
  api_version?: string | null;
  config?: Record<string, string>;
  sync_interval_minutes?: number;
  is_active?: boolean;
}

export interface ERPConnectionResponse extends ERPConnectionBase {
  id: string;
  company_id: string;
  status: 'active' | 'inactive' | 'error' | 'syncing';
  last_sync_at?: ISODateTime | null;
  last_error?: string | null;
  created_at: ISODateTime;
  updated_at: ISODateTime;
}

export interface FieldMappingBase {
  connection_id: string;
  source_entity: string;
  source_field: string;
  target_entity: string;
  target_field: string;
  transform?: string | null;
  is_key?: boolean;
  is_required?: boolean;
}

export interface FieldMappingCreate extends FieldMappingBase {}

export interface FieldMappingUpdate {
  source_field?: string;
  target_field?: string;
  transform?: string | null;
  is_key?: boolean;
  is_required?: boolean;
  is_active?: boolean;
}

export interface FieldMappingResponse extends FieldMappingBase {
  id: string;
  company_id: string;
  is_active: boolean;
  created_at: ISODateTime;
}

export interface SyncStatusResponse {
  job_id: string;
  status: 'queued' | 'running' | 'completed' | 'failed' | 'cancelled';
  entity_type: string;
  records_total: number;
  records_processed: number;
  records_failed: number;
  started_at: ISODateTime;
  completed_at?: ISODateTime | null;
  error_message?: string | null;
}

export interface SyncLogResponse {
  id: string;
  job_id: string;
  level: 'info' | 'warning' | 'error';
  message: string;
  entity_id?: string | null;
  created_at: ISODateTime;
}

export interface SyncLogListResponse {
  items: SyncLogResponse[];
  total: number;
  page: number;
}

export interface SyncStatsResponse {
  total_syncs: number;
  successful_syncs: number;
  failed_syncs: number;
  total_records_synced: number;
  avg_sync_duration_seconds: number;
  last_sync_at?: ISODateTime | null;
  by_entity: Record<string, { synced: number; failed: number }>;
}

export interface SyncHealthCheckResponse {
  connection_id: string;
  connection_name: string;
  provider: ERPProvider;
  status: 'healthy' | 'degraded' | 'unhealthy';
  last_sync_status: string;
  api_latency_ms: number;
  error_rate_percent: number;
  recommendations: string[];
}

export interface SyncTriggerRequest {
  entity_types?: string[];
  full_sync?: boolean;
}

export interface WebhookResponse {
  received: boolean;
  event_id: string;
  processed_at: ISODateTime;
}

export interface ERPWebhookPayload {
  event_type: string;
  provider: ERPProvider;
  timestamp: ISODateTime;
  data: Record<string, unknown>;
  signature?: string | null;
}

export interface SuccessResponse {
  success: boolean;
  message: string;
  id?: string | null;
}

// ============================================
// Event Bus Types
// ============================================

export interface EventDefinitionBase {
  name: string;
  description?: string | null;
  event_schema?: Record<string, unknown> | null;
  category?: string | null;
  tags?: string[];
}

export interface EventDefinitionCreate extends EventDefinitionBase {}

export interface EventDefinitionUpdate {
  description?: string | null;
  event_schema?: Record<string, unknown> | null;
  category?: string | null;
  tags?: string[];
  is_active?: boolean;
}

export interface EventDefinitionResponse extends EventDefinitionBase {
  id: string;
  version: number;
  is_active: boolean;
  created_at: ISODateTime;
  updated_at: ISODateTime;
}

export interface EventDefinitionListResponse {
  items: EventDefinitionResponse[];
  total: number;
  page: number;
}

export interface EventSubscriptionBase {
  event_name: string;
  target_url?: string | null;
  target_queue?: string | null;
  target_function?: string | null;
  filter_expression?: string | null;
  retry_policy?: {
    max_retries: number;
    backoff_seconds: number;
  } | null;
}

export interface EventSubscriptionCreate extends EventSubscriptionBase {}

export interface EventSubscriptionUpdate {
  target_url?: string | null;
  target_queue?: string | null;
  target_function?: string | null;
  filter_expression?: string | null;
  retry_policy?: {
    max_retries: number;
    backoff_seconds: number;
  } | null;
  is_active?: boolean;
}

export interface EventSubscriptionResponse extends EventSubscriptionBase {
  id: string;
  company_id: string;
  is_active: boolean;
  created_at: ISODateTime;
}

export interface EventSubscriptionListResponse {
  items: EventSubscriptionResponse[];
  total: number;
  page: number;
}

export interface EventLogResponse {
  id: string;
  event_name: string;
  payload: Record<string, unknown>;
  status: 'pending' | 'processing' | 'completed' | 'failed' | 'retrying';
  attempts: number;
  error_message?: string | null;
  processed_at?: ISODateTime | null;
  created_at: ISODateTime;
}

export interface EventLogListResponse {
  items: EventLogResponse[];
  total: number;
  page: number;
}

export interface EventRetryResponse {
  log_id: string;
  status: string;
  next_attempt_at?: ISODateTime | null;
}

export interface DeadLetterEventResponse {
  id: string;
  original_event_id: string;
  event_name: string;
  payload: Record<string, unknown>;
  error_reason: string;
  error_message?: string | null;
  created_at: ISODateTime;
  failed_at: ISODateTime;
}

export interface DeadLetterEventListResponse {
  items: DeadLetterEventResponse[];
  total: number;
  page: number;
}

export interface DeadLetterResolveRequest {
  resolution: 'retry' | 'discard' | 'manual';
  notes?: string | null;
}

export interface DeadLetterResolveResponse {
  id: string;
  status: string;
  resolved_at: ISODateTime;
}

export interface DeadLetterRetryResponse {
  dead_letter_id: string;
  new_event_id: string;
  status: string;
}

export interface AutomationRuleBase {
  name: string;
  description?: string | null;
  trigger_event: string;
  condition_expression: string;
  actions: Array<{
    type: string;
    config: Record<string, unknown>;
  }>;
  priority?: number;
}

export interface AutomationRuleCreate extends AutomationRuleBase {}

export interface AutomationRuleUpdate {
  name?: string;
  description?: string | null;
  trigger_event?: string;
  condition_expression?: string;
  actions?: Array<{
    type: string;
    config: Record<string, unknown>;
  }>;
  priority?: number;
  is_active?: boolean;
}

export interface AutomationRuleResponse extends AutomationRuleBase {
  id: string;
  company_id: string;
  is_active: boolean;
  execution_count: number;
  last_executed_at?: ISODateTime | null;
  created_at: ISODateTime;
}

export interface AutomationRuleListResponse {
  items: AutomationRuleResponse[];
  total: number;
  page: number;
}

export interface AutomationRuleToggleResponse {
  id: string;
  is_active: boolean;
  toggled_at: ISODateTime;
}

export interface AutomationExecutionResponse {
  id: string;
  rule_id: string;
  rule_name: string;
  trigger_event_id: string;
  status: 'success' | 'failed' | 'partial';
  executed_actions: number;
  failed_actions: number;
  started_at: ISODateTime;
  completed_at: ISODateTime;
}

export interface EventPublishRequest {
  event_name: string;
  payload: Record<string, unknown>;
  delay_seconds?: number;
}

export interface EventPublishResponse {
  event_id: string;
  event_name: string;
  status: string;
  published_at: ISODateTime;
}

export interface EventStatsResponse {
  total_events_today: number;
  total_events_this_week: number;
  events_by_type: Record<string, number>;
  failed_events: number;
  dead_letter_count: number;
  avg_processing_time_ms: number;
  period: string;
}

export interface EventRetryRequest {
  log_id: string;
  force?: boolean;
}

// ============================================
// Audit & Security Types
// ============================================

export type AuditAction = 'create' | 'read' | 'update' | 'delete' | 'login' | 'logout' | 'export' | 'import' | 'sync' | 'other';
export type SecurityEventSeverity = 'info' | 'warning' | 'critical';

export interface AuditLogBase {
  user_id?: string | null;
  company_id: string;
  action: AuditAction;
  entity_type: string;
  entity_id?: string | null;
  description: string;
  ip_address?: string | null;
  user_agent?: string | null;
  metadata?: Record<string, unknown> | null;
}

export interface AuditLogCreate extends AuditLogBase {}

export interface AuditLogResponse extends AuditLogBase {
  id: string;
  created_at: ISODateTime;
}

export interface AuditLogListResponse {
  items: AuditLogResponse[];
  total: number;
  page: number;
  page_size: number;
}

export interface AuditLogFilter {
  company_id?: string;
  user_id?: string | null;
  action?: AuditAction | null;
  entity_type?: string | null;
  start_date?: ISODateTime | null;
  end_date?: ISODateTime | null;
  search?: string | null;
}

export interface SecurityEventBase {
  event_type: string;
  severity: SecurityEventSeverity;
  description: string;
  source_ip?: string | null;
  user_id?: string | null;
  company_id: string;
  metadata?: Record<string, unknown> | null;
}

export interface SecurityEventCreate extends SecurityEventBase {}

export interface SecurityEventResponse extends SecurityEventBase {
  id: string;
  status: 'new' | 'investigating' | 'resolved' | 'false_positive';
  resolved_by?: string | null;
  resolved_at?: ISODateTime | null;
  resolution_notes?: string | null;
  created_at: ISODateTime;
}

export interface SecurityEventListResponse {
  items: SecurityEventResponse[];
  total: number;
  page: number;
}

export interface SecurityEventFilter {
  company_id?: string;
  event_type?: string | null;
  severity?: SecurityEventSeverity | null;
  status?: string | null;
  start_date?: ISODateTime | null;
  end_date?: ISODateTime | null;
}

export interface SecurityEventResolve {
  resolution_notes: string;
  status?: 'resolved' | 'false_positive';
}

export interface LoginAttemptBase {
  email: string;
  ip_address: string;
  user_agent?: string | null;
  success: boolean;
  failure_reason?: string | null;
  company_id?: string | null;
}

export interface LoginAttemptResponse extends LoginAttemptBase {
  id: string;
  created_at: ISODateTime;
}

export interface LoginAttemptListResponse {
  items: LoginAttemptResponse[];
  total: number;
  page: number;
}

export interface LoginAttemptFilter {
  company_id?: string | null;
  email?: string | null;
  ip_address?: string | null;
  success?: boolean | null;
  start_date?: ISODateTime | null;
  end_date?: ISODateTime | null;
}

export interface APIKeyBase {
  name: string;
  description?: string | null;
  permissions?: string[];
  expires_at?: ISODateTime | null;
}

export interface APIKeyCreate extends APIKeyBase {}

export interface APIKeyUpdate {
  name?: string;
  description?: string | null;
  permissions?: string[];
  is_active?: boolean;
}

export interface APIKeyResponse extends APIKeyBase {
  id: string;
  company_id: string;
  key_prefix: string;
  is_active: boolean;
  last_used_at?: ISODateTime | null;
  created_at: ISODateTime;
}

export interface APIKeyListResponse {
  items: APIKeyResponse[];
  total: number;
  page: number;
}

export interface APIKeyValidateRequest {
  api_key: string;
  required_permission?: string | null;
}

export interface APIKeyValidationResult {
  valid: boolean;
  key_id?: string | null;
  company_id?: string | null;
  name?: string | null;
  permissions?: string[];
  error?: string | null;
}

export interface DataAccessLogBase {
  user_id: string;
  company_id: string;
  data_type: string;
  data_id: string;
  access_type: string;
  purpose?: string | null;
}

export interface DataAccessLogCreate extends DataAccessLogBase {}

export interface DataAccessLogResponse extends DataAccessLogBase {
  id: string;
  created_at: ISODateTime;
}

export interface DataAccessLogListResponse {
  items: DataAccessLogResponse[];
  total: number;
  page: number;
}

export interface DataAccessLogFilter {
  company_id: string;
  user_id?: string | null;
  data_type?: string | null;
  start_date?: ISODateTime | null;
  end_date?: ISODateTime | null;
}

export interface AuditStatsResponse {
  total_events_today: number;
  total_events_this_week: number;
  events_by_action: Record<AuditAction, number>;
  security_events_today: number;
  failed_logins_today: number;
  active_api_keys: number;
  period: string;
}

export interface APIKeyWithPlainKey extends APIKeyResponse {
  plain_key: string; // Yalnizca olusturma sirasinda gosterilir
}

export type ExportFormat = 'json' | 'csv' | 'xlsx' | 'pdf';

// ============================================
// Support Types
// ============================================

export type TicketStatus = 'open' | 'pending' | 'resolved' | 'closed' | 'escalated';
export type TicketPriority = 'low' | 'medium' | 'high' | 'urgent';
export type TicketSource = 'web' | 'email' | 'chat' | 'phone' | 'social' | 'api';

export interface TicketBase {
  subject: string;
  description: string;
  priority?: TicketPriority;
  source?: TicketSource;
  category?: string | null;
  metadata?: Record<string, unknown> | null;
  requester_name: string;
  requester_email: Email;
  requester_phone?: string | null;
}

export interface TicketCreate extends TicketBase {}

export interface TicketUpdate {
  subject?: string;
  description?: string;
  priority?: TicketPriority;
  category?: string | null;
  status?: TicketStatus;
  assigned_to_id?: string | null;
}

export interface TicketResponse extends TicketBase {
  id: string;
  company_id: string;
  status: TicketStatus;
  assigned_to_id?: string | null;
  assigned_to_name?: string | null;
  resolution_time_minutes?: number | null;
  created_at: ISODateTime;
  updated_at: ISODateTime;
}

export interface TicketListResponse {
  items: TicketResponse[];
  total: number;
  page: number;
  page_size: number;
}

export interface TicketAssign {
  assigned_to_id: string;
  notes?: string | null;
}

export interface TicketClose {
  resolution_notes?: string | null;
  satisfaction_rating?: number | null;
}

export interface TicketEscalate {
  reason: string;
  escalated_to_id?: string | null;
  priority?: TicketPriority;
}

export interface MessageBase {
  ticket_id: string;
  content: string;
  sender_type: 'customer' | 'agent' | 'system' | 'ai';
  sender_id?: string | null;
  attachments?: string[];
  metadata?: Record<string, unknown> | null;
}

export interface MessageCreate extends MessageBase {}

export interface MessageResponse extends MessageBase {
  id: string;
  created_at: ISODateTime;
}

export interface MessageListResponse {
  items: MessageResponse[];
  total: number;
  page: number;
}

export interface ConversationReplyRequest {
  content: string;
  sender_type?: 'agent' | 'system';
  attachments?: string[];
}

export interface ConversationReplyResponse {
  message: MessageResponse;
  ai_suggestion?: string | null;
  sentiment?: string | null;
}

export interface TicketFilterParams {
  status?: TicketStatus | null;
  priority?: TicketPriority | null;
  category?: string | null;
  source?: TicketSource | null;
  assigned_to_id?: string | null;
  search?: string | null;
  start_date?: ISODateTime | null;
  end_date?: ISODateTime | null;
}

export interface SupportMacroBase {
  name: string;
  description?: string | null;
  shortcut?: string | null;
  content: string;
  variables?: string[];
  category?: string | null;
}

export interface SupportMacroCreate extends SupportMacroBase {}

export interface SupportMacroUpdate {
  name?: string;
  description?: string | null;
  shortcut?: string | null;
  content?: string;
  variables?: string[];
  category?: string | null;
  is_active?: boolean;
}

export interface SupportMacroResponse extends SupportMacroBase {
  id: string;
  company_id: string;
  is_active: boolean;
  created_at: ISODateTime;
}

export interface SupportMacroListResponse {
  items: SupportMacroResponse[];
  total: number;
  page: number;
}

export interface MacroExpandRequest {
  macro_id: string;
  variables?: Record<string, string>;
}

export interface MacroExpandResponse {
  expanded_content: string;
  macro_name: string;
}

export interface KnowledgeBaseArticleBase {
  title: string;
  content: string;
  category_id: string;
  tags?: string[];
  is_published?: boolean;
}

export interface KnowledgeBaseArticleCreate extends KnowledgeBaseArticleBase {}

export interface KnowledgeBaseArticleUpdate {
  title?: string;
  content?: string;
  category_id?: string;
  tags?: string[];
  is_published?: boolean;
}

export interface KnowledgeBaseArticleResponse extends KnowledgeBaseArticleBase {
  id: string;
  company_id: string;
  view_count: number;
  helpful_count: number;
  created_at: ISODateTime;
  updated_at: ISODateTime;
}

export interface KnowledgeBaseArticleListResponse {
  items: KnowledgeBaseArticleResponse[];
  total: number;
  page: number;
}

export interface KnowledgeBaseCategoryCreate {
  name: string;
  description?: string | null;
  parent_id?: string | null;
  order?: number;
}

export interface KnowledgeBaseCategoryResponse {
  id: string;
  company_id: string;
  name: string;
  description?: string | null;
  parent_id?: string | null;
  order: number;
  article_count: number;
  created_at: ISODateTime;
}

export interface KnowledgeBaseSearchRequest {
  query: string;
  category_id?: string | null;
  limit?: number;
}

export interface KnowledgeBaseSearchResponse {
  results: Array<{
    article_id: string;
    title: string;
    excerpt: string;
    category: string;
    relevance_score: number;
  }>;
  total: number;
}

export interface EscalationRuleBase {
  name: string;
  description?: string | null;
  condition_type: 'priority' | 'wait_time' | 'sentiment' | 'category' | 'custom';
  condition_config: Record<string, unknown>;
  action_type: 'assign' | 'notify' | 'create_ticket' | 'webhook';
  action_config: Record<string, unknown>;
}

export interface EscalationRuleCreate extends EscalationRuleBase {}

export interface EscalationRuleUpdate {
  name?: string;
  description?: string | null;
  condition_type?: string;
  condition_config?: Record<string, unknown>;
  action_type?: string;
  action_config?: Record<string, unknown>;
  is_active?: boolean;
  priority?: number;
}

export interface EscalationRuleResponse extends EscalationRuleBase {
  id: string;
  company_id: string;
  is_active: boolean;
  priority: number;
  trigger_count: number;
  created_at: ISODateTime;
}

export interface EscalationRuleListResponse {
  items: EscalationRuleResponse[];
  total: number;
  page: number;
}

export interface EscalationTriggerResult {
  triggered: boolean;
  rule_ids: string[];
  actions_taken: Array<{
    rule_id: string;
    action_type: string;
    result: string;
  }>;
}

export interface AIReplyRequest {
  ticket_id: string;
  context?: string | null;
  tone?: 'professional' | 'friendly' | 'empathetic' | 'technical';
  include_kb?: boolean;
}

export interface AIReplyResponse {
  reply: string;
  confidence: number;
  sources?: Array<{
    type: string;
    id: string;
    title: string;
  }>;
  suggested_tags?: string[];
}

export interface CategorizationRequest {
  text: string;
  categories?: string[];
}

export interface CategorizationResponse {
  category: string;
  confidence: number;
  all_scores: Record<string, number>;
}

export interface SentimentAnalysisRequest {
  text: string;
}

export interface SentimentAnalysisResponse {
  sentiment: 'positive' | 'negative' | 'neutral' | 'mixed';
  score: number; // -1 to 1
  emotions: Record<string, number>;
  urgency_level: 'low' | 'medium' | 'high';
}

export interface HumanTakeoverRequest {
  conversation_id: string;
  reason?: string | null;
  agent_id: string;
}

export interface HumanTakeoverResponse {
  conversation_id: string;
  status: string;
  agent_id: string;
  taken_over_at: ISODateTime;
}

export interface SupportAnalyticsSummary {
  total_tickets: number;
  open_tickets: number;
  avg_resolution_time_hours: number;
  first_response_time_avg_minutes: number;
  satisfaction_score_avg: number;
  tickets_by_status: Record<TicketStatus, number>;
  tickets_by_priority: Record<TicketPriority, number>;
  top_categories: Array<{ category: string; count: number }>;
  period: string;
}


// ============================================
// Notification Types
// ============================================

export type NotificationType = 'info' | 'success' | 'warning' | 'error';
export type NotificationChannel = 'in_app' | 'email' | 'push' | 'sms';

export interface NotificationBase {
  user_id: string;
  title: string;
  message: string;
  type: NotificationType;
  channels: NotificationChannel[];
  action_url?: string | null;
  metadata?: Record<string, unknown> | null;
}

export interface NotificationCreate extends NotificationBase {}

export interface NotificationResponse extends NotificationBase {
  id: string;
  company_id: string;
  is_read: boolean;
  read_at?: ISODateTime | null;
  created_at: ISODateTime;
}

export interface NotificationListResponse {
  items: NotificationResponse[];
  total: number;
  unread_count: number;
  page: number;
  page_size: number;
}

export interface NotificationPreference {
  user_id: string;
  channel: NotificationChannel;
  event_type: string;
  enabled: boolean;
  quiet_hours_start?: string | null;
  quiet_hours_end?: string | null;
}

// ============================================
// Health Types
// ============================================

export interface HealthStatus {
  status: 'healthy' | 'degraded' | 'unhealthy';
  version: string;
  timestamp: ISODateTime;
  uptime_seconds: number;
}

export interface DetailedHealthResponse {
  status: string;
  version: string;
  timestamp: ISODateTime;
  uptime_seconds: number;
  environment: string;
  services: Record<string, {
    status: 'healthy' | 'degraded' | 'unhealthy';
    response_time_ms: number;
    last_checked: ISODateTime;
    message?: string | null;
  }>;
}

export interface DBHealthResponse {
  database: string;
  status: string;
  response_time_ms: number;
  connection_pool: {
    size: number;
    available: number;
    used: number;
  };
}

export interface RedisHealthResponse {
  redis: string;
  status: string;
  response_time_ms: number;
  memory_usage_mb: number;
  connected_clients: number;
}

// ============================================
// Pagination & Common Types
// ============================================

export interface PaginatedResponse<T> {
  items: T[];
  total: number;
  page: number;
  page_size: number;
  total_pages: number;
  has_next: boolean;
  has_prev: boolean;
}

export interface PaginationParams {
  page?: number;
  page_size?: number;
  sort_by?: string | null;
  sort_order?: 'asc' | 'desc';
}

export interface SortParams {
  sort_by?: string;
  sort_order?: 'asc' | 'desc';
}

export interface DateRangeFilter {
  start_date: ISODate;
  end_date: ISODate;
}

export interface SuccessResponse {
  success: boolean;
  message: string;
  id?: string | null;
}

export interface ErrorDetail {
  loc: (string | number)[];
  msg: string;
  type: string;
}

export interface ValidationErrorResponse {
  detail: ErrorDetail[] | string;
  status_code: number;
  type?: string;
}

// ============================================
// API Endpoint Type Definitions
// ============================================

export type HttpMethod = 'GET' | 'POST' | 'PUT' | 'PATCH' | 'DELETE';

export interface ApiEndpointDefinition {
  method: HttpMethod;
  path: string;
  operationId: string;
  summary: string;
  tags: string[];
  hasRequestBody: boolean;
  hasResponseModel: boolean;
  responseModel?: string | null;
  statusCode?: number;
}

export type ApiEndpointGroup = Record<string, ApiEndpointDefinition>;

export interface ApiEndpoints {
  auth: ApiEndpointGroup;
  companies: ApiEndpointGroup;
  branches: ApiEndpointGroup;
  dashboard: ApiEndpointGroup;
  analytics: ApiEndpointGroup;
  notifications: ApiEndpointGroup;
  erp: ApiEndpointGroup;
  ai: ApiEndpointGroup;
  social: ApiEndpointGroup;
  media: ApiEndpointGroup;
  events: ApiEndpointGroup;
  billing: ApiEndpointGroup;
  audit: ApiEndpointGroup;
  health: ApiEndpointGroup;
  ads: ApiEndpointGroup;
  support: ApiEndpointGroup;
}

// ============================================
// API Client Types
// ============================================

export interface ApiClientConfig {
  baseURL: string;
  timeout?: number;
  headers?: Record<string, string>;
  withCredentials?: boolean;
}

export interface ApiResponse<T = unknown> {
  data: T;
  status: number;
  statusText: string;
  headers: Record<string, string>;
}

export interface ApiError {
  detail: string;
  status_code: number;
  type?: string;
}

export type ApiResult<T> =
  | { success: true; data: T; response: ApiResponse<T> }
  | { success: false; error: ApiError; response?: ApiResponse<unknown> };

// ============================================
// Path Parameter Helpers
// ============================================

export type PathParams<T extends string> =
  T extends `${string}{${infer Param}}${infer Rest}`
    ? { [K in Param]: string } & PathParams<Rest>
    : {};

// ============================================
// Export all module types for convenience
// ============================================

export type {
  // Auth
  UserRegister,
  UserLogin,
  UserResponse,
  TokenResponse,
  PasswordReset,
  PasswordChange,
  LogoutRequest,
  // Companies
  CompanyCreate,
  CompanyUpdate,
  CompanyResponse,
  CompanyListResponse,
  // Branches
  BranchCreate,
  BranchUpdate,
  BranchResponse,
  BranchListResponse,
  BranchConfigCreate,
  BranchConfigUpdate,
  BranchConfigResponse,
  // Billing
  PlanCreate,
  PlanUpdate,
  PlanResponse,
  PlanListResponse,
  SubscriptionCreate,
  SubscriptionResponse,
  SubscribeRequest,
  SubscriptionUpdate,
  SubscriptionCancelRequest,
  UsageRecordResponse,
  UsageSummaryResponse,
  QuotaResponse,
  QuotaCheckResponse,
  InvoiceResponse,
  InvoiceListResponse,
  BillingStatsResponse,
  CompanyBillingSummary,
  // Dashboard
  DashboardStatsResponse,
  DashboardChartResponse,
  DashboardAlertsResponse,
  ExecutiveSummaryResponse,
  BranchDashboardResponse,
  // Analytics
  AnalyticsOverviewResponse,
  TrafficResponse,
  AudienceResponse,
  KpiMetricsResponse,
  BranchComparisonResponse,
  ConversionAnalyticsResponse,
  CampaignAnalyticsResponse,
  AIInsightsResponse,
  GrowthMetricsResponse,
  // AI
  AIPromptCreate,
  AIPromptUpdate,
  AIPromptResponse,
  AIPromptListResponse,
  AIGenerateRequest,
  AIGenerateResponse,
  AISuggestionCreate,
  AISuggestionFeedback,
  AISuggestionResponse,
  AISuggestionListResponse,
  AIRecommendationCreate,
  AIRecommendationResponse,
  AIRecommendationListResponse,
  AIConversationCreate,
  AIConversationResponse,
  AIConversationListResponse,
  AIMessageResponse,
  AISendMessageRequest,
  AISendMessageResponse,
  AIUsageResponse,
  AIUsageListResponse,
  AIUsageSummary,
  AICacheResponse,
  AICacheStats,
  AIErrorResponse,
  // Ads
  AdPlatformCreate,
  AdPlatformUpdate,
  AdPlatformResponse,
  AdPlatformListResponse,
  AdCampaignCreate,
  AdCampaignUpdate,
  AdCampaignResponse,
  AdCampaignListResponse,
  AdCampaignMetricsResponse,
  AdCreativeCreate,
  AdCreativeUpdate,
  AdCreativeResponse,
  AdCreativeListResponse,
  AdAudienceCreate,
  AdAudienceUpdate,
  AdAudienceResponse,
  AdAudienceListResponse,
  AdMetricResponse,
  AdMetricListResponse,
  AggregatedMetricsResponse,
  PerformanceDashboardResponse,
  ROASAnalysisResponse,
  CPAAnalysisResponse,
  CreativeFatigueResponse,
  AudienceOverlapResponse,
  AdBudgetRecommendationResponse,
  AdBudgetRecommendationListResponse,
  LocalRecommendationsResponse,
  SyncRequest,
  SyncResponse,
  ABTestResultResponse,
  DateRangeFilter,
  // Social
  SocialAccountCreate,
  SocialAccountResponse,
  SocialPostCreate,
  SocialPostUpdate,
  SocialPostResponse,
  SocialPostListResponse,
  SocialCompetitorCreate,
  SocialCompetitorResponse,
  SocialAnalyticsResponse,
  SocialScheduleResponse,
  SocialEngagementResponse,
  // Media
  MediaAssetCreate,
  MediaAssetUpdate,
  MediaAssetResponse,
  MediaAssetListItem,
  MediaAssetListResponse,
  MediaAssetFilter,
  MediaCollectionCreate,
  MediaCollectionUpdate,
  MediaCollectionResponse,
  MediaCollectionListResponse,
  MediaCollectionItemAdd,
  MediaTagCreate,
  MediaTagResponse,
  MediaTagUpdate,
  MediaStatsResponse,
  UploadResponse,
  UploadInitiateRequest,
  UploadCompleteRequest,
  SignedUrlResponse,
  PresignedUploadUrlResponse,
  AIAnalysisRequest,
  AIAnalysisResult,
  AIAnalysisTypesResponse,
  JobStatusResponse,
  BulkTagRequest,
  BulkDeleteRequest,
  BulkOperationResponse,
  TagAddRequest,
  // ERP
  ERPConnectionCreate,
  ERPConnectionUpdate,
  ERPConnectionResponse,
  FieldMappingCreate,
  FieldMappingUpdate,
  FieldMappingResponse,
  SyncStatusResponse,
  SyncLogResponse,
  SyncLogListResponse,
  SyncStatsResponse,
  SyncHealthCheckResponse,
  SyncTriggerRequest,
  WebhookResponse,
  ERPWebhookPayload,
  // Events
  EventDefinitionCreate,
  EventDefinitionUpdate,
  EventDefinitionResponse,
  EventDefinitionListResponse,
  EventSubscriptionCreate,
  EventSubscriptionUpdate,
  EventSubscriptionResponse,
  EventSubscriptionListResponse,
  EventLogResponse,
  EventLogListResponse,
  EventRetryResponse,
  DeadLetterEventResponse,
  DeadLetterEventListResponse,
  DeadLetterResolveRequest,
  DeadLetterResolveResponse,
  DeadLetterRetryResponse,
  AutomationRuleCreate,
  AutomationRuleUpdate,
  AutomationRuleResponse,
  AutomationRuleListResponse,
  AutomationRuleToggleResponse,
  AutomationExecutionResponse,
  EventPublishRequest,
  EventPublishResponse,
  EventStatsResponse,
  EventRetryRequest,
  // Audit
  AuditLogCreate,
  AuditLogResponse,
  AuditLogListResponse,
  AuditLogFilter,
  SecurityEventCreate,
  SecurityEventResponse,
  SecurityEventListResponse,
  SecurityEventFilter,
  SecurityEventResolve,
  LoginAttemptResponse,
  LoginAttemptListResponse,
  LoginAttemptFilter,
  APIKeyCreate,
  APIKeyUpdate,
  APIKeyResponse,
  APIKeyListResponse,
  APIKeyValidateRequest,
  APIKeyValidationResult,
  DataAccessLogCreate,
  DataAccessLogResponse,
  DataAccessLogListResponse,
  DataAccessLogFilter,
  AuditStatsResponse,
  APIKeyWithPlainKey,
  // Support
  TicketCreate,
  TicketUpdate,
  TicketResponse,
  TicketListResponse,
  TicketAssign,
  TicketClose,
  TicketEscalate,
  MessageCreate,
  MessageResponse,
  MessageListResponse,
  ConversationReplyRequest,
  ConversationReplyResponse,
  TicketFilterParams,
  SupportMacroCreate,
  SupportMacroUpdate,
  SupportMacroResponse,
  SupportMacroListResponse,
  MacroExpandRequest,
  MacroExpandResponse,
  KnowledgeBaseArticleCreate,
  KnowledgeBaseArticleUpdate,
  KnowledgeBaseArticleResponse,
  KnowledgeBaseArticleListResponse,
  KnowledgeBaseCategoryCreate,
  KnowledgeBaseCategoryResponse,
  KnowledgeBaseSearchRequest,
  KnowledgeBaseSearchResponse,
  EscalationRuleCreate,
  EscalationRuleUpdate,
  EscalationRuleResponse,
  EscalationRuleListResponse,
  EscalationTriggerResult,
  AIReplyRequest,
  AIReplyResponse,
  CategorizationRequest,
  CategorizationResponse,
  SentimentAnalysisRequest,
  SentimentAnalysisResponse,
  HumanTakeoverRequest,
  HumanTakeoverResponse,
  SupportAnalyticsSummary,
  // Notifications
  NotificationCreate,
  NotificationResponse,
  NotificationListResponse,
  NotificationPreference,
  // Health
  HealthStatus,
  DetailedHealthResponse,
  DBHealthResponse,
  RedisHealthResponse,
};
