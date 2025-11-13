import { Sparkles, DollarSign, Zap, Shield } from "lucide-react";

interface WelcomeStepProps {
  onNext: () => void;
}

/**
 * Welcome Step - First onboarding step
 *
 * Introduces CutCosts and its benefits
 */
export function WelcomeStep({ onNext }: WelcomeStepProps) {
  const benefits = [
    {
      icon: DollarSign,
      title: "Save Money",
      description: "Detect wasteful cloud resources and reduce costs by up to 40%",
      gradient: "from-green-600 to-emerald-600",
    },
    {
      icon: Zap,
      title: "Lightning Fast",
      description: "Scan your entire cloud infrastructure in minutes, not hours",
      gradient: "from-yellow-600 to-orange-600",
    },
    {
      icon: Shield,
      title: "Secure & Read-Only",
      description: "We only read your cloud data - no write or delete permissions",
      gradient: "from-blue-600 to-purple-600",
    },
  ];

  return (
    <div className="text-center max-w-4xl mx-auto">
      {/* Hero section */}
      <div className="mb-8">
        <div className="inline-flex items-center justify-center h-20 w-20 rounded-2xl bg-gradient-to-br from-blue-600 via-purple-600 to-pink-600 shadow-2xl mb-6 animate-pulse">
          <Sparkles className="h-10 w-10 text-white" />
        </div>

        <h1 className="text-4xl md:text-5xl font-extrabold bg-gradient-to-r from-blue-600 via-purple-600 to-pink-600 bg-clip-text text-transparent mb-4">
          Welcome to CutCosts!
        </h1>

        <p className="text-xl text-gray-600 mb-2">
          Your Cloud Cost Optimization Platform
        </p>

        <p className="text-lg text-gray-500 max-w-2xl mx-auto">
          Automatically detect orphaned resources, unused services, and wasteful
          cloud spending across AWS, Azure, and GCP.
        </p>
      </div>

      {/* Benefits cards */}
      <div className="grid gap-6 md:grid-cols-3 mb-10">
        {benefits.map((benefit) => {
          const Icon = benefit.icon;
          return (
            <div
              key={benefit.title}
              className="group relative overflow-hidden rounded-2xl border-2 border-gray-200 bg-white p-6 transition-all hover:border-transparent hover:shadow-2xl hover:-translate-y-1"
            >
              <div
                className={`absolute inset-0 bg-gradient-to-br ${benefit.gradient} opacity-0 group-hover:opacity-5 transition-opacity`}
              ></div>

              <div className="relative z-10">
                <div
                  className={`inline-flex items-center justify-center h-12 w-12 rounded-xl bg-gradient-to-br ${benefit.gradient} shadow-lg mb-4`}
                >
                  <Icon className="h-6 w-6 text-white" />
                </div>

                <h3 className="text-lg font-bold text-gray-900 mb-2">
                  {benefit.title}
                </h3>

                <p className="text-sm text-gray-600">{benefit.description}</p>
              </div>
            </div>
          );
        })}
      </div>

      {/* Getting started preview */}
      <div className="rounded-2xl border-2 border-dashed border-blue-300 bg-blue-50/50 p-8 mb-8">
        <h2 className="text-2xl font-bold text-gray-900 mb-4">
          Get Started in 3 Simple Steps
        </h2>

        <div className="grid gap-4 md:grid-cols-3 text-left">
          <div className="flex items-start gap-3">
            <div className="flex h-8 w-8 items-center justify-center rounded-full bg-blue-600 text-white font-bold text-sm flex-shrink-0">
              1
            </div>
            <div>
              <h4 className="font-semibold text-gray-900 mb-1">
                Connect Account
              </h4>
              <p className="text-sm text-gray-600">
                Add your AWS, Azure, or GCP credentials
              </p>
            </div>
          </div>

          <div className="flex items-start gap-3">
            <div className="flex h-8 w-8 items-center justify-center rounded-full bg-purple-600 text-white font-bold text-sm flex-shrink-0">
              2
            </div>
            <div>
              <h4 className="font-semibold text-gray-900 mb-1">Run Scan</h4>
              <p className="text-sm text-gray-600">
                We'll analyze your cloud infrastructure
              </p>
            </div>
          </div>

          <div className="flex items-start gap-3">
            <div className="flex h-8 w-8 items-center justify-center rounded-full bg-pink-600 text-white font-bold text-sm flex-shrink-0">
              3
            </div>
            <div>
              <h4 className="font-semibold text-gray-900 mb-1">Save Money</h4>
              <p className="text-sm text-gray-600">
                Review findings and reduce waste
              </p>
            </div>
          </div>
        </div>
      </div>

      {/* CTA */}
      <button
        onClick={onNext}
        className="group inline-flex items-center gap-2 rounded-xl bg-gradient-to-r from-blue-600 to-purple-600 px-8 py-4 text-lg font-bold text-white shadow-lg hover:shadow-2xl transition-all hover:scale-105"
      >
        Let's Get Started!
        <Sparkles className="h-5 w-5 group-hover:rotate-12 transition-transform" />
      </button>

      <p className="mt-6 text-sm text-gray-500">
        Takes less than 5 minutes • No credit card required
      </p>
    </div>
  );
}
