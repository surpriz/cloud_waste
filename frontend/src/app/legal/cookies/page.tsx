import type { Metadata } from "next";
import { Cookie, Check, X, Settings, AlertCircle } from "lucide-react";

export const metadata: Metadata = {
  title: "Cookie Policy - CutCosts | GDPR Compliant",
  description:
    "CutCosts Cookie Policy - Learn about the cookies we use, their purpose, and how to manage your preferences.",
};

export default function CookiePolicyPage() {
  return (
    <div className="prose prose-gray max-w-none">
      {/* Header */}
      <div className="not-prose mb-8">
        <div className="flex items-center gap-3 mb-4">
          <Cookie className="w-8 h-8 text-blue-600" />
          <h1 className="text-4xl font-bold text-gray-900">Cookie Policy</h1>
        </div>
        <p className="text-gray-600 text-lg">
          Last updated: <strong>January 2025</strong>
        </p>
        <p className="text-gray-600 mt-2">
          This Cookie Policy explains how CutCosts uses cookies and similar tracking technologies on our website
          and application.
        </p>
      </div>

      {/* Quick Summary */}
      <div className="not-prose bg-blue-50 border border-blue-200 rounded-lg p-6 mb-8">
        <h3 className="text-lg font-semibold text-blue-900 mb-3">Quick Summary</h3>
        <ul className="space-y-2 text-sm text-blue-800">
          <li>
            <strong>✓ Essential cookies:</strong> Required for authentication and security (cannot be disabled)
          </li>
          <li>
            <strong>✓ Functional cookies:</strong> Remember your preferences (theme, language)
          </li>
          <li>
            <strong>✓ Analytics cookies:</strong> Help us improve the service (optional, requires consent)
          </li>
          <li>
            <strong>✗ Advertising cookies:</strong> We do not use advertising or tracking cookies
          </li>
        </ul>
        <p className="text-sm text-blue-700 mt-4">
          You can manage your cookie preferences at any time by clicking "Cookie Settings" in the footer.
        </p>
      </div>

      {/* Table of Contents */}
      <nav className="not-prose bg-gray-50 rounded-lg p-6 mb-8">
        <h2 className="text-lg font-semibold text-gray-900 mb-4">Table of Contents</h2>
        <ol className="space-y-2 text-sm">
          <li>
            <a href="#what-are-cookies" className="text-blue-600 hover:underline">
              1. What Are Cookies?
            </a>
          </li>
          <li>
            <a href="#why-we-use-cookies" className="text-blue-600 hover:underline">
              2. Why We Use Cookies
            </a>
          </li>
          <li>
            <a href="#types-of-cookies" className="text-blue-600 hover:underline">
              3. Types of Cookies We Use
            </a>
          </li>
          <li>
            <a href="#third-party-cookies" className="text-blue-600 hover:underline">
              4. Third-Party Cookies
            </a>
          </li>
          <li>
            <a href="#manage-cookies" className="text-blue-600 hover:underline">
              5. How to Manage Cookies
            </a>
          </li>
          <li>
            <a href="#updates" className="text-blue-600 hover:underline">
              6. Updates to This Policy
            </a>
          </li>
          <li>
            <a href="#contact" className="text-blue-600 hover:underline">
              7. Contact Us
            </a>
          </li>
        </ol>
      </nav>

      {/* 1. What Are Cookies */}
      <section id="what-are-cookies" className="mb-12">
        <h2 className="text-2xl font-bold text-gray-900 mb-4">1. What Are Cookies?</h2>
        <p>
          Cookies are small text files that are placed on your device (computer, smartphone, tablet) when you visit a
          website. They are widely used to make websites work more efficiently and provide information to website
          owners.
        </p>
        <p className="mt-4">
          Cookies can be:
        </p>
        <ul className="space-y-2 mt-2">
          <li>
            <strong>Session cookies:</strong> Temporary cookies that expire when you close your browser
          </li>
          <li>
            <strong>Persistent cookies:</strong> Remain on your device for a set period or until you delete them
          </li>
          <li>
            <strong>First-party cookies:</strong> Set by CutCosts directly
          </li>
          <li>
            <strong>Third-party cookies:</strong> Set by external services we use (e.g., analytics)
          </li>
        </ul>
      </section>

      {/* 2. Why We Use Cookies */}
      <section id="why-we-use-cookies" className="mb-12">
        <h2 className="text-2xl font-bold text-gray-900 mb-4">2. Why We Use Cookies</h2>
        <p>
          We use cookies to:
        </p>
        <ul className="space-y-2 mt-4">
          <li>
            <strong>Keep you logged in:</strong> Authenticate your session and remember your login
          </li>
          <li>
            <strong>Secure your account:</strong> Prevent unauthorized access and CSRF attacks
          </li>
          <li>
            <strong>Remember preferences:</strong> Save your theme, language, and notification settings
          </li>
          <li>
            <strong>Improve performance:</strong> Cache data to make the website faster
          </li>
          <li>
            <strong>Analyze usage:</strong> Understand how users interact with CutCosts (with your consent)
          </li>
        </ul>
      </section>

      {/* 3. Types of Cookies We Use */}
      <section id="types-of-cookies" className="mb-12">
        <h2 className="text-2xl font-bold text-gray-900 mb-4">3. Types of Cookies We Use</h2>

        {/* Essential Cookies */}
        <div className="not-prose bg-white border border-gray-200 rounded-lg p-6 mb-6">
          <div className="flex items-start gap-3 mb-3">
            <Check className="w-6 h-6 text-green-600 flex-shrink-0 mt-1" />
            <div>
              <h3 className="text-lg font-semibold text-gray-900">Essential Cookies (Always Active)</h3>
              <p className="text-gray-600 text-sm mt-1">
                These cookies are necessary for the website to function and cannot be disabled.
              </p>
            </div>
          </div>

          <div className="mt-4">
            <table className="w-full text-sm">
              <thead className="bg-gray-50">
                <tr>
                  <th className="px-4 py-2 text-left font-semibold text-gray-700">Cookie Name</th>
                  <th className="px-4 py-2 text-left font-semibold text-gray-700">Purpose</th>
                  <th className="px-4 py-2 text-left font-semibold text-gray-700">Duration</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-gray-200">
                <tr>
                  <td className="px-4 py-3 font-mono text-xs">access_token</td>
                  <td className="px-4 py-3 text-gray-600">
                    JWT authentication token to keep you logged in
                  </td>
                  <td className="px-4 py-3 text-gray-600">15 minutes</td>
                </tr>
                <tr>
                  <td className="px-4 py-3 font-mono text-xs">refresh_token</td>
                  <td className="px-4 py-3 text-gray-600">
                    Token to refresh your session without re-login
                  </td>
                  <td className="px-4 py-3 text-gray-600">7-30 days</td>
                </tr>
                <tr>
                  <td className="px-4 py-3 font-mono text-xs">csrf_token</td>
                  <td className="px-4 py-3 text-gray-600">
                    Security token to prevent cross-site request forgery attacks
                  </td>
                  <td className="px-4 py-3 text-gray-600">Session</td>
                </tr>
              </tbody>
            </table>
          </div>
        </div>

        {/* Functional Cookies */}
        <div className="not-prose bg-white border border-gray-200 rounded-lg p-6 mb-6">
          <div className="flex items-start gap-3 mb-3">
            <Settings className="w-6 h-6 text-blue-600 flex-shrink-0 mt-1" />
            <div>
              <h3 className="text-lg font-semibold text-gray-900">Functional Cookies</h3>
              <p className="text-gray-600 text-sm mt-1">
                These cookies enhance your experience by remembering your preferences.
              </p>
            </div>
          </div>

          <div className="mt-4">
            <table className="w-full text-sm">
              <thead className="bg-gray-50">
                <tr>
                  <th className="px-4 py-2 text-left font-semibold text-gray-700">Cookie Name</th>
                  <th className="px-4 py-2 text-left font-semibold text-gray-700">Purpose</th>
                  <th className="px-4 py-2 text-left font-semibold text-gray-700">Duration</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-gray-200">
                <tr>
                  <td className="px-4 py-3 font-mono text-xs">theme</td>
                  <td className="px-4 py-3 text-gray-600">
                    Remembers your preferred theme (light/dark mode)
                  </td>
                  <td className="px-4 py-3 text-gray-600">1 year</td>
                </tr>
                <tr>
                  <td className="px-4 py-3 font-mono text-xs">language</td>
                  <td className="px-4 py-3 text-gray-600">
                    Stores your preferred language
                  </td>
                  <td className="px-4 py-3 text-gray-600">1 year</td>
                </tr>
                <tr>
                  <td className="px-4 py-3 font-mono text-xs">cookie_consent</td>
                  <td className="px-4 py-3 text-gray-600">
                    Remembers your cookie preferences
                  </td>
                  <td className="px-4 py-3 text-gray-600">1 year</td>
                </tr>
              </tbody>
            </table>
          </div>
        </div>

        {/* Analytics Cookies */}
        <div className="not-prose bg-white border border-gray-200 rounded-lg p-6 mb-6">
          <div className="flex items-start gap-3 mb-3">
            <AlertCircle className="w-6 h-6 text-yellow-600 flex-shrink-0 mt-1" />
            <div>
              <h3 className="text-lg font-semibold text-gray-900">Analytics Cookies (Optional)</h3>
              <p className="text-gray-600 text-sm mt-1">
                These cookies help us understand how users interact with CutCosts. <strong>Requires your consent.</strong>
              </p>
            </div>
          </div>

          <div className="mt-4">
            <table className="w-full text-sm">
              <thead className="bg-gray-50">
                <tr>
                  <th className="px-4 py-2 text-left font-semibold text-gray-700">Cookie Name</th>
                  <th className="px-4 py-2 text-left font-semibold text-gray-700">Purpose</th>
                  <th className="px-4 py-2 text-left font-semibold text-gray-700">Duration</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-gray-200">
                <tr>
                  <td className="px-4 py-3 font-mono text-xs">_ga</td>
                  <td className="px-4 py-3 text-gray-600">
                    Google Analytics - Tracks user behavior (anonymized)
                  </td>
                  <td className="px-4 py-3 text-gray-600">2 years</td>
                </tr>
                <tr>
                  <td className="px-4 py-3 font-mono text-xs">_ga_*</td>
                  <td className="px-4 py-3 text-gray-600">
                    Google Analytics 4 - Session tracking
                  </td>
                  <td className="px-4 py-3 text-gray-600">2 years</td>
                </tr>
              </tbody>
            </table>
          </div>

          <div className="mt-4 p-4 bg-yellow-50 rounded-lg">
            <p className="text-yellow-900 text-xs">
              <strong>Note:</strong> Analytics cookies are only set if you accept them in the cookie banner. You can
              withdraw consent at any time.
            </p>
          </div>
        </div>

        {/* No Advertising Cookies */}
        <div className="not-prose bg-green-50 border border-green-200 rounded-lg p-6">
          <div className="flex items-start gap-3">
            <X className="w-6 h-6 text-green-600 flex-shrink-0 mt-1" />
            <div>
              <h3 className="text-lg font-semibold text-green-900">We Do NOT Use:</h3>
              <ul className="mt-2 space-y-1 text-sm text-green-800">
                <li>✗ Advertising or marketing cookies</li>
                <li>✗ Social media tracking pixels</li>
                <li>✗ Cross-site tracking cookies</li>
                <li>✗ Retargeting or remarketing cookies</li>
              </ul>
            </div>
          </div>
        </div>
      </section>

      {/* 4. Third-Party Cookies */}
      <section id="third-party-cookies" className="mb-12">
        <h2 className="text-2xl font-bold text-gray-900 mb-4">4. Third-Party Cookies</h2>
        <p>
          We use a limited number of trusted third-party services that may set cookies:
        </p>

        <div className="not-prose mt-6 space-y-4">
          <div className="border-l-4 border-blue-500 pl-4">
            <p className="font-semibold text-gray-900">Google Analytics (Optional)</p>
            <p className="text-gray-600 text-sm mt-1">
              Used for anonymized usage analytics. Only active if you consent to analytics cookies.
            </p>
            <p className="text-gray-600 text-xs mt-2">
              Privacy Policy:{" "}
              <a
                href="https://policies.google.com/privacy"
                target="_blank"
                rel="noopener noreferrer"
                className="text-blue-600 hover:underline"
              >
                Google Privacy Policy
              </a>
            </p>
          </div>
        </div>

        <p className="mt-6 text-sm text-gray-600">
          We regularly review our third-party services to ensure they comply with GDPR and respect your privacy.
        </p>
      </section>

      {/* 5. How to Manage Cookies */}
      <section id="manage-cookies" className="mb-12">
        <h2 className="text-2xl font-bold text-gray-900 mb-4">5. How to Manage Cookies</h2>

        <h3 className="text-xl font-semibold text-gray-900 mt-6 mb-3">5.1 CutCosts Cookie Preferences</h3>
        <p>
          You can manage your cookie preferences at any time by:
        </p>
        <ul className="space-y-2 mt-2">
          <li>
            Clicking <strong>"Cookie Settings"</strong> in the footer of any page
          </li>
          <li>
            Going to <strong>Settings → Privacy → Cookies</strong> in your dashboard
          </li>
        </ul>

        <h3 className="text-xl font-semibold text-gray-900 mt-6 mb-3">5.2 Browser Settings</h3>
        <p>
          You can also control cookies through your browser settings:
        </p>
        <ul className="space-y-2 mt-4">
          <li>
            <strong>Google Chrome:</strong>{" "}
            <code className="text-xs bg-gray-100 px-2 py-1 rounded">
              Settings → Privacy and security → Cookies and other site data
            </code>
          </li>
          <li>
            <strong>Firefox:</strong>{" "}
            <code className="text-xs bg-gray-100 px-2 py-1 rounded">
              Settings → Privacy & Security → Cookies and Site Data
            </code>
          </li>
          <li>
            <strong>Safari:</strong>{" "}
            <code className="text-xs bg-gray-100 px-2 py-1 rounded">
              Preferences → Privacy → Manage Website Data
            </code>
          </li>
          <li>
            <strong>Edge:</strong>{" "}
            <code className="text-xs bg-gray-100 px-2 py-1 rounded">
              Settings → Cookies and site permissions → Manage and delete cookies
            </code>
          </li>
        </ul>

        <div className="not-prose bg-yellow-50 border border-yellow-200 rounded-lg p-4 mt-6">
          <p className="text-yellow-900 text-sm">
            <strong>Warning:</strong> Blocking essential cookies will prevent CutCosts from functioning properly.
            You will not be able to log in or use the service.
          </p>
        </div>

        <h3 className="text-xl font-semibold text-gray-900 mt-6 mb-3">5.3 Do Not Track (DNT)</h3>
        <p>
          We respect the "Do Not Track" (DNT) browser setting. If you have DNT enabled, we will not set analytics
          cookies, even if you have not explicitly rejected them.
        </p>
      </section>

      {/* 6. Updates to This Policy */}
      <section id="updates" className="mb-12">
        <h2 className="text-2xl font-bold text-gray-900 mb-4">6. Updates to This Policy</h2>
        <p>
          We may update this Cookie Policy from time to time to reflect changes in our practices or legal
          requirements. We will notify you of significant changes by:
        </p>
        <ul className="space-y-2 mt-2">
          <li>Displaying a prominent notice on our website</li>
          <li>Updating the "Last updated" date at the top of this page</li>
        </ul>
        <p className="mt-4 text-sm text-gray-600">
          <strong>Last updated:</strong> January 2025
        </p>
      </section>

      {/* 7. Contact Us */}
      <section id="contact" className="mb-12">
        <h2 className="text-2xl font-bold text-gray-900 mb-4">7. Contact Us</h2>
        <p>
          If you have questions about our use of cookies, please contact us:
        </p>
        <div className="not-prose bg-blue-50 rounded-lg p-6 mt-4">
          <p className="text-gray-900 font-semibold text-lg">CutCosts Privacy Team</p>
          <p className="text-gray-700 mt-2">
            Email:{" "}
            <a href="mailto:privacy@cutcosts.tech" className="text-blue-600 hover:underline font-semibold">
              privacy@cutcosts.tech
            </a>
          </p>
          <p className="text-gray-700">
            Address: <span className="font-mono">[YOUR COMPANY ADDRESS]</span>
          </p>
        </div>
      </section>

      {/* Footer */}
      <div className="not-prose border-t border-gray-200 pt-8 mt-12">
        <p className="text-sm text-gray-500 text-center">
          © {new Date().getFullYear()} CutCosts. All rights reserved.
        </p>
        <p className="text-xs text-gray-400 text-center mt-2">
          This Cookie Policy is part of our{" "}
          <a href="/legal/privacy" className="text-blue-600 hover:underline">
            Privacy Policy
          </a>{" "}
          and{" "}
          <a href="/legal/terms" className="text-blue-600 hover:underline">
            Terms of Service
          </a>
          .
        </p>
      </div>
    </div>
  );
}
