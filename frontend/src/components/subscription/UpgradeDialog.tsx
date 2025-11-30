/**
 * Upgrade Dialog Component
 * Shows when user reaches a subscription limit
 */

"use client";

import { useRouter } from "next/navigation";
import {
  AlertCircle,
  ArrowRight,
  Check,
  Crown,
  Sparkles,
  X,
} from "lucide-react";
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from "@/components/ui/RadixDialog";
import { Button } from "@/components/ui/button";
import { Separator } from "@/components/ui/separator";

interface UpgradeDialogProps {
  open: boolean;
  onOpenChange: (open: boolean) => void;
  reason:
    | "scan_limit"
    | "cloud_account_limit"
    | "ai_chat"
    | "impact_tracking"
    | "api_access"
    | "email_notifications";
  currentPlan?: "free" | "pro" | "enterprise";
}

export function UpgradeDialog({
  open,
  onOpenChange,
  reason,
  currentPlan = "free",
}: UpgradeDialogProps) {
  const router = useRouter();

  const getReasonConfig = () => {
    switch (reason) {
      case "scan_limit":
        return {
          title: "Scan Limit Reached",
          description:
            "You've reached your monthly scan limit. Upgrade to continue scanning your cloud resources.",
          icon: AlertCircle,
          iconColor: "text-orange-600",
          features: ["Unlimited scans per month", "Priority scan processing"],
        };
      case "cloud_account_limit":
        return {
          title: "Cloud Account Limit Reached",
          description:
            "You've reached your cloud account limit. Upgrade to connect more accounts.",
          icon: AlertCircle,
          iconColor: "text-orange-600",
          features: [
            "Up to 5 cloud accounts (Pro)",
            "Unlimited cloud accounts (Enterprise)",
          ],
        };
      case "ai_chat":
        return {
          title: "AI Chat Assistant",
          description:
            "Get intelligent insights and recommendations from our AI-powered assistant.",
          icon: Sparkles,
          iconColor: "text-blue-600",
          features: [
            "AI-powered resource analysis",
            "Intelligent cost optimization recommendations",
            "Natural language queries",
          ],
        };
      case "impact_tracking":
        return {
          title: "Environmental Impact Tracking",
          description:
            "Track the environmental impact of your cloud waste and savings.",
          icon: Sparkles,
          iconColor: "text-green-600",
          features: [
            "CO2 emissions tracking",
            "Environmental impact metrics",
            "Sustainability reports",
          ],
        };
      case "api_access":
        return {
          title: "API Access",
          description:
            "Integrate CutCosts with your existing tools and workflows.",
          icon: Crown,
          iconColor: "text-purple-600",
          features: [
            "Full REST API access",
            "Webhooks for real-time updates",
            "Custom integrations",
          ],
        };
      case "email_notifications":
        return {
          title: "Email Notifications",
          description: "Get notified when important events occur in your account.",
          icon: Sparkles,
          iconColor: "text-blue-600",
          features: [
            "Scan completion alerts",
            "New orphaned resources detected",
            "Cost threshold notifications",
          ],
        };
      default:
        return {
          title: "Upgrade Required",
          description: "This feature requires a premium subscription.",
          icon: AlertCircle,
          iconColor: "text-orange-600",
          features: [],
        };
    }
  };

  const config = getReasonConfig();
  const Icon = config.icon;

  const getRecommendedPlan = () => {
    if (reason === "api_access") return "enterprise";
    if (currentPlan === "free") return "pro";
    return "enterprise";
  };

  const recommendedPlan = getRecommendedPlan();

  const handleUpgrade = () => {
    onOpenChange(false);
    router.push("/pricing");
  };

  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent className="sm:max-w-md">
        <DialogHeader>
          <button
            onClick={() => onOpenChange(false)}
            className="absolute right-4 top-4 rounded-sm opacity-70 ring-offset-background transition-opacity hover:opacity-100 focus:outline-none focus:ring-2 focus:ring-ring focus:ring-offset-2 disabled:pointer-events-none data-[state=open]:bg-accent data-[state=open]:text-muted-foreground"
          >
            <X className="h-4 w-4" />
            <span className="sr-only">Close</span>
          </button>
          <div className="flex items-center gap-3">
            <div
              className={`flex h-12 w-12 items-center justify-center rounded-full bg-opacity-10 ${
                config.iconColor.replace("text-", "bg-")
              }`}
            >
              <Icon className={`h-6 w-6 ${config.iconColor}`} />
            </div>
            <div>
              <DialogTitle>{config.title}</DialogTitle>
              <DialogDescription className="text-left">
                {config.description}
              </DialogDescription>
            </div>
          </div>
        </DialogHeader>

        <Separator />

        <div className="space-y-4">
          <div>
            <h4 className="font-semibold text-sm mb-3">
              What you'll get with {recommendedPlan === "pro" ? "Pro" : "Enterprise"}:
            </h4>
            <ul className="space-y-2">
              {config.features.map((feature, idx) => (
                <li key={idx} className="flex items-start gap-2 text-sm">
                  <Check className="h-4 w-4 text-green-600 mt-0.5 flex-shrink-0" />
                  <span>{feature}</span>
                </li>
              ))}
            </ul>
          </div>

          <div className="rounded-lg bg-blue-50 p-4 border border-blue-200">
            <p className="text-sm text-blue-800">
              {recommendedPlan === "pro" ? (
                <>
                  <strong>Pro Plan:</strong> €29/month - Perfect for growing teams
                </>
              ) : (
                <>
                  <strong>Enterprise Plan:</strong> €99/month - Unlimited resources
                </>
              )}
            </p>
          </div>
        </div>

        <DialogFooter className="flex-col sm:flex-col gap-2">
          <Button onClick={handleUpgrade} className="w-full" size="lg">
            <ArrowRight className="mr-2 h-4 w-4" />
            View Pricing Plans
          </Button>
          <Button
            variant="ghost"
            onClick={() => onOpenChange(false)}
            className="w-full"
          >
            Maybe Later
          </Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  );
}
