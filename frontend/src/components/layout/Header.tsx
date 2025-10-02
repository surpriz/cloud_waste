"use client";

import { useAuthStore } from "@/stores/useAuthStore";
import { Bell, User } from "lucide-react";

export function Header() {
  const user = useAuthStore((state) => state.user);

  return (
    <header className="flex h-16 items-center justify-between border-b bg-white px-6">
      <div>
        <h2 className="text-xl font-semibold text-gray-900">
          Welcome back, {user?.full_name || user?.email || "User"}
        </h2>
        <p className="text-sm text-gray-500">
          Monitor and optimize your cloud resources
        </p>
      </div>

      <div className="flex items-center gap-4">
        {/* Notifications */}
        <button className="relative rounded-full p-2 text-gray-400 hover:bg-gray-100 hover:text-gray-600">
          <Bell className="h-5 w-5" />
          <span className="absolute right-1 top-1 h-2 w-2 rounded-full bg-red-500" />
        </button>

        {/* User menu */}
        <div className="flex items-center gap-2 rounded-lg border px-3 py-2">
          <User className="h-5 w-5 text-gray-400" />
          <span className="text-sm font-medium text-gray-700">
            {user?.email}
          </span>
        </div>
      </div>
    </header>
  );
}
