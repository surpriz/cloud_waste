import Link from "next/link";
import { ArrowLeft, Shield, FileText, Cookie, Scale } from "lucide-react";

export default function LegalLayout({
  children,
}: {
  children: React.ReactNode;
}) {
  const legalPages = [
    { href: "/legal/privacy", label: "Privacy Policy", icon: Shield },
    { href: "/legal/terms", label: "Terms of Service", icon: FileText },
    { href: "/legal/cookies", label: "Cookie Policy", icon: Cookie },
    { href: "/legal/legal-notice", label: "Legal Notice", icon: Scale },
  ];

  return (
    <div className="min-h-screen bg-gradient-to-br from-gray-50 to-gray-100">
      {/* Header */}
      <header className="bg-white border-b border-gray-200 sticky top-0 z-50 shadow-sm">
        <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8">
          <div className="flex items-center justify-between h-16">
            <Link
              href="/"
              className="flex items-center gap-2 text-gray-600 hover:text-gray-900 transition-colors"
            >
              <ArrowLeft className="w-4 h-4" />
              <span className="font-medium">Back to Home</span>
            </Link>

            <Link
              href="/"
              className="text-2xl font-bold bg-gradient-to-r from-blue-600 to-indigo-600 bg-clip-text text-transparent"
            >
              CutCosts
            </Link>
          </div>
        </div>
      </header>

      {/* Main content */}
      <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-12">
        <div className="grid grid-cols-1 lg:grid-cols-4 gap-8">
          {/* Sidebar navigation */}
          <aside className="lg:col-span-1">
            <nav className="bg-white rounded-xl shadow-sm border border-gray-200 p-4 sticky top-24">
              <h3 className="text-sm font-semibold text-gray-900 mb-4 px-2">
                Legal Documents
              </h3>
              <ul className="space-y-1">
                {legalPages.map(({ href, label, icon: Icon }) => (
                  <li key={href}>
                    <Link
                      href={href}
                      className="flex items-center gap-3 px-3 py-2 rounded-lg text-gray-700 hover:bg-blue-50 hover:text-blue-600 transition-colors group"
                    >
                      <Icon className="w-4 h-4 text-gray-400 group-hover:text-blue-600" />
                      <span className="text-sm font-medium">{label}</span>
                    </Link>
                  </li>
                ))}
              </ul>

              <div className="mt-6 pt-6 border-t border-gray-200">
                <p className="text-xs text-gray-500 px-2">
                  Last updated: January 2025
                </p>
              </div>
            </nav>
          </aside>

          {/* Content */}
          <main className="lg:col-span-3">
            <div className="bg-white rounded-xl shadow-sm border border-gray-200 p-8 md:p-12">
              {children}
            </div>
          </main>
        </div>
      </div>
    </div>
  );
}
