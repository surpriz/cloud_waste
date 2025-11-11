/**
 * Authentication utilities
 */

import { authAPI } from "./api";
import type { User } from "@/types";

export function isAuthenticated(): boolean {
  if (typeof window === "undefined") return false;
  const token = localStorage.getItem("access_token");
  return !!token;
}

export async function getCurrentUser(): Promise<User | null> {
  try {
    return await authAPI.getCurrentUser();
  } catch (error) {
    return null;
  }
}

export function logout(): void {
  authAPI.logout();
  if (typeof window !== "undefined") {
    // Clear ALL localStorage to prevent state pollution between users
    // This includes onboarding state, preferences, and any cached data
    localStorage.clear();

    // Redirect to login page
    // Note: Store resets are handled by useAuthStore.logout()
    window.location.href = "/auth/login";
  }
}

/**
 * Decode JWT token (simple implementation, no verification)
 */
export function decodeToken(token: string): any {
  try {
    const base64Url = token.split(".")[1];
    if (!base64Url) return null;
    
    const base64 = base64Url.replace(/-/g, "+").replace(/_/g, "/");
    const jsonPayload = decodeURIComponent(
      atob(base64)
        .split("")
        .map((c) => "%" + ("00" + c.charCodeAt(0).toString(16)).slice(-2))
        .join("")
    );
    return JSON.parse(jsonPayload);
  } catch (error) {
    return null;
  }
}

/**
 * Check if token is expired
 */
export function isTokenExpired(token: string): boolean {
  const decoded = decodeToken(token);
  if (!decoded || !decoded.exp) return true;

  const expirationTime = decoded.exp * 1000; // Convert to milliseconds
  return Date.now() >= expirationTime;
}

/**
 * Auto-refresh token if expired
 */
export async function ensureValidToken(): Promise<boolean> {
  if (typeof window === "undefined") return false;

  const token = localStorage.getItem("access_token");
  if (!token) return false;

  if (isTokenExpired(token)) {
    try {
      await authAPI.refreshToken();
      return true;
    } catch (error) {
      logout();
      return false;
    }
  }

  return true;
}
