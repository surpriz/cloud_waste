/**
 * API client for CutCosts backend
 */

import type {
  AuthTokens,
  CloudAccount,
  CloudAccountCreate,
  LoginRequest,
  OrphanResource,
  OrphanResourceStats,
  OrphanResourceUpdate,
  RegisterRequest,
  ResourceFilters,
  Scan,
  ScanCreate,
  ScanFilters,
  ScanProgress,
  ScanSummary,
  ScanWithResources,
  User,
} from "@/types";

const API_URL = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000";

class APIError extends Error {
  constructor(
    public status: number,
    message: string
  ) {
    super(message);
    this.name = "APIError";
  }
}

/**
 * Get auth token from localStorage
 */
function getAuthToken(): string | null {
  if (typeof window === "undefined") return null;
  return localStorage.getItem("access_token");
}

/**
 * Set auth tokens in localStorage
 */
function setAuthTokens(tokens: AuthTokens): void {
  if (typeof window === "undefined") return;
  localStorage.setItem("access_token", tokens.access_token);
  localStorage.setItem("refresh_token", tokens.refresh_token);
}

/**
 * Clear auth tokens from localStorage
 */
function clearAuthTokens(): void {
  if (typeof window === "undefined") return;
  localStorage.removeItem("access_token");
  localStorage.removeItem("refresh_token");
}

/**
 * Generic fetch wrapper with auth and error handling
 */
async function fetchAPI<T>(
  endpoint: string,
  options: RequestInit = {}
): Promise<T> {
  const token = getAuthToken();

  const headers: Record<string, string> = {
    "Content-Type": "application/json",
    ...(options.headers as Record<string, string>),
  };

  if (token) {
    headers["Authorization"] = `Bearer ${token}`;
  }

  const response = await fetch(`${API_URL}${endpoint}`, {
    ...options,
    headers,
  });

  if (!response.ok) {
    const error = await response.json().catch(() => ({ detail: "Unknown error" }));
    const apiError = new APIError(response.status, error.detail || "API Error");

    // Capture API errors in Sentry (except 401/403 which are normal auth errors)
    if (typeof window !== "undefined" && response.status !== 401 && response.status !== 403) {
      try {
        const Sentry = await import("@sentry/nextjs");
        Sentry.captureException(apiError, {
          tags: {
            api_endpoint: endpoint,
            http_status: response.status,
          },
          extra: {
            error_detail: error.detail,
            request_method: options.method || "GET",
          },
        });
      } catch (e) {
        // Don't fail if Sentry capture fails
        console.error("Failed to capture error in Sentry:", e);
      }
    }

    throw apiError;
  }

  // Handle 204 No Content
  if (response.status === 204) {
    return undefined as T;
  }

  return response.json();
}

/**
 * Authentication API
 */
export const authAPI = {
  async register(data: RegisterRequest): Promise<User> {
    return fetchAPI<User>("/api/v1/auth/register", {
      method: "POST",
      body: JSON.stringify(data),
    });
  },

  async login(data: LoginRequest): Promise<AuthTokens> {
    const formData = new URLSearchParams();
    formData.append("username", data.username);
    formData.append("password", data.password);
    if (data.remember_me !== undefined) {
      formData.append("remember_me", data.remember_me.toString());
    }

    const response = await fetch(`${API_URL}/api/v1/auth/login`, {
      method: "POST",
      headers: {
        "Content-Type": "application/x-www-form-urlencoded",
      },
      body: formData,
    });

    if (!response.ok) {
      const error = await response.json().catch(() => ({ detail: "Login failed" }));
      throw new APIError(response.status, error.detail || "Login failed");
    }

    const tokens = await response.json();
    setAuthTokens(tokens);
    return tokens;
  },

  async getCurrentUser(): Promise<User> {
    return fetchAPI<User>("/api/v1/auth/me");
  },

  async refreshToken(): Promise<AuthTokens> {
    const refreshToken = localStorage.getItem("refresh_token");
    if (!refreshToken) {
      throw new Error("No refresh token available");
    }

    const response = await fetch(`${API_URL}/api/v1/auth/refresh`, {
      method: "POST",
      headers: {
        "Content-Type": "application/json",
      },
      body: JSON.stringify({ refresh_token: refreshToken }),
    });

    if (!response.ok) {
      clearAuthTokens();
      throw new APIError(response.status, "Token refresh failed");
    }

    const tokens = await response.json();
    setAuthTokens(tokens);
    return tokens;
  },

  logout(): void {
    clearAuthTokens();
  },

  async verifyEmail(token: string): Promise<{ message: string }> {
    return fetchAPI<{ message: string }>(`/api/v1/auth/verify-email/${token}`);
  },

  async resendVerificationEmail(email: string): Promise<{ message: string }> {
    const formData = new URLSearchParams();
    formData.append("email", email);

    return fetchAPI<{ message: string }>("/api/v1/auth/resend-verification", {
      method: "POST",
      headers: {
        "Content-Type": "application/x-www-form-urlencoded",
      },
      body: formData,
    });
  },
};

/**
 * Cloud Accounts API
 */
export const accountsAPI = {
  async list(): Promise<CloudAccount[]> {
    return fetchAPI<CloudAccount[]>("/api/v1/accounts/");
  },

  async get(id: string): Promise<CloudAccount> {
    return fetchAPI<CloudAccount>(`/api/v1/accounts/${id}`);
  },

  async create(data: CloudAccountCreate): Promise<CloudAccount> {
    return fetchAPI<CloudAccount>("/api/v1/accounts/", {
      method: "POST",
      body: JSON.stringify(data),
    });
  },

  async update(id: string, data: Partial<CloudAccountCreate>): Promise<CloudAccount> {
    return fetchAPI<CloudAccount>(`/api/v1/accounts/${id}`, {
      method: "PATCH",
      body: JSON.stringify(data),
    });
  },

  async delete(id: string): Promise<void> {
    return fetchAPI<void>(`/api/v1/accounts/${id}`, {
      method: "DELETE",
    });
  },

  async validate(id: string): Promise<any> {
    return fetchAPI<any>(`/api/v1/accounts/${id}/validate`, {
      method: "POST",
    });
  },

  async validateCredentials(data: CloudAccountCreate): Promise<{
    valid: boolean;
    provider: string;
    account_id?: string;
    subscription_id?: string;
    subscription_name?: string;
    message: string;
  }> {
    return fetchAPI(`/api/v1/accounts/validate-credentials`, {
      method: "POST",
      body: JSON.stringify(data),
    });
  },
};

/**
 * Scans API
 */
export const scansAPI = {
  async list(filters?: ScanFilters): Promise<Scan[]> {
    const params = new URLSearchParams();
    if (filters?.skip) params.append("skip", filters.skip.toString());
    if (filters?.limit) params.append("limit", filters.limit.toString());

    const query = params.toString() ? `?${params.toString()}` : "";
    return fetchAPI<Scan[]>(`/api/v1/scans/${query}`);
  },

  async get(id: string): Promise<ScanWithResources> {
    return fetchAPI<ScanWithResources>(`/api/v1/scans/${id}`);
  },

  async create(data: ScanCreate): Promise<Scan> {
    return fetchAPI<Scan>("/api/v1/scans/", {
      method: "POST",
      body: JSON.stringify(data),
    });
  },

  async getSummary(cloudAccountId?: string): Promise<ScanSummary> {
    const params = cloudAccountId
      ? `?cloud_account_id=${cloudAccountId}`
      : "";
    return fetchAPI<ScanSummary>(`/api/v1/scans/summary${params}`);
  },

  async listByAccount(accountId: string, filters?: ScanFilters): Promise<Scan[]> {
    const params = new URLSearchParams();
    if (filters?.skip) params.append("skip", filters.skip.toString());
    if (filters?.limit) params.append("limit", filters.limit.toString());

    const query = params.toString() ? `?${params.toString()}` : "";
    return fetchAPI<Scan[]>(`/api/v1/scans/account/${accountId}${query}`);
  },

  async delete(id: string): Promise<void> {
    return fetchAPI<void>(`/api/v1/scans/${id}`, {
      method: "DELETE",
    });
  },

  async deleteAll(): Promise<void> {
    return fetchAPI<void>("/api/v1/scans/", {
      method: "DELETE",
    });
  },

  async getProgress(id: string): Promise<ScanProgress> {
    return fetchAPI<ScanProgress>(`/api/v1/scans/${id}/progress`);
  },
};

/**
 * Orphan Resources API
 */
export const resourcesAPI = {
  async list(filters?: ResourceFilters): Promise<OrphanResource[]> {
    const params = new URLSearchParams();
    if (filters?.cloud_account_id) params.append("cloud_account_id", filters.cloud_account_id);
    if (filters?.status) params.append("status", filters.status);
    if (filters?.resource_type) params.append("resource_type", filters.resource_type);
    if (filters?.skip) params.append("skip", filters.skip.toString());
    if (filters?.limit) params.append("limit", filters.limit.toString());

    const query = params.toString() ? `?${params.toString()}` : "";
    return fetchAPI<OrphanResource[]>(`/api/v1/resources/${query}`);
  },

  async get(id: string): Promise<OrphanResource> {
    return fetchAPI<OrphanResource>(`/api/v1/resources/${id}`);
  },

  async update(id: string, data: OrphanResourceUpdate): Promise<OrphanResource> {
    return fetchAPI<OrphanResource>(`/api/v1/resources/${id}`, {
      method: "PATCH",
      body: JSON.stringify(data),
    });
  },

  async delete(id: string): Promise<void> {
    return fetchAPI<void>(`/api/v1/resources/${id}`, {
      method: "DELETE",
    });
  },

  async getStats(cloudAccountId?: string, status?: string): Promise<OrphanResourceStats> {
    const params = new URLSearchParams();
    if (cloudAccountId) params.append("cloud_account_id", cloudAccountId);
    if (status) params.append("status", status);

    const query = params.toString() ? `?${params.toString()}` : "";
    return fetchAPI<OrphanResourceStats>(`/api/v1/resources/stats${query}`);
  },

  async getTopCost(cloudAccountId?: string, limit: number = 10): Promise<OrphanResource[]> {
    const params = new URLSearchParams();
    if (cloudAccountId) params.append("cloud_account_id", cloudAccountId);
    params.append("limit", limit.toString());

    const query = params.toString() ? `?${params.toString()}` : "";
    return fetchAPI<OrphanResource[]>(`/api/v1/resources/top-cost${query}`);
  },
};

/**
 * Impact & Savings API
 */
export const impactAPI = {
  async getSummary(): Promise<any> {
    return fetchAPI<any>("/api/v1/impact/summary");
  },

  async getTimeline(period: "day" | "week" | "month" | "year" | "all" = "month"): Promise<any> {
    return fetchAPI<any>(`/api/v1/impact/timeline?period=${period}`);
  },

  async getAchievements(): Promise<any> {
    return fetchAPI<any>("/api/v1/impact/achievements");
  },

  async getQuickStats(): Promise<any> {
    return fetchAPI<any>("/api/v1/impact/quick-stats");
  },
};

/**
 * Chat API (AI Assistant)
 */
export const chatAPI = {
  async listConversations(): Promise<import("@/types").ChatConversationListItem[]> {
    return fetchAPI<import("@/types").ChatConversationListItem[]>("/api/v1/chat/conversations");
  },

  async getConversation(id: string): Promise<import("@/types").ChatConversation> {
    return fetchAPI<import("@/types").ChatConversation>(`/api/v1/chat/conversations/${id}`);
  },

  async createConversation(title: string): Promise<import("@/types").ChatConversation> {
    return fetchAPI<import("@/types").ChatConversation>("/api/v1/chat/conversations", {
      method: "POST",
      body: JSON.stringify({ title }),
    });
  },

  async updateConversation(id: string, title: string): Promise<import("@/types").ChatConversation> {
    return fetchAPI<import("@/types").ChatConversation>(`/api/v1/chat/conversations/${id}`, {
      method: "PATCH",
      body: JSON.stringify({ title }),
    });
  },

  async deleteConversation(id: string): Promise<void> {
    return fetchAPI<void>(`/api/v1/chat/conversations/${id}`, {
      method: "DELETE",
    });
  },

  /**
   * Stream a message using Server-Sent Events (SSE)
   */
  streamMessage(
    conversationId: string,
    message: string,
    onChunk: (chunk: string) => void,
    onComplete: () => void,
    onError: (error: Error) => void
  ): () => void {
    const token = getAuthToken();
    const url = `${API_URL}/api/v1/chat/conversations/${conversationId}/messages`;

    // Create request with SSE
    fetch(url, {
      method: "POST",
      headers: {
        "Content-Type": "application/json",
        ...(token && { Authorization: `Bearer ${token}` }),
      },
      body: JSON.stringify({ content: message }),
    })
      .then(async (response) => {
        if (!response.ok) {
          const error = await response.json().catch(() => ({ detail: "Stream failed" }));
          throw new Error(error.detail || "Stream failed");
        }

        if (!response.body) {
          throw new Error("No response body");
        }

        const reader = response.body.getReader();
        const decoder = new TextDecoder();

        try {
          while (true) {
            const { done, value } = await reader.read();

            if (done) {
              onComplete();
              break;
            }

            // Decode chunk
            const chunk = decoder.decode(value, { stream: true });

            // Parse SSE format (lines starting with "data: ")
            const lines = chunk.split("\n");
            for (const line of lines) {
              if (line.startsWith("data: ")) {
                const data = line.substring(6).trim();

                // Handle different event types
                if (line.includes("event: message")) {
                  onChunk(data);
                } else if (line.includes("event: done")) {
                  onComplete();
                  return;
                } else if (line.includes("event: error")) {
                  onError(new Error(data));
                  return;
                } else {
                  // Default: assume it's message content
                  onChunk(data);
                }
              }
            }
          }
        } catch (err) {
          onError(err as Error);
        }
      })
      .catch((err) => {
        onError(err);
      });

    // Return cleanup function
    return () => {
      // Cleanup handled by reader closure
    };
  },
};

/**
 * Admin API (Superuser only)
 */
export const adminAPI = {
  async getStats(): Promise<import("@/types").AdminStats> {
    return fetchAPI<import("@/types").AdminStats>("/api/v1/admin/stats");
  },

  async listUsers(skip: number = 0, limit: number = 100): Promise<import("@/types").User[]> {
    const params = new URLSearchParams();
    params.append("skip", skip.toString());
    params.append("limit", limit.toString());
    const query = params.toString() ? `?${params.toString()}` : "";
    return fetchAPI<import("@/types").User[]>(`/api/v1/admin/users${query}`);
  },

  async getUserById(userId: string): Promise<import("@/types").User> {
    return fetchAPI<import("@/types").User>(`/api/v1/admin/users/${userId}`);
  },

  async updateUser(userId: string, data: import("@/types").UserAdminUpdate): Promise<import("@/types").User> {
    return fetchAPI<import("@/types").User>(`/api/v1/admin/users/${userId}`, {
      method: "PATCH",
      body: JSON.stringify(data),
    });
  },

  async toggleUserActive(userId: string): Promise<import("@/types").User> {
    return fetchAPI<import("@/types").User>(`/api/v1/admin/users/${userId}/toggle-active`, {
      method: "POST",
    });
  },

  async deleteUser(userId: string): Promise<void> {
    return fetchAPI<void>(`/api/v1/admin/users/${userId}`, {
      method: "DELETE",
    });
  },

  // Pricing management
  async getPricingStats(): Promise<import("@/types").PricingStats> {
    return fetchAPI<import("@/types").PricingStats>("/api/v1/admin/pricing/stats");
  },

  async getPricingCache(
    provider?: string,
    region?: string,
    service?: string,
    skip: number = 0,
    limit: number = 100
  ): Promise<import("@/types").PricingCacheItem[]> {
    const params = new URLSearchParams();
    if (provider) params.append("provider", provider);
    if (region) params.append("region", region);
    if (service) params.append("service", service);
    params.append("skip", skip.toString());
    params.append("limit", limit.toString());
    const query = params.toString() ? `?${params.toString()}` : "";
    return fetchAPI<import("@/types").PricingCacheItem[]>(`/api/v1/admin/pricing/cache${query}`);
  },

  async refreshPricing(): Promise<import("@/types").PricingRefreshResponse> {
    return fetchAPI<import("@/types").PricingRefreshResponse>("/api/v1/admin/pricing/refresh", {
      method: "POST",
    });
  },

  async getRefreshTaskStatus(taskId: string): Promise<import("@/types").PricingRefreshResponse> {
    return fetchAPI<import("@/types").PricingRefreshResponse>(`/api/v1/admin/pricing/refresh/${taskId}`);
  },

  // ML data management
  async getMLStats(): Promise<import("@/types").MLDataStats> {
    return fetchAPI<import("@/types").MLDataStats>("/api/v1/admin/ml-stats");
  },

  async exportMLData(days: number = 90, format: string = "json"): Promise<import("@/types").MLExportResponse> {
    const params = new URLSearchParams();
    params.append("days", days.toString());
    params.append("output_format", format);
    const query = params.toString() ? `?${params.toString()}` : "";
    return fetchAPI<import("@/types").MLExportResponse>(`/api/v1/admin/ml-export${query}`, {
      method: "POST",
    });
  },

  // AWS SES email monitoring
  async getSESMetrics(): Promise<import("@/types").SESMetrics> {
    return fetchAPI<import("@/types").SESMetrics>("/api/v1/admin/ses-metrics");
  },

  async getSESIdentities(): Promise<import("@/types").SESIdentityMetrics[]> {
    return fetchAPI<import("@/types").SESIdentityMetrics[]>("/api/v1/admin/ses-identities");
  },

  // Detection Rules - Admin
  async setAllDetectionRulesToZero(): Promise<{ message: string; resources_updated: number; total_resources: number }> {
    return fetchAPI<{ message: string; resources_updated: number; total_resources: number }>(
      "/api/v1/detection-rules/admin/set-all-to-zero",
      {
        method: "POST",
      }
    );
  },

  // Subscription Management
  async getSubscriptionPlans(): Promise<import("@/types/subscription").SubscriptionPlan[]> {
    return fetchAPI<import("@/types/subscription").SubscriptionPlan[]>("/api/v1/subscriptions/plans");
  },

  async getCurrentSubscription(): Promise<import("@/types/subscription").UserSubscription> {
    return fetchAPI<import("@/types/subscription").UserSubscription>("/api/v1/subscriptions/current");
  },

  async createCheckoutSession(
    request: import("@/types/subscription").CreateCheckoutSessionRequest
  ): Promise<import("@/types/subscription").CreateCheckoutSessionResponse> {
    return fetchAPI<import("@/types/subscription").CreateCheckoutSessionResponse>("/api/v1/subscriptions/create-checkout-session", {
      method: "POST",
      body: JSON.stringify(request),
    });
  },

  async createPortalSession(
    request: import("@/types/subscription").CreatePortalSessionRequest
  ): Promise<import("@/types/subscription").CreatePortalSessionResponse> {
    return fetchAPI<import("@/types/subscription").CreatePortalSessionResponse>("/api/v1/subscriptions/create-portal-session", {
      method: "POST",
      body: JSON.stringify(request),
    });
  },
};

// Default export with all API methods
const api = {
  ...authAPI,
  ...accountsAPI,
  ...scansAPI,
  ...resourcesAPI,
  ...impactAPI,
  ...chatAPI,
  ...adminAPI,
};

export default api;
export { APIError, clearAuthTokens, getAuthToken, setAuthTokens };
