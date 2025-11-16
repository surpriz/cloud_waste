"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";
import {
  LayoutDashboard,
  Cloud,
  Search,
  Settings,
  BookOpen,
  LogOut,
  X,
  TrendingUp,
  MessageSquare,
  Shield,
  Trash2,
  Sparkles,
} from "lucide-react";
import { useAuthStore } from "@/stores/useAuthStore";

const navigation = [
  { name: "Dashboard", href: "/dashboard", icon: LayoutDashboard },
  { name: "Cloud Accounts", href: "/dashboard/accounts", icon: Cloud },
  { name: "Scans", href: "/dashboard/scans", icon: Search },
  { name: "Waste Detection", href: "/dashboard/resources", icon: Trash2 },
  { name: "Cost Optimization", href: "/dashboard/cost-intelligence", icon: Sparkles },
  { name: "🤖 AI Assistant", href: "/dashboard/assistant", icon: MessageSquare },
  { name: "💰 Impact & Savings", href: "/dashboard/impact", icon: TrendingUp },
  { name: "Settings", href: "/dashboard/settings", icon: Settings },
  { name: "Documentation", href: "/dashboard/docs", icon: BookOpen },
];

interface SidebarProps {
  isMobileMenuOpen?: boolean;
  onCloseMobileMenu?: () => void;
}

export function Sidebar({ isMobileMenuOpen = false, onCloseMobileMenu }: SidebarProps) {
  const pathname = usePathname();
  const logout = useAuthStore((state) => state.logout);
  const user = useAuthStore((state) => state.user);

  const SidebarContent = () => (
    <>
      {/* Logo */}
      <div className="flex h-16 items-center justify-between px-4 border-b border-gray-800">
        <h1 className="text-2xl font-bold text-white">CutCosts</h1>
        {/* Close button (mobile only) */}
        {onCloseMobileMenu && (
          <button
            onClick={onCloseMobileMenu}
            className="lg:hidden rounded-lg p-2 text-gray-400 hover:bg-gray-800 hover:text-white transition-colors"
            aria-label="Close menu"
          >
            <X className="h-6 w-6" />
          </button>
        )}
      </div>

      {/* Navigation */}
      <nav className="flex-1 space-y-1 px-3 py-4">
        {navigation.map((item) => {
          const isActive = pathname === item.href;
          const Icon = item.icon;

          return (
            <Link
              key={item.name}
              href={item.href}
              onClick={onCloseMobileMenu}
              className={`
                flex items-center gap-3 rounded-lg px-3 py-2 text-sm font-medium transition-colors
                ${
                  isActive
                    ? "bg-gray-800 text-white"
                    : "text-gray-400 hover:bg-gray-800 hover:text-white"
                }
              `}
            >
              <Icon className="h-5 w-5" />
              {item.name}
            </Link>
          );
        })}

        {/* Admin Panel - Only visible to superusers */}
        {user?.is_superuser && (
          <>
            <div className="border-t border-gray-700 my-2"></div>
            <Link
              href="/dashboard/admin"
              onClick={onCloseMobileMenu}
              className={`
                flex items-center gap-3 rounded-lg px-3 py-2 text-sm font-medium transition-colors
                ${
                  pathname === "/dashboard/admin"
                    ? "bg-purple-900 text-white"
                    : "text-purple-400 hover:bg-purple-900 hover:text-white"
                }
              `}
            >
              <Shield className="h-5 w-5" />
              Admin Panel
            </Link>
          </>
        )}
      </nav>

      {/* Logout */}
      <div className="border-t border-gray-800 p-3">
        <button
          onClick={logout}
          className="flex w-full items-center gap-3 rounded-lg px-3 py-2 text-sm font-medium text-gray-400 transition-colors hover:bg-gray-800 hover:text-white"
        >
          <LogOut className="h-5 w-5" />
          Logout
        </button>
      </div>
    </>
  );

  return (
    <>
      {/* Desktop Sidebar - Always visible on large screens */}
      <div className="hidden lg:flex h-screen w-64 flex-col bg-gray-900">
        <SidebarContent />
      </div>

      {/* Mobile Sidebar - Overlay */}
      {isMobileMenuOpen && (
        <div className="fixed inset-0 z-50 lg:hidden">
          {/* Backdrop */}
          <div
            className="fixed inset-0 bg-black/50 backdrop-blur-sm"
            onClick={onCloseMobileMenu}
            aria-hidden="true"
          />
          {/* Sidebar */}
          <div className="fixed inset-y-0 left-0 w-64 bg-gray-900 shadow-xl">
            <div className="flex h-full flex-col">
              <SidebarContent />
            </div>
          </div>
        </div>
      )}
    </>
  );
}
