"use client";

import { useState } from "react";
import { Cloud, Check, ArrowRight, ExternalLink } from "lucide-react";
import Link from "next/link";
import { useAccountStore } from "@/stores/useAccountStore";

interface AddAccountStepProps {
  onNext: () => void;
  onSkip: () => void;
}

/**
 * Add Account Step - Second onboarding step
 *
 * Guides user to connect their first cloud account
 */
export function AddAccountStep({ onNext, onSkip }: AddAccountStepProps) {
  const { accounts } = useAccountStore();
  const [selectedProvider, setSelectedProvider] = useState<
    "aws" | "azure" | "gcp" | null
  >(null);

  const hasAccounts = accounts.length > 0;

  const providers = [
    {
      id: "aws" as const,
      name: "Amazon Web Services",
      logo: "🟧",
      description: "Detect orphaned EBS volumes, snapshots, EC2 instances, and more",
      popular: true,
    },
    {
      id: "azure" as const,
      name: "Microsoft Azure",
      logo: "🔷",
      description: "Find unattached disks, unused VMs, and orphaned resources",
      popular: false,
    },
    {
      id: "gcp" as const,
      name: "Google Cloud Platform",
      logo: "🔴",
      description: "Identify idle compute instances and unused storage",
      popular: false,
    },
  ];

  return (
    <div className="text-center max-w-4xl mx-auto">
      {/* Header */}
      <div className="mb-8">
        <div className="inline-flex items-center justify-center h-16 w-16 rounded-2xl bg-gradient-to-br from-blue-600 to-cyan-600 shadow-lg mb-4">
          <Cloud className="h-8 w-8 text-white" />
        </div>

        <h2 className="text-3xl md:text-4xl font-extrabold text-gray-900 mb-3">
          Connect Your First Cloud Account
        </h2>

        <p className="text-lg text-gray-600">
          Choose your cloud provider to get started detecting waste
        </p>
      </div>

      {/* Already has accounts */}
      {hasAccounts && (
        <div className="mb-8 rounded-2xl border-2 border-green-300 bg-green-50 p-6">
          <div className="flex items-center justify-center gap-3 mb-3">
            <div className="flex h-10 w-10 items-center justify-center rounded-full bg-green-600">
              <Check className="h-6 w-6 text-white" />
            </div>
            <h3 className="text-xl font-bold text-green-900">
              Account Connected!
            </h3>
          </div>

          <p className="text-green-700 mb-4">
            You've successfully connected {accounts.length} cloud{" "}
            {accounts.length === 1 ? "account" : "accounts"}. You're ready to
            run your first scan!
          </p>

          <button
            onClick={onNext}
            className="inline-flex items-center gap-2 rounded-xl bg-green-600 px-6 py-3 font-semibold text-white hover:bg-green-700 transition-colors"
          >
            Continue to Next Step
            <ArrowRight className="h-5 w-5" />
          </button>
        </div>
      )}

      {/* Provider selection */}
      {!hasAccounts && (
        <>
          <div className="grid gap-4 md:grid-cols-3 mb-8">
            {providers.map((provider) => (
              <button
                key={provider.id}
                onClick={() => setSelectedProvider(provider.id)}
                className={`
                  group relative overflow-hidden rounded-2xl border-2 p-6 text-left transition-all
                  ${
                    selectedProvider === provider.id
                      ? "border-blue-600 bg-blue-50 shadow-lg"
                      : "border-gray-300 bg-white hover:border-blue-400 hover:shadow-md"
                  }
                `}
              >
                {provider.popular && (
                  <div className="absolute top-3 right-3">
                    <span className="inline-flex items-center rounded-full bg-blue-600 px-2 py-1 text-xs font-semibold text-white">
                      Popular
                    </span>
                  </div>
                )}

                <div className="text-4xl mb-3">{provider.logo}</div>

                <h3 className="text-lg font-bold text-gray-900 mb-2">
                  {provider.name}
                </h3>

                <p className="text-sm text-gray-600 mb-4">
                  {provider.description}
                </p>

                {selectedProvider === provider.id && (
                  <div className="flex items-center gap-2 text-blue-600 font-semibold text-sm">
                    <Check className="h-4 w-4" />
                    Selected
                  </div>
                )}
              </button>
            ))}
          </div>

          {/* Call to action */}
          <div className="rounded-2xl border border-gray-200 bg-gray-50 p-8">
            <h3 className="text-xl font-bold text-gray-900 mb-3">
              Ready to Connect?
            </h3>

            <p className="text-gray-600 mb-6">
              You'll be redirected to the account setup page where you can
              securely add your cloud credentials.
            </p>

            <div className="flex flex-col sm:flex-row gap-4 justify-center">
              <Link
                href="/dashboard/accounts"
                className="inline-flex items-center justify-center gap-2 rounded-xl bg-gradient-to-r from-blue-600 to-purple-600 px-6 py-3 font-semibold text-white shadow-lg hover:shadow-xl transition-all hover:scale-105"
              >
                <Cloud className="h-5 w-5" />
                Go to Account Setup
                <ExternalLink className="h-4 w-4" />
              </Link>

              <button
                onClick={onSkip}
                className="inline-flex items-center justify-center gap-2 rounded-xl border-2 border-gray-300 bg-white px-6 py-3 font-semibold text-gray-700 hover:bg-gray-50 transition-colors"
              >
                I'll Do This Later
              </button>
            </div>
          </div>

          {/* Security note */}
          <div className="mt-6 rounded-xl bg-blue-50 border border-blue-200 p-4">
            <p className="text-sm text-blue-800">
              🔒 <strong>Security First:</strong> We only request read-only
              permissions. Your credentials are encrypted and never stored in
              plain text.
            </p>
          </div>
        </>
      )}
    </div>
  );
}
