"use client";

import { useEffect, useState } from "react";
import { useRouter, useSearchParams } from "next/navigation";
import { CheckCircle, Loader2, ArrowRight } from "lucide-react";
import { Button } from "@/components/ui/button";
import {
  Card,
  CardContent,
  CardDescription,
  CardFooter,
  CardHeader,
  CardTitle,
} from "@/components/ui/card";
import useSubscriptionStore from "@/stores/useSubscriptionStore";

export default function PaymentSuccessContent() {
  const router = useRouter();
  const searchParams = useSearchParams();
  const { fetchCurrentSubscription } = useSubscriptionStore();
  const [isLoading, setIsLoading] = useState(true);

  useEffect(() => {
    // Refresh subscription data after successful payment
    const refreshData = async () => {
      // Wait a bit for webhook to process
      await new Promise((resolve) => setTimeout(resolve, 2000));
      await fetchCurrentSubscription();
      setIsLoading(false);
    };

    refreshData();
  }, []);

  const sessionId = searchParams.get("session_id");

  if (isLoading) {
    return (
      <div className="min-h-screen flex items-center justify-center bg-gradient-to-b from-green-50 to-white">
        <Card className="w-full max-w-md">
          <CardContent className="pt-6 flex flex-col items-center gap-4">
            <Loader2 className="h-12 w-12 animate-spin text-green-600" />
            <p className="text-lg font-medium text-gray-700">
              Processing your payment...
            </p>
            <p className="text-sm text-gray-500 text-center">
              Please wait while we confirm your subscription
            </p>
          </CardContent>
        </Card>
      </div>
    );
  }

  return (
    <div className="min-h-screen flex items-center justify-center bg-gradient-to-b from-green-50 to-white p-4">
      <Card className="w-full max-w-md">
        <CardHeader className="text-center">
          <div className="mx-auto mb-4 flex h-16 w-16 items-center justify-center rounded-full bg-green-100">
            <CheckCircle className="h-10 w-10 text-green-600" />
          </div>
          <CardTitle className="text-2xl">Payment Successful!</CardTitle>
          <CardDescription>
            Your subscription has been activated successfully
          </CardDescription>
        </CardHeader>

        <CardContent className="space-y-4">
          <div className="rounded-lg bg-green-50 p-4 border border-green-200">
            <p className="text-sm text-green-800 text-center">
              🎉 Welcome to CutCosts Premium! You now have access to all premium
              features.
            </p>
          </div>

          {sessionId && (
            <div className="text-center">
              <p className="text-xs text-gray-500">Session ID</p>
              <p className="text-xs font-mono text-gray-600 break-all">
                {sessionId}
              </p>
            </div>
          )}

          <div className="space-y-2">
            <h3 className="font-semibold text-sm text-gray-900">
              What's next?
            </h3>
            <ul className="space-y-2 text-sm text-gray-600">
              <li className="flex items-start gap-2">
                <ArrowRight className="h-4 w-4 mt-0.5 text-green-600 flex-shrink-0" />
                <span>Access AI Chat Assistant for intelligent insights</span>
              </li>
              <li className="flex items-start gap-2">
                <ArrowRight className="h-4 w-4 mt-0.5 text-green-600 flex-shrink-0" />
                <span>
                  Run unlimited scans to detect all orphaned resources
                </span>
              </li>
              <li className="flex items-start gap-2">
                <ArrowRight className="h-4 w-4 mt-0.5 text-green-600 flex-shrink-0" />
                <span>Track environmental impact of your savings</span>
              </li>
              <li className="flex items-start gap-2">
                <ArrowRight className="h-4 w-4 mt-0.5 text-green-600 flex-shrink-0" />
                <span>Manage your subscription anytime in Settings</span>
              </li>
            </ul>
          </div>

          <div className="pt-4 space-y-2 text-center text-sm text-gray-600">
            <p>A confirmation email has been sent to your inbox.</p>
            <p>
              You can manage your subscription and billing details in your
              account settings.
            </p>
          </div>
        </CardContent>

        <CardFooter className="flex flex-col gap-2">
          <Button
            className="w-full"
            size="lg"
            onClick={() => router.push("/dashboard")}
          >
            Go to Dashboard
          </Button>
          <Button
            variant="outline"
            className="w-full"
            onClick={() => router.push("/dashboard/subscription")}
          >
            View Subscription Details
          </Button>
        </CardFooter>
      </Card>
    </div>
  );
}
