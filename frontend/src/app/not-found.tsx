import Link from "next/link";
import { Cloud, Home, LayoutDashboard, SearchX } from "lucide-react";
import type { Metadata } from "next";

export const metadata: Metadata = {
  title: "404 - Page Not Found | CloudWaste",
  description: "The page you're looking for has drifted into the cloud",
};

export default function NotFound() {
  return (
    <div className="relative flex min-h-screen flex-col items-center justify-center overflow-hidden bg-gradient-to-br from-blue-600 via-indigo-600 to-purple-700 px-4">
      {/* Animated background elements */}
      <div className="absolute inset-0 opacity-20">
        <div className="absolute top-1/4 left-1/4 h-96 w-96 rounded-full bg-white blur-3xl animate-pulse"></div>
        <div className="absolute bottom-1/4 right-1/4 h-96 w-96 rounded-full bg-blue-300 blur-3xl animate-pulse delay-1000"></div>
      </div>

      {/* Content */}
      <div className="relative z-10 text-center max-w-2xl">
        {/* Animated 404 Icon */}
        <div className="mb-8 flex justify-center">
          <div className="relative">
            <Cloud className="h-32 w-32 text-white/20 animate-pulse" strokeWidth={1} />
            <SearchX
              className="absolute top-1/2 left-1/2 -translate-x-1/2 -translate-y-1/2 h-16 w-16 text-white animate-bounce"
              strokeWidth={2}
            />
          </div>
        </div>

        {/* Error code */}
        <h1 className="text-9xl md:text-[12rem] font-extrabold text-white/90 leading-none mb-4 tracking-tight">
          404
        </h1>

        {/* Title */}
        <h2 className="text-3xl md:text-4xl font-bold text-white mb-4">
          Cette page a disparu dans le cloud ☁️
        </h2>

        {/* Description */}
        <p className="text-lg md:text-xl text-blue-100 mb-8 max-w-md mx-auto">
          La ressource que vous cherchez n'existe plus ou n'a jamais existé.
          Peut-être est-elle devenue un orphelin ? 🤔
        </p>

        {/* Action buttons */}
        <div className="flex flex-col sm:flex-row gap-4 justify-center items-center mt-12">
          <Link
            href="/"
            className="group inline-flex items-center gap-3 rounded-xl bg-white px-8 py-4 text-lg font-bold text-blue-600 transition-all hover:scale-105 hover:shadow-2xl shadow-xl"
          >
            <Home className="h-5 w-5 group-hover:text-blue-500 transition-colors" />
            Retour à l'accueil
          </Link>
          <Link
            href="/dashboard"
            className="inline-flex items-center gap-3 rounded-xl border-2 border-white/30 bg-white/10 backdrop-blur-sm px-8 py-4 text-lg font-semibold text-white transition-all hover:bg-white/20 hover:border-white/50"
          >
            <LayoutDashboard className="h-5 w-5" />
            Tableau de bord
          </Link>
        </div>

        {/* Helpful links */}
        <div className="mt-16 pt-8 border-t border-white/20">
          <p className="text-sm text-blue-200 mb-4">Pages populaires :</p>
          <div className="flex flex-wrap justify-center gap-4 text-sm">
            <Link
              href="/dashboard/accounts"
              className="text-white/80 hover:text-white transition-colors underline underline-offset-4"
            >
              Comptes cloud
            </Link>
            <Link
              href="/dashboard/scans"
              className="text-white/80 hover:text-white transition-colors underline underline-offset-4"
            >
              Analyses
            </Link>
            <Link
              href="/dashboard/resources"
              className="text-white/80 hover:text-white transition-colors underline underline-offset-4"
            >
              Ressources orphelines
            </Link>
          </div>
        </div>
      </div>
    </div>
  );
}
