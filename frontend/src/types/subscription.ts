/**
 * Subscription types
 */

export interface SubscriptionPlan {
  id: string;
  name: string;
  display_name: string;
  description: string | null;
  price_monthly: number;
  currency: string;
  stripe_price_id: string | null;

  // Limits
  max_scans_per_month: number | null;
  max_cloud_accounts: number | null;

  // Features
  has_ai_chat: boolean;
  has_impact_tracking: boolean;
  has_email_notifications: boolean;
  has_api_access: boolean;
  has_priority_support: boolean;

  is_active: boolean;
}

export interface UserSubscription {
  id: string;
  user_id: string;
  plan: SubscriptionPlan;
  status: 'active' | 'canceled' | 'past_due' | 'incomplete' | 'trialing';
  stripe_subscription_id: string | null;
  current_period_start: string | null;
  current_period_end: string | null;
  cancel_at_period_end: boolean;
  scans_used_this_month: number;
  last_scan_reset_at: string | null;
  created_at: string;
  canceled_at: string | null;
}

export interface CreateCheckoutSessionRequest {
  plan_name: 'pro' | 'enterprise';
  success_url: string;
  cancel_url: string;
}

export interface CreateCheckoutSessionResponse {
  session_id: string;
  url: string;
}

export interface CreatePortalSessionRequest {
  return_url: string;
}

export interface CreatePortalSessionResponse {
  url: string;
}

export interface SubscriptionLimitCheck {
  allowed: boolean;
  error_message: string | null;
  current_usage: number | null;
  limit: number | null;
}
