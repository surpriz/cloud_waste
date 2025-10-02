import Link from "next/link";
import { Cloud, DollarSign, Search, Shield, TrendingDown, Zap, Lock, BarChart3 } from "lucide-react";

export default function Home() {
  return (
    <main className="flex min-h-screen flex-col">
      {/* Hero Section */}
      <div className="relative flex flex-1 flex-col items-center justify-center overflow-hidden bg-gradient-to-br from-blue-600 via-indigo-600 to-purple-700 px-4 py-32">
        {/* Animated background elements */}
        <div className="absolute inset-0 opacity-20">
          <div className="absolute top-1/4 left-1/4 h-96 w-96 rounded-full bg-white blur-3xl animate-pulse"></div>
          <div className="absolute bottom-1/4 right-1/4 h-96 w-96 rounded-full bg-blue-300 blur-3xl animate-pulse delay-1000"></div>
        </div>

        <div className="relative z-10 text-center max-w-5xl">
          <div className="inline-block mb-4 px-4 py-2 bg-white/10 backdrop-blur-sm rounded-full border border-white/20">
            <span className="text-white/90 text-sm font-medium">🚀 Save up to 40% on your cloud costs</span>
          </div>

          <h1 className="text-7xl md:text-8xl font-extrabold text-white mb-6 leading-tight">
            Cloud<span className="bg-gradient-to-r from-yellow-300 to-orange-400 bg-clip-text text-transparent">Waste</span>
          </h1>

          <p className="mt-6 text-2xl md:text-3xl text-blue-100 max-w-3xl mx-auto font-light">
            Detect orphaned AWS resources automatically and
            <span className="font-semibold text-white"> slash your cloud bills</span>
          </p>

          <div className="mt-12 flex flex-col sm:flex-row gap-4 justify-center items-center">
            <Link
              href="/auth/register"
              className="group relative inline-flex items-center gap-3 rounded-xl bg-white px-10 py-4 text-lg font-bold text-blue-600 transition-all hover:scale-105 hover:shadow-2xl shadow-xl"
            >
              <Zap className="h-5 w-5 group-hover:text-yellow-500 transition-colors" />
              Start Free Trial
              <div className="absolute -top-1 -right-1 h-3 w-3 bg-green-400 rounded-full animate-ping"></div>
            </Link>
            <Link
              href="/auth/login"
              className="inline-flex items-center gap-3 rounded-xl border-2 border-white/30 bg-white/10 backdrop-blur-sm px-10 py-4 text-lg font-semibold text-white transition-all hover:bg-white/20 hover:border-white/50"
            >
              Sign In
            </Link>
          </div>

          <div className="mt-16 flex flex-wrap justify-center gap-8 text-white/90">
            <div className="flex items-center gap-2">
              <Shield className="h-5 w-5 text-green-300" />
              <span className="text-sm">100% Read-Only</span>
            </div>
            <div className="flex items-center gap-2">
              <Lock className="h-5 w-5 text-green-300" />
              <span className="text-sm">Bank-Level Security</span>
            </div>
            <div className="flex items-center gap-2">
              <Zap className="h-5 w-5 text-yellow-300" />
              <span className="text-sm">Setup in 2 Minutes</span>
            </div>
          </div>
        </div>
      </div>

      {/* Stats Section */}
      <div className="bg-gradient-to-b from-white to-gray-50 px-4 py-20">
        <div className="mx-auto max-w-6xl">
          <div className="grid gap-8 md:grid-cols-3 mb-20">
            <div className="text-center p-8 rounded-2xl bg-white shadow-lg border border-gray-100">
              <div className="text-5xl font-extrabold text-blue-600">$2.4M+</div>
              <div className="mt-2 text-gray-600 font-medium">Saved by Users</div>
            </div>
            <div className="text-center p-8 rounded-2xl bg-white shadow-lg border border-gray-100">
              <div className="text-5xl font-extrabold text-blue-600">50K+</div>
              <div className="mt-2 text-gray-600 font-medium">Resources Detected</div>
            </div>
            <div className="text-center p-8 rounded-2xl bg-white shadow-lg border border-gray-100">
              <div className="text-5xl font-extrabold text-blue-600">99.9%</div>
              <div className="mt-2 text-gray-600 font-medium">Uptime SLA</div>
            </div>
          </div>

          <div className="text-center mb-16">
            <h2 className="text-4xl md:text-5xl font-bold text-gray-900 mb-4">
              Powerful Features for
              <span className="bg-gradient-to-r from-blue-600 to-purple-600 bg-clip-text text-transparent"> Cost Optimization</span>
            </h2>
            <p className="text-xl text-gray-600 max-w-2xl mx-auto">
              Everything you need to detect and eliminate cloud waste across your infrastructure
            </p>
          </div>

          <div className="grid gap-8 md:grid-cols-2 lg:grid-cols-4">
            <FeatureCard
              icon={Search}
              title="Auto Scan"
              description="Automatically detect 7 types of orphaned AWS resources"
              gradient="from-blue-500 to-blue-600"
            />
            <FeatureCard
              icon={DollarSign}
              title="Cost Analysis"
              description="Calculate exact monthly and annual savings potential"
              gradient="from-green-500 to-emerald-600"
            />
            <FeatureCard
              icon={Shield}
              title="Read-Only"
              description="100% safe - we only read, never delete your resources"
              gradient="from-purple-500 to-purple-600"
            />
            <FeatureCard
              icon={Cloud}
              title="Multi-Account"
              description="Manage multiple AWS accounts from one dashboard"
              gradient="from-orange-500 to-red-600"
            />
          </div>
        </div>
      </div>

      {/* How It Works Section */}
      <div className="bg-gray-50 px-4 py-24">
        <div className="mx-auto max-w-6xl">
          <div className="text-center mb-16">
            <h2 className="text-4xl font-bold text-gray-900 mb-4">
              Get Started in 3 Simple Steps
            </h2>
            <p className="text-xl text-gray-600">
              Start saving on your cloud costs in minutes, not hours
            </p>
          </div>

          <div className="grid gap-8 md:grid-cols-3">
            <div className="relative bg-white p-8 rounded-2xl shadow-lg border border-gray-100">
              <div className="absolute -top-4 -left-4 h-12 w-12 bg-gradient-to-br from-blue-600 to-blue-700 rounded-xl flex items-center justify-center text-white font-bold text-xl shadow-lg">
                1
              </div>
              <div className="mt-4">
                <h3 className="text-xl font-bold text-gray-900 mb-3">Connect Your AWS Account</h3>
                <p className="text-gray-600">
                  Add your AWS credentials with read-only permissions. We never modify or delete anything.
                </p>
              </div>
            </div>

            <div className="relative bg-white p-8 rounded-2xl shadow-lg border border-gray-100">
              <div className="absolute -top-4 -left-4 h-12 w-12 bg-gradient-to-br from-purple-600 to-purple-700 rounded-xl flex items-center justify-center text-white font-bold text-xl shadow-lg">
                2
              </div>
              <div className="mt-4">
                <h3 className="text-xl font-bold text-gray-900 mb-3">Run Automatic Scan</h3>
                <p className="text-gray-600">
                  Our AI-powered scanner analyzes your infrastructure and identifies orphaned resources.
                </p>
              </div>
            </div>

            <div className="relative bg-white p-8 rounded-2xl shadow-lg border border-gray-100">
              <div className="absolute -top-4 -left-4 h-12 w-12 bg-gradient-to-br from-green-600 to-green-700 rounded-xl flex items-center justify-center text-white font-bold text-xl shadow-lg">
                3
              </div>
              <div className="mt-4">
                <h3 className="text-xl font-bold text-gray-900 mb-3">Review & Save Money</h3>
                <p className="text-gray-600">
                  Get detailed cost reports and recommendations to eliminate waste and reduce your bills.
                </p>
              </div>
            </div>
          </div>
        </div>
      </div>

      {/* CTA Section */}
      <div className="relative bg-gradient-to-r from-blue-600 via-purple-600 to-indigo-700 px-4 py-24 overflow-hidden">
        <div className="absolute inset-0 opacity-10">
          <div className="absolute top-0 right-0 h-96 w-96 rounded-full bg-white blur-3xl"></div>
          <div className="absolute bottom-0 left-0 h-96 w-96 rounded-full bg-yellow-300 blur-3xl"></div>
        </div>

        <div className="relative z-10 mx-auto max-w-4xl text-center">
          <h2 className="text-4xl md:text-5xl font-extrabold text-white mb-6">
            Ready to Cut Your Cloud Costs?
          </h2>
          <p className="mt-4 text-xl md:text-2xl text-blue-100 max-w-2xl mx-auto">
            Join hundreds of companies saving thousands of dollars monthly by eliminating cloud waste
          </p>
          <div className="mt-10 flex flex-col sm:flex-row gap-4 justify-center">
            <Link
              href="/auth/register"
              className="group inline-flex items-center justify-center gap-3 rounded-xl bg-white px-10 py-4 text-lg font-bold text-blue-600 transition-all hover:scale-105 hover:shadow-2xl"
            >
              <TrendingDown className="h-5 w-5 group-hover:text-green-600 transition-colors" />
              Start Saving Now - It's Free
            </Link>
            <Link
              href="/dashboard"
              className="inline-flex items-center justify-center gap-3 rounded-xl border-2 border-white bg-transparent px-10 py-4 text-lg font-semibold text-white transition-all hover:bg-white hover:text-blue-600"
            >
              <BarChart3 className="h-5 w-5" />
              View Demo Dashboard
            </Link>
          </div>

          <div className="mt-12 flex flex-wrap justify-center gap-6 text-white/80 text-sm">
            <span>✓ No credit card required</span>
            <span>✓ Setup in under 2 minutes</span>
            <span>✓ Cancel anytime</span>
          </div>
        </div>
      </div>

      {/* Footer */}
      <footer className="bg-gray-900 px-4 py-12 text-gray-400">
        <div className="mx-auto max-w-6xl text-center">
          <p>&copy; 2025 CloudWaste. Built with FastAPI & Next.js.</p>
          <div className="mt-4 flex justify-center gap-6">
            <a
              href="http://localhost:8000/api/docs"
              target="_blank"
              rel="noopener noreferrer"
              className="hover:text-white transition-colors"
            >
              API Docs
            </a>
            <a href="/dashboard" className="hover:text-white transition-colors">
              Dashboard
            </a>
          </div>
        </div>
      </footer>
    </main>
  );
}

function FeatureCard({ icon: Icon, title, description, gradient }: any) {
  return (
    <div className="group relative rounded-2xl border border-gray-200 bg-white p-8 text-center transition-all hover:border-transparent hover:shadow-2xl hover:-translate-y-2">
      <div className={`absolute inset-0 rounded-2xl bg-gradient-to-br ${gradient} opacity-0 group-hover:opacity-100 transition-opacity`}></div>

      <div className="relative z-10">
        <div className={`mx-auto flex h-16 w-16 items-center justify-center rounded-2xl bg-gradient-to-br ${gradient} shadow-lg`}>
          <Icon className="h-8 w-8 text-white" />
        </div>
        <h3 className="mt-6 text-xl font-bold text-gray-900 group-hover:text-white transition-colors">{title}</h3>
        <p className="mt-3 text-gray-600 group-hover:text-white/90 transition-colors">{description}</p>
      </div>
    </div>
  );
}
