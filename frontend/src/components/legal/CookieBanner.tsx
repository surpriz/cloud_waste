"use client";

import { useState, useEffect } from "react";
import Link from "next/link";
import { Cookie, X, Settings, Check } from "lucide-react";

interface CookiePreferences {
  essential: boolean; // Always true, cannot be disabled
  functional: boolean;
  analytics: boolean;
  timestamp: number;
}

const DEFAULT_PREFERENCES: CookiePreferences = {
  essential: true,
  functional: false,
  analytics: false,
  timestamp: Date.now(),
};

export function CookieBanner() {
  const [showBanner, setShowBanner] = useState(false);
  const [showCustomize, setShowCustomize] = useState(false);
  const [preferences, setPreferences] = useState<CookiePreferences>(DEFAULT_PREFERENCES);

  useEffect(() => {
    // Check if user has already made a choice
    const stored = localStorage.getItem("cookie_consent");

    // Check for Do Not Track browser setting
    const dnt = navigator.doNotTrack === "1" || (window as any).doNotTrack === "1";

    if (stored) {
      try {
        const parsed = JSON.parse(stored) as CookiePreferences;
        setPreferences(parsed);
        applyPreferences(parsed);
      } catch (e) {
        // Invalid stored data, show banner
        setShowBanner(true);
      }
    } else if (dnt) {
      // Respect Do Not Track - set minimal cookies and don't show banner
      const dntPreferences = { ...DEFAULT_PREFERENCES, timestamp: Date.now() };
      savePreferences(dntPreferences);
      setPreferences(dntPreferences);
      applyPreferences(dntPreferences);
    } else {
      // No preference stored and no DNT - show banner
      setShowBanner(true);
    }
  }, []);

  const savePreferences = (prefs: CookiePreferences) => {
    const toSave = { ...prefs, timestamp: Date.now() };
    localStorage.setItem("cookie_consent", JSON.stringify(toSave));
    setPreferences(toSave);
    applyPreferences(toSave);
  };

  const applyPreferences = (prefs: CookiePreferences) => {
    // Apply preferences to actual cookies/tracking
    // Essential cookies are always active

    // Functional cookies (theme, language, etc.)
    if (!prefs.functional) {
      // Remove functional cookies if disabled
      localStorage.removeItem("theme");
      localStorage.removeItem("language");
    }

    // Analytics cookies (Google Analytics, etc.)
    if (prefs.analytics) {
      // Enable analytics (placeholder - implement GA4 here)
      console.log("Analytics enabled");
      // Example: window.gtag('consent', 'update', { analytics_storage: 'granted' });
    } else {
      // Disable analytics
      console.log("Analytics disabled");
      // Example: window.gtag('consent', 'update', { analytics_storage: 'denied' });
    }
  };

  const handleAcceptAll = () => {
    const allAccepted: CookiePreferences = {
      essential: true,
      functional: true,
      analytics: true,
      timestamp: Date.now(),
    };
    savePreferences(allAccepted);
    setShowBanner(false);
    setShowCustomize(false);
  };

  const handleRejectAll = () => {
    savePreferences({ ...DEFAULT_PREFERENCES, timestamp: Date.now() });
    setShowBanner(false);
    setShowCustomize(false);
  };

  const handleSaveCustom = () => {
    savePreferences(preferences);
    setShowBanner(false);
    setShowCustomize(false);
  };

  const handleOpenCustomize = () => {
    setShowCustomize(true);
  };

  // Expose method to re-open banner (for "Cookie Settings" link in footer)
  useEffect(() => {
    (window as any).openCookieSettings = () => {
      setShowBanner(true);
      setShowCustomize(true);
    };
  }, []);

  if (!showBanner) return null;

  return (
    <>
      {/* Overlay */}
      <div className="fixed inset-0 bg-black/30 backdrop-blur-sm z-[9998]" onClick={() => {}} />

      {/* Cookie Banner */}
      {!showCustomize && (
        <div className="fixed bottom-0 left-0 right-0 z-[9999] p-4 md:p-6 animate-slide-up">
          <div className="max-w-6xl mx-auto bg-white dark:bg-gray-800 rounded-xl shadow-2xl border border-gray-200 dark:border-gray-700 p-6 md:p-8">
            <div className="flex items-start gap-4">
              <Cookie className="w-8 h-8 text-blue-600 flex-shrink-0" />

              <div className="flex-1">
                <h2 className="text-xl font-bold text-gray-900 dark:text-white mb-2">
                  🍪 We Value Your Privacy
                </h2>
                <p className="text-gray-700 dark:text-gray-300 text-sm md:text-base mb-4">
                  CloudWaste uses <strong>essential cookies</strong> to provide secure authentication and core
                  functionality. We'd also like to use <strong>optional cookies</strong> for analytics to help us
                  improve the service. You can customize your preferences at any time.
                </p>
                <p className="text-gray-600 dark:text-gray-400 text-xs">
                  By clicking "Accept All", you agree to the storing of cookies on your device. Learn more in our{" "}
                  <Link href="/legal/cookies" className="text-blue-600 hover:underline font-semibold">
                    Cookie Policy
                  </Link>{" "}
                  and{" "}
                  <Link href="/legal/privacy" className="text-blue-600 hover:underline font-semibold">
                    Privacy Policy
                  </Link>
                  .
                </p>
              </div>
            </div>

            <div className="mt-6 flex flex-col sm:flex-row gap-3">
              <button
                onClick={handleAcceptAll}
                className="flex-1 sm:flex-none px-6 py-3 bg-blue-600 hover:bg-blue-700 text-white rounded-lg font-semibold transition-colors flex items-center justify-center gap-2"
              >
                <Check className="w-4 h-4" />
                Accept All
              </button>
              <button
                onClick={handleRejectAll}
                className="flex-1 sm:flex-none px-6 py-3 bg-gray-200 dark:bg-gray-700 hover:bg-gray-300 dark:hover:bg-gray-600 text-gray-900 dark:text-white rounded-lg font-semibold transition-colors flex items-center justify-center gap-2"
              >
                <X className="w-4 h-4" />
                Reject All
              </button>
              <button
                onClick={handleOpenCustomize}
                className="flex-1 sm:flex-none px-6 py-3 border-2 border-gray-300 dark:border-gray-600 hover:border-gray-400 dark:hover:border-gray-500 text-gray-900 dark:text-white rounded-lg font-semibold transition-colors flex items-center justify-center gap-2"
              >
                <Settings className="w-4 h-4" />
                Customize
              </button>
            </div>
          </div>
        </div>
      )}

      {/* Customization Modal */}
      {showCustomize && (
        <div className="fixed inset-0 z-[9999] flex items-center justify-center p-4">
          <div className="bg-white dark:bg-gray-800 rounded-xl shadow-2xl border border-gray-200 dark:border-gray-700 max-w-2xl w-full max-h-[90vh] overflow-y-auto">
            <div className="p-6 md:p-8">
              <div className="flex items-center justify-between mb-6">
                <h2 className="text-2xl font-bold text-gray-900 dark:text-white flex items-center gap-2">
                  <Settings className="w-6 h-6 text-blue-600" />
                  Cookie Preferences
                </h2>
                <button
                  onClick={() => setShowCustomize(false)}
                  className="p-2 hover:bg-gray-100 dark:hover:bg-gray-700 rounded-lg transition-colors"
                >
                  <X className="w-5 h-5 text-gray-500" />
                </button>
              </div>

              <p className="text-gray-600 dark:text-gray-400 text-sm mb-6">
                Choose which cookies you want to allow. Essential cookies are always required for the site to function
                properly.
              </p>

              {/* Essential Cookies */}
              <div className="mb-6 border border-gray-200 dark:border-gray-700 rounded-lg p-4 bg-gray-50 dark:bg-gray-900">
                <div className="flex items-start justify-between">
                  <div className="flex-1">
                    <h3 className="font-semibold text-gray-900 dark:text-white mb-1">
                      Essential Cookies
                    </h3>
                    <p className="text-sm text-gray-600 dark:text-gray-400 mb-2">
                      Required for authentication, security, and core functionality. Cannot be disabled.
                    </p>
                    <details className="text-xs text-gray-500 dark:text-gray-500">
                      <summary className="cursor-pointer hover:text-gray-700 dark:hover:text-gray-300">
                        View details
                      </summary>
                      <ul className="mt-2 ml-4 space-y-1 list-disc">
                        <li><code>access_token</code> - Authentication (15 min)</li>
                        <li><code>refresh_token</code> - Session refresh (7-30 days)</li>
                        <li><code>csrf_token</code> - Security (session)</li>
                      </ul>
                    </details>
                  </div>
                  <div className="ml-4">
                    <div className="w-11 h-6 bg-blue-600 rounded-full relative">
                      <div className="absolute right-1 top-1 w-4 h-4 bg-white rounded-full"></div>
                    </div>
                    <p className="text-xs text-gray-500 mt-1">Always On</p>
                  </div>
                </div>
              </div>

              {/* Functional Cookies */}
              <div className="mb-6 border border-gray-200 dark:border-gray-700 rounded-lg p-4">
                <div className="flex items-start justify-between">
                  <div className="flex-1">
                    <h3 className="font-semibold text-gray-900 dark:text-white mb-1">
                      Functional Cookies
                    </h3>
                    <p className="text-sm text-gray-600 dark:text-gray-400 mb-2">
                      Remember your preferences like theme, language, and notification settings.
                    </p>
                    <details className="text-xs text-gray-500 dark:text-gray-500">
                      <summary className="cursor-pointer hover:text-gray-700 dark:hover:text-gray-300">
                        View details
                      </summary>
                      <ul className="mt-2 ml-4 space-y-1 list-disc">
                        <li><code>theme</code> - Dark/light mode (1 year)</li>
                        <li><code>language</code> - Preferred language (1 year)</li>
                      </ul>
                    </details>
                  </div>
                  <div className="ml-4">
                    <button
                      onClick={() => setPreferences({ ...preferences, functional: !preferences.functional })}
                      className="relative"
                    >
                      <div className={`w-11 h-6 rounded-full transition-colors ${
                        preferences.functional ? "bg-blue-600" : "bg-gray-300 dark:bg-gray-600"
                      }`}>
                        <div className={`absolute top-1 w-4 h-4 bg-white rounded-full transition-transform ${
                          preferences.functional ? "right-1" : "left-1"
                        }`}></div>
                      </div>
                    </button>
                  </div>
                </div>
              </div>

              {/* Analytics Cookies */}
              <div className="mb-6 border border-gray-200 dark:border-gray-700 rounded-lg p-4">
                <div className="flex items-start justify-between">
                  <div className="flex-1">
                    <h3 className="font-semibold text-gray-900 dark:text-white mb-1">
                      Analytics Cookies
                    </h3>
                    <p className="text-sm text-gray-600 dark:text-gray-400 mb-2">
                      Help us understand how you use CloudWaste so we can improve the service. All data is
                      anonymized.
                    </p>
                    <details className="text-xs text-gray-500 dark:text-gray-500">
                      <summary className="cursor-pointer hover:text-gray-700 dark:hover:text-gray-300">
                        View details
                      </summary>
                      <ul className="mt-2 ml-4 space-y-1 list-disc">
                        <li><code>_ga</code> - Google Analytics (2 years)</li>
                        <li><code>_ga_*</code> - GA4 session tracking (2 years)</li>
                      </ul>
                    </details>
                  </div>
                  <div className="ml-4">
                    <button
                      onClick={() => setPreferences({ ...preferences, analytics: !preferences.analytics })}
                      className="relative"
                    >
                      <div className={`w-11 h-6 rounded-full transition-colors ${
                        preferences.analytics ? "bg-blue-600" : "bg-gray-300 dark:bg-gray-600"
                      }`}>
                        <div className={`absolute top-1 w-4 h-4 bg-white rounded-full transition-transform ${
                          preferences.analytics ? "right-1" : "left-1"
                        }`}></div>
                      </div>
                    </button>
                  </div>
                </div>
              </div>

              {/* Action Buttons */}
              <div className="flex flex-col sm:flex-row gap-3 mt-6 pt-6 border-t border-gray-200 dark:border-gray-700">
                <button
                  onClick={handleSaveCustom}
                  className="flex-1 px-6 py-3 bg-blue-600 hover:bg-blue-700 text-white rounded-lg font-semibold transition-colors flex items-center justify-center gap-2"
                >
                  <Check className="w-4 h-4" />
                  Save Preferences
                </button>
                <button
                  onClick={handleRejectAll}
                  className="flex-1 px-6 py-3 bg-gray-200 dark:bg-gray-700 hover:bg-gray-300 dark:hover:bg-gray-600 text-gray-900 dark:text-white rounded-lg font-semibold transition-colors"
                >
                  Reject All
                </button>
              </div>

              <p className="text-xs text-gray-500 dark:text-gray-400 text-center mt-4">
                Learn more:{" "}
                <Link href="/legal/cookies" className="text-blue-600 hover:underline">
                  Cookie Policy
                </Link>{" "}
                |{" "}
                <Link href="/legal/privacy" className="text-blue-600 hover:underline">
                  Privacy Policy
                </Link>
              </p>
            </div>
          </div>
        </div>
      )}

      <style jsx>{`
        @keyframes slide-up {
          from {
            transform: translateY(100%);
            opacity: 0;
          }
          to {
            transform: translateY(0);
            opacity: 1;
          }
        }
        .animate-slide-up {
          animation: slide-up 0.3s ease-out;
        }
      `}</style>
    </>
  );
}
