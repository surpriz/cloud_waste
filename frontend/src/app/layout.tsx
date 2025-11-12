import type { Metadata } from "next";
import { Inter } from "next/font/google";
import "./globals.css";
import { CookieBanner } from "@/components/legal/CookieBanner";
import { StructuredData } from "@/components/seo/StructuredData";
import { SentryProvider } from "@/components/providers/SentryProvider";

const inter = Inter({ subsets: ["latin"] });

export const metadata: Metadata = {
  metadataBase: new URL("https://cloudwaste.com"),
  title: {
    default: "CloudWaste - Detect Orphaned Cloud Resources",
    template: "%s | CloudWaste",
  },
  description: "Identify and track unused cloud resources to reduce costs across AWS, Azure, and GCP. Save up to 40% with automated orphaned resource detection and intelligent cost optimization.",
  keywords: [
    "cloud cost optimization",
    "AWS cost savings",
    "Azure cost reduction",
    "GCP waste detection",
    "orphaned resources",
    "cloud waste",
    "DevOps",
    "FinOps",
    "cloud cost management",
    "infrastructure optimization",
  ],
  authors: [{ name: "CloudWaste", url: "https://cloudwaste.com" }],
  creator: "CloudWaste",
  publisher: "CloudWaste",
  robots: {
    index: true,
    follow: true,
    googleBot: {
      index: true,
      follow: true,
      "max-video-preview": -1,
      "max-image-preview": "large",
      "max-snippet": -1,
    },
  },
  openGraph: {
    type: "website",
    locale: "en_US",
    url: "https://cloudwaste.com",
    siteName: "CloudWaste",
    title: "CloudWaste - Detect Orphaned Cloud Resources",
    description: "Identify and track unused cloud resources to reduce costs across AWS, Azure, and GCP. Save up to 40% on your cloud bills.",
    images: [
      {
        url: "/og-image.png",
        width: 1200,
        height: 630,
        alt: "CloudWaste - Cloud Cost Optimization Platform",
      },
    ],
  },
  twitter: {
    card: "summary_large_image",
    title: "CloudWaste - Detect Orphaned Cloud Resources",
    description: "Identify and track unused cloud resources to reduce costs across AWS, Azure, and GCP. Save up to 40% on your cloud bills.",
    images: ["/og-image.png"],
    creator: "@cloudwaste",
    site: "@cloudwaste",
  },
  icons: {
    icon: [
      { url: "/favicon.ico", sizes: "32x32" },
      { url: "/icon-192.png", sizes: "192x192", type: "image/png" },
      { url: "/icon-512.png", sizes: "512x512", type: "image/png" },
    ],
    apple: [
      { url: "/apple-touch-icon.png", sizes: "180x180", type: "image/png" },
    ],
  },
  manifest: "/manifest.json",
  verification: {
    // Add your verification tokens when ready
    // google: "your-google-site-verification-code",
    // yandex: "your-yandex-verification-code",
    // bing: "your-bing-verification-code",
  },
  alternates: {
    canonical: "https://cloudwaste.com",
  },
  category: "technology",
};

export const viewport = {
  width: "device-width",
  initialScale: 1,
  maximumScale: 5,
  themeColor: "#2563eb",
};

export default function RootLayout({
  children,
}: {
  children: React.ReactNode;
}) {
  return (
    <html lang="en">
      <head>
        <StructuredData />
      </head>
      <body className={inter.className}>
        <SentryProvider>
          {children}
          <CookieBanner />
        </SentryProvider>
      </body>
    </html>
  );
}
