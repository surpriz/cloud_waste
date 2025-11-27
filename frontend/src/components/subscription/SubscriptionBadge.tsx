/**
 * Subscription Badge Component
 * Displays the user's current subscription plan as a badge
 */

"use client";

import { useEffect } from "react";
import { Crown, Sparkles, Zap } from "lucide-react";
import useSubscriptionStore from "@/stores/useSubscriptionStore";

interface SubscriptionBadgeProps {
  size?: "sm" | "md" | "lg";
  showIcon?: boolean;
}

export function SubscriptionBadge({
  size = "md",
  showIcon = true,
}: SubscriptionBadgeProps) {
  const { currentSubscription, fetchCurrentSubscription } =
    useSubscriptionStore();

  useEffect(() => {
    if (!currentSubscription) {
      fetchCurrentSubscription();
    }
  }, [currentSubscription]);

  if (!currentSubscription) {
    return null;
  }

  const { plan } = currentSubscription;

  const sizeClasses = {
    sm: "text-xs px-2 py-1",
    md: "text-sm px-3 py-1.5",
    lg: "text-base px-4 py-2",
  };

  const iconSizes = {
    sm: "h-3 w-3",
    md: "h-4 w-4",
    lg: "h-5 w-5",
  };

  const getPlanConfig = () => {
    switch (plan.name) {
      case "free":
        return {
          label: "Free",
          icon: Zap,
          className: "bg-gray-100 text-gray-700 border border-gray-300",
        };
      case "pro":
        return {
          label: "Pro",
          icon: Sparkles,
          className:
            "bg-gradient-to-r from-blue-500 to-blue-600 text-white shadow-md",
        };
      case "enterprise":
        return {
          label: "Enterprise",
          icon: Crown,
          className:
            "bg-gradient-to-r from-purple-600 to-blue-600 text-white shadow-lg",
        };
      default:
        return {
          label: plan.display_name,
          icon: Zap,
          className: "bg-gray-100 text-gray-700",
        };
    }
  };

  const config = getPlanConfig();
  const Icon = config.icon;

  return (
    <div
      className={`inline-flex items-center gap-1.5 font-semibold rounded-full ${sizeClasses[size]} ${config.className}`}
    >
      {showIcon && <Icon className={iconSizes[size]} />}
      <span>{config.label}</span>
    </div>
  );
}
