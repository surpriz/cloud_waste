"use client";

import { useEffect, useState } from "react";
import { useRouter } from "next/navigation";
import { Sidebar } from "@/components/layout/Sidebar";
import { Header } from "@/components/layout/Header";
import { BackToTop } from "@/components/layout/BackToTop";
import { OnboardingBanner } from "@/components/onboarding";
import { useAuthStore } from "@/stores/useAuthStore";
import { useAccountStore } from "@/stores/useAccountStore";
import { useScanStore } from "@/stores/useScanStore";
import { useOnboardingStore } from "@/stores/useOnboardingStore";
import { isAuthenticated } from "@/lib/auth";

export default function DashboardLayout({
  children,
}: {
  children: React.ReactNode;
}) {
  const router = useRouter();
  const { user, fetchCurrentUser } = useAuthStore();
  const { accounts } = useAccountStore();
  const { scans } = useScanStore();
  const { isCompleted, dismissed, resetOnboarding } = useOnboardingStore();
  const [isMobileMenuOpen, setIsMobileMenuOpen] = useState(false);

  // Debug log
  useEffect(() => {
    console.log("[DashboardLayout] Mounted", { user });
  }, []);

  useEffect(() => {
    if (!isAuthenticated()) {
      router.push("/auth/login");
      return;
    }

    if (!user) {
      fetchCurrentUser();
    }
  }, [user, fetchCurrentUser, router]);

  // Auto-reset onboarding for genuinely new users
  // This fixes localStorage pollution from previous users
  useEffect(() => {
    // Only check when user is loaded and we have accounts/scans data
    if (!user) return;

    const isNewUser = accounts.length === 0 && scans.length === 0;
    const onboardingMarkedAsDone = isCompleted || dismissed;

    // If user is new but onboarding shows as done (from localStorage pollution),
    // reset it so they see the onboarding banner
    if (isNewUser && onboardingMarkedAsDone) {
      console.log("[DashboardLayout] Detected new user with polluted state, resetting onboarding");
      resetOnboarding();
    }
  }, [user, accounts.length, scans.length, isCompleted, dismissed, resetOnboarding]);

  // Close mobile menu on route change
  useEffect(() => {
    setIsMobileMenuOpen(false);
  }, [children]);

  if (!isAuthenticated() || !user) {
    return (
      <div className="flex h-screen items-center justify-center">
        <div className="text-gray-500">Loading...</div>
      </div>
    );
  }

  return (
    <div className="flex h-screen bg-gray-50">
      <Sidebar
        isMobileMenuOpen={isMobileMenuOpen}
        onCloseMobileMenu={() => setIsMobileMenuOpen(false)}
      />
      <div className="flex flex-1 flex-col overflow-hidden">
        <Header onOpenMobileMenu={() => setIsMobileMenuOpen(true)} />
        <main className="flex-1 overflow-y-auto p-4 md:p-6">
          {/* Onboarding Banner - shown until setup is complete */}
          <div className="mb-6">
            <OnboardingBanner />
          </div>

          {children}
        </main>
      </div>
      <BackToTop />
    </div>
  );
}
