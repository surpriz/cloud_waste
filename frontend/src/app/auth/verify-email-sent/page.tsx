"use client";

import { useState } from "react";
import { useSearchParams } from "next/navigation";
import { authAPI } from "@/lib/api";
import { Mail, RefreshCcw } from "lucide-react";
import Link from "next/link";

export const dynamic = 'force-dynamic'

export default function VerifyEmailSentPage() {
  const searchParams = useSearchParams();
  const email = searchParams.get("email") || "";
  const [isResending, setIsResending] = useState(false);
  const [message, setMessage] = useState("");

  const handleResend = async () => {
    if (!email) {
      setMessage("Email address is missing");
      return;
    }

    setIsResending(true);
    setMessage("");

    try {
      await authAPI.resendVerificationEmail(email);
      setMessage("✅ Verification email resent successfully! Check your inbox.");
    } catch (error: any) {
      setMessage(`❌ Error: ${error.message}`);
    } finally {
      setIsResending(false);
    }
  };

  return (
    <div className="min-h-screen flex items-center justify-center bg-gray-900 px-4">
      <div className="max-w-md w-full">
        <div className="bg-gray-800 rounded-lg shadow-xl p-8 border border-gray-700">
          {/* Icon */}
          <div className="flex justify-center mb-6">
            <div className="w-16 h-16 bg-blue-600/20 rounded-full flex items-center justify-center">
              <Mail className="w-8 h-8 text-blue-400" />
            </div>
          </div>

          {/* Title */}
          <h1 className="text-2xl font-bold text-white text-center mb-2">
            Vérifiez votre email
          </h1>

          {/* Description */}
          <p className="text-gray-400 text-center mb-6">
            Un email de vérification a été envoyé à <br />
            <span className="text-blue-400 font-medium">{email}</span>
          </p>

          {/* Instructions */}
          <div className="bg-gray-900/50 rounded-lg p-4 mb-6 border border-gray-700">
            <p className="text-sm text-gray-300 mb-3">
              📧 <strong>Prochaines étapes :</strong>
            </p>
            <ol className="text-sm text-gray-400 space-y-2 pl-6 list-decimal">
              <li>Ouvrez votre boîte email</li>
              <li>Cliquez sur le lien de vérification</li>
              <li>Revenez vous connecter</li>
            </ol>
          </div>

          {/* Warning */}
          <div className="bg-yellow-900/20 border border-yellow-800/30 rounded-lg p-3 mb-6">
            <p className="text-xs text-yellow-200">
              ⏱️ <strong>Important :</strong> Le lien expire dans 7 jours. Si vous ne vérifiez pas votre email, votre compte sera automatiquement supprimé après 14 jours.
            </p>
          </div>

          {/* Resend button */}
          <button
            onClick={handleResend}
            disabled={isResending || !email}
            className="w-full flex items-center justify-center gap-2 bg-blue-600 hover:bg-blue-700 disabled:bg-gray-700 disabled:cursor-not-allowed text-white py-3 px-4 rounded-lg font-medium transition-colors mb-4"
          >
            {isResending ? (
              <>
                <RefreshCcw className="w-4 h-4 animate-spin" />
                Envoi en cours...
              </>
            ) : (
              <>
                <RefreshCcw className="w-4 h-4" />
                Renvoyer l'email
              </>
            )}
          </button>

          {/* Message */}
          {message && (
            <div className={`text-sm text-center mb-4 ${message.startsWith("✅") ? "text-green-400" : "text-red-400"}`}>
              {message}
            </div>
          )}

          {/* Support link */}
          <p className="text-sm text-gray-500 text-center">
            Problème ? <Link href="/auth/login" className="text-blue-400 hover:text-blue-300">Retour à la connexion</Link>
          </p>
        </div>

        {/* Footer note */}
        <p className="text-xs text-gray-600 text-center mt-4">
          Vérifiez également vos spams si vous ne trouvez pas l'email
        </p>
      </div>
    </div>
  );
}
