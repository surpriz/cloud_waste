"use client";

import { useEffect } from "react";
import { useRouter } from "next/navigation";
import {
  AlertCircle,
  ArrowUpRight,
  Calendar,
  Check,
  CreditCard,
  Loader2,
  TrendingUp,
  Zap,
} from "lucide-react";
import { Button } from "@/components/ui/button";
import {
  Card,
  CardContent,
  CardDescription,
  CardFooter,
  CardHeader,
  CardTitle,
} from "@/components/ui/card";
import { Progress } from "@/components/ui/progress";
import { Separator } from "@/components/ui/separator";
import useSubscriptionStore from "@/stores/useSubscriptionStore";

export default function SubscriptionPage() {
  const router = useRouter();
  const {
    currentSubscription,
    isLoadingSubscription,
    subscriptionError,
    fetchCurrentSubscription,
    openCustomerPortal,
    getScanUsage,
  } = useSubscriptionStore();

  useEffect(() => {
    fetchCurrentSubscription();
  }, []);

  const handleManageSubscription = async () => {
    try {
      await openCustomerPortal(`${window.location.origin}/dashboard/subscription`);
    } catch (error) {
      console.error("Error opening customer portal:", error);
    }
  };

  const handleUpgrade = () => {
    router.push("/pricing");
  };

  if (isLoadingSubscription) {
    return (
      <div className="flex items-center justify-center min-h-screen">
        <Loader2 className="h-8 w-8 animate-spin text-blue-600" />
      </div>
    );
  }

  if (subscriptionError) {
    return (
      <div className="flex flex-col items-center justify-center min-h-screen gap-4">
        <AlertCircle className="h-12 w-12 text-red-500" />
        <p className="text-lg text-gray-600">{subscriptionError}</p>
        <Button onClick={() => fetchCurrentSubscription()}>Try Again</Button>
      </div>
    );
  }

  if (!currentSubscription) {
    return (
      <div className="flex flex-col items-center justify-center min-h-screen gap-4">
        <AlertCircle className="h-12 w-12 text-yellow-500" />
        <p className="text-lg text-gray-600">No active subscription found</p>
        <Button onClick={() => router.push("/pricing")}>View Plans</Button>
      </div>
    );
  }

  const { plan, status, current_period_end, cancel_at_period_end } =
    currentSubscription;
  const scanUsage = getScanUsage();
  const scanPercentage =
    scanUsage.limit !== null
      ? (scanUsage.used / scanUsage.limit) * 100
      : 0;

  const isFree = plan.name === "free";
  const isPro = plan.name === "pro";
  const isEnterprise = plan.name === "enterprise";

  return (
    <div className="container mx-auto p-6 max-w-6xl">
      <div className="mb-8">
        <h1 className="text-3xl font-bold mb-2">Subscription</h1>
        <p className="text-gray-600">
          Manage your subscription and billing settings
        </p>
      </div>

      <div className="grid gap-6 md:grid-cols-2">
        {/* Current Plan */}
        <Card>
          <CardHeader>
            <CardTitle className="flex items-center gap-2">
              <Zap className="h-5 w-5 text-blue-600" />
              Current Plan
            </CardTitle>
            <CardDescription>Your active subscription plan</CardDescription>
          </CardHeader>
          <CardContent className="space-y-4">
            <div className="flex items-baseline gap-3">
              <span className="text-3xl font-bold">{plan.display_name}</span>
              <span
                className={`px-2 py-1 text-xs font-semibold rounded ${
                  status === "active"
                    ? "bg-green-100 text-green-700"
                    : status === "canceled"
                      ? "bg-red-100 text-red-700"
                      : "bg-yellow-100 text-yellow-700"
                }`}
              >
                {status}
              </span>
            </div>

            <Separator />

            <div className="space-y-2">
              <div className="flex justify-between">
                <span className="text-sm text-gray-600">Price</span>
                <span className="font-semibold">
                  €{Number(plan.price_monthly).toFixed(0)}/month
                </span>
              </div>

              {current_period_end && (
                <div className="flex justify-between">
                  <span className="text-sm text-gray-600">Next billing date</span>
                  <span className="font-semibold">
                    {new Date(current_period_end).toLocaleDateString()}
                  </span>
                </div>
              )}

              {cancel_at_period_end && (
                <div className="flex items-start gap-2 p-3 bg-yellow-50 border border-yellow-200 rounded">
                  <AlertCircle className="h-4 w-4 text-yellow-600 mt-0.5" />
                  <p className="text-sm text-yellow-800">
                    Your subscription will cancel at the end of the current
                    period.
                  </p>
                </div>
              )}
            </div>
          </CardContent>
          <CardFooter className="flex gap-2">
            {!isFree && (
              <Button
                onClick={handleManageSubscription}
                className="flex-1"
                variant="outline"
              >
                <CreditCard className="mr-2 h-4 w-4" />
                Manage Billing
              </Button>
            )}
            {!isEnterprise && (
              <Button onClick={handleUpgrade} className="flex-1">
                <TrendingUp className="mr-2 h-4 w-4" />
                Upgrade
              </Button>
            )}
          </CardFooter>
        </Card>

        {/* Usage Statistics */}
        <Card>
          <CardHeader>
            <CardTitle className="flex items-center gap-2">
              <TrendingUp className="h-5 w-5 text-green-600" />
              Usage Statistics
            </CardTitle>
            <CardDescription>Your current month's usage</CardDescription>
          </CardHeader>
          <CardContent className="space-y-6">
            {/* Scans Usage */}
            <div className="space-y-2">
              <div className="flex justify-between text-sm">
                <span className="font-medium">Scans</span>
                <span className="text-gray-600">
                  {scanUsage.used} / {scanUsage.limit ?? "∞"} used
                </span>
              </div>
              {scanUsage.limit !== null ? (
                <>
                  <Progress value={scanPercentage} className="h-2" />
                  {scanPercentage >= 80 && (
                    <p className="text-sm text-orange-600">
                      You're approaching your scan limit. Consider upgrading!
                    </p>
                  )}
                </>
              ) : (
                <div className="flex items-center gap-2 text-sm text-green-600">
                  <Check className="h-4 w-4" />
                  Unlimited scans available
                </div>
              )}
            </div>

            <Separator />

            {/* Cloud Accounts */}
            <div className="space-y-2">
              <div className="flex justify-between text-sm">
                <span className="font-medium">Cloud Accounts</span>
                <span className="text-gray-600">
                  Limit: {plan.max_cloud_accounts ?? "∞"}
                </span>
              </div>
              {plan.max_cloud_accounts === null && (
                <div className="flex items-center gap-2 text-sm text-green-600">
                  <Check className="h-4 w-4" />
                  Unlimited accounts available
                </div>
              )}
            </div>
          </CardContent>
        </Card>

        {/* Plan Features */}
        <Card className="md:col-span-2">
          <CardHeader>
            <CardTitle>Plan Features</CardTitle>
            <CardDescription>
              What's included in your {plan.display_name} plan
            </CardDescription>
          </CardHeader>
          <CardContent>
            <div className="grid md:grid-cols-2 gap-4">
              <FeatureItem
                enabled={true}
                text={`${plan.max_scans_per_month ?? "Unlimited"} scans per month`}
              />
              <FeatureItem
                enabled={true}
                text={`Up to ${plan.max_cloud_accounts ?? "unlimited"} cloud accounts`}
              />
              <FeatureItem
                enabled={plan.has_ai_chat}
                text="AI Chat Assistant"
              />
              <FeatureItem
                enabled={plan.has_impact_tracking}
                text="Environmental Impact Tracking"
              />
              <FeatureItem
                enabled={plan.has_email_notifications}
                text="Email Notifications"
              />
              <FeatureItem enabled={plan.has_api_access} text="API Access" />
              <FeatureItem
                enabled={plan.has_priority_support}
                text="Priority Support"
              />
              <FeatureItem enabled={true} text="Orphaned Resource Detection" />
              <FeatureItem enabled={true} text="Cost Optimization Insights" />
              <FeatureItem enabled={true} text="Multi-Cloud Support" />
            </div>
          </CardContent>
          {!isEnterprise && (
            <CardFooter>
              <Button onClick={handleUpgrade} className="w-full" size="lg">
                <ArrowUpRight className="mr-2 h-4 w-4" />
                Upgrade to unlock all features
              </Button>
            </CardFooter>
          )}
        </Card>
      </div>
    </div>
  );
}

function FeatureItem({ enabled, text }: { enabled: boolean; text: string }) {
  return (
    <div className="flex items-center gap-2">
      {enabled ? (
        <Check className="h-5 w-5 text-green-600 flex-shrink-0" />
      ) : (
        <div className="h-5 w-5 rounded-full border-2 border-gray-300 flex-shrink-0" />
      )}
      <span className={enabled ? "text-gray-900" : "text-gray-400"}>
        {text}
      </span>
    </div>
  );
}
