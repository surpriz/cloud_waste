"use client";

import { useEffect, useState } from "react";
import { useRouter } from "next/navigation";
import { useAuthStore } from "@/stores/useAuthStore";

export default function AdminLayout({
  children,
}: {
  children: React.ReactNode;
}) {
  const router = useRouter();
  const user = useAuthStore((state) => state.user);
  const fetchCurrentUser = useAuthStore((state) => state.fetchCurrentUser);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    const checkAdmin = async () => {
      // Fetch user if not loaded
      if (!user) {
        await fetchCurrentUser();
      }
      setLoading(false);
    };

    checkAdmin();
  }, [user, fetchCurrentUser]);

  useEffect(() => {
    // Redirect if not superuser
    if (!loading && (!user || !user.is_superuser)) {
      router.push("/dashboard");
    }
  }, [loading, user, router]);

  // Show loading state
  if (loading) {
    return (
      <div className="flex items-center justify-center min-h-screen">
        <div className="text-center">
          <div className="animate-spin rounded-full h-12 w-12 border-b-2 border-blue-600 mx-auto"></div>
          <p className="mt-4 text-gray-600">Verifying admin access...</p>
        </div>
      </div>
    );
  }

  // Show nothing if not admin (will redirect)
  if (!user || !user.is_superuser) {
    return null;
  }

  // Render admin content
  return <>{children}</>;
}
