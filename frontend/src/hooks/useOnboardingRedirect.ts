/**
 * Hook for automatic onboarding redirection after login/registration
 */

import { useEffect } from "react";
import { useRouter } from "next/navigation";
import { useOnboardingStore } from "@/stores/useOnboardingStore";

/**
 * Auto-redirect to onboarding if not completed
 *
 * Usage: Call this hook after successful login/registration
 *
 * @example
 * ```tsx
 * function LoginPage() {
 *   const redirectToOnboarding = useOnboardingRedirect();
 *
 *   const handleLogin = async () => {
 *     await login();
 *     redirectToOnboarding(); // Will redirect if onboarding not done
 *   };
 * }
 * ```
 */
export function useOnboardingRedirect() {
  const router = useRouter();
  const { isCompleted, dismissed, accountAdded, firstScanCompleted } = useOnboardingStore();

  const redirectIfNeeded = () => {
    // Debug log
    console.log("[useOnboardingRedirect] Checking redirect:", {
      isCompleted,
      dismissed,
      accountAdded,
      firstScanCompleted,
    });

    // Don't redirect if onboarding is completed or dismissed
    if (isCompleted || dismissed) {
      console.log("[useOnboardingRedirect] Redirecting to /dashboard (completed or dismissed)");
      router.push("/dashboard");
      return;
    }

    // Redirect to onboarding for first-time users
    console.log("[useOnboardingRedirect] Redirecting to /onboarding (not completed)");
    router.push("/onboarding");
  };

  return redirectIfNeeded;
}

/**
 * Auto-redirect hook with useEffect (automatic version)
 *
 * Automatically redirects when component mounts.
 * Use this in protected routes after login.
 *
 * @example
 * ```tsx
 * function DashboardRedirect() {
 *   useAutoOnboardingRedirect();
 *   return <div>Redirecting...</div>;
 * }
 * ```
 */
export function useAutoOnboardingRedirect() {
  const router = useRouter();
  const { isCompleted, dismissed } = useOnboardingStore();

  useEffect(() => {
    if (!isCompleted && !dismissed) {
      router.push("/onboarding");
    } else {
      router.push("/dashboard");
    }
  }, [isCompleted, dismissed, router]);
}
