import type { Metadata } from "next";
import { Inter } from "next/font/google";
import "./globals.css";
import { CookieBanner } from "@/components/legal/CookieBanner";

const inter = Inter({ subsets: ["latin"] });

export const metadata: Metadata = {
  title: "CloudWaste - Detect Orphaned Cloud Resources",
  description: "Identify and track unused cloud resources to reduce costs across AWS, Azure, and GCP. Save up to 40% with automated orphaned resource detection and intelligent cost optimization.",
  keywords: "cloud cost optimization, AWS cost savings, Azure cost reduction, GCP waste detection, orphaned resources, cloud waste, DevOps, FinOps",
  authors: [{ name: "CloudWaste" }],
  openGraph: {
    title: "CloudWaste - Detect Orphaned Cloud Resources",
    description: "Identify and track unused cloud resources to reduce costs",
    url: "https://cloudwaste.com",
    siteName: "CloudWaste",
    locale: "en_US",
    type: "website",
  },
  twitter: {
    card: "summary_large_image",
    title: "CloudWaste - Detect Orphaned Cloud Resources",
    description: "Identify and track unused cloud resources to reduce costs",
  },
};

export default function RootLayout({
  children,
}: {
  children: React.ReactNode;
}) {
  return (
    <html lang="en">
      <body className={inter.className}>
        {children}
        <CookieBanner />
      </body>
    </html>
  );
}
