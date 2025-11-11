import { Metadata } from "next";
import { OnboardingWizard } from "@/components/onboarding";

export const metadata: Metadata = {
  title: "Get Started | CloudWaste",
  description: "Welcome to CloudWaste - Let's get you set up to start detecting cloud waste",
};

/**
 * Onboarding Page
 *
 * Main onboarding wizard page that guides new users through setup
 */
export default function OnboardingPage() {
  return <OnboardingWizard />;
}
