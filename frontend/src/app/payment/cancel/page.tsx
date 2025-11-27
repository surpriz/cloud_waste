"use client";

import { useRouter } from "next/navigation";
import { XCircle, ArrowLeft, HelpCircle } from "lucide-react";
import { Button } from "@/components/ui/button";
import {
  Card,
  CardContent,
  CardDescription,
  CardFooter,
  CardHeader,
  CardTitle,
} from "@/components/ui/card";

export default function PaymentCancelPage() {
  const router = useRouter();

  return (
    <div className="min-h-screen flex items-center justify-center bg-gradient-to-b from-orange-50 to-white p-4">
      <Card className="w-full max-w-md">
        <CardHeader className="text-center">
          <div className="mx-auto mb-4 flex h-16 w-16 items-center justify-center rounded-full bg-orange-100">
            <XCircle className="h-10 w-10 text-orange-600" />
          </div>
          <CardTitle className="text-2xl">Payment Cancelled</CardTitle>
          <CardDescription>
            Your subscription payment was not completed
          </CardDescription>
        </CardHeader>

        <CardContent className="space-y-4">
          <div className="rounded-lg bg-orange-50 p-4 border border-orange-200">
            <p className="text-sm text-orange-800 text-center">
              No charges have been made to your account
            </p>
          </div>

          <div className="space-y-3">
            <p className="text-sm text-gray-600 text-center">
              You cancelled the payment process. Don't worry, you can try again
              anytime!
            </p>

            <div className="space-y-2 pt-2">
              <h3 className="font-semibold text-sm text-gray-900 flex items-center gap-2">
                <HelpCircle className="h-4 w-4" />
                Need help?
              </h3>
              <ul className="space-y-2 text-sm text-gray-600 pl-6">
                <li className="list-disc">
                  If you encountered any issues during checkout, please contact
                  support
                </li>
                <li className="list-disc">
                  You can continue using the Free plan with limited features
                </li>
                <li className="list-disc">
                  Upgrade anytime to unlock all premium features
                </li>
              </ul>
            </div>
          </div>

          <div className="pt-4 space-y-2">
            <h3 className="font-semibold text-sm text-gray-900">
              Why upgrade to Premium?
            </h3>
            <ul className="space-y-2 text-sm text-gray-600">
              <li className="flex items-start gap-2">
                <span className="text-green-600">✓</span>
                <span>Unlimited scans per month</span>
              </li>
              <li className="flex items-start gap-2">
                <span className="text-green-600">✓</span>
                <span>AI-powered insights and recommendations</span>
              </li>
              <li className="flex items-start gap-2">
                <span className="text-green-600">✓</span>
                <span>Environmental impact tracking</span>
              </li>
              <li className="flex items-start gap-2">
                <span className="text-green-600">✓</span>
                <span>Priority support</span>
              </li>
            </ul>
          </div>
        </CardContent>

        <CardFooter className="flex flex-col gap-2">
          <Button
            className="w-full"
            size="lg"
            onClick={() => router.push("/pricing")}
          >
            <ArrowLeft className="mr-2 h-4 w-4" />
            Back to Pricing
          </Button>
          <Button
            variant="outline"
            className="w-full"
            onClick={() => router.push("/dashboard")}
          >
            Continue with Free Plan
          </Button>
        </CardFooter>
      </Card>
    </div>
  );
}
