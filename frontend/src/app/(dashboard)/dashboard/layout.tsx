"use client";

import { BackToTop } from "@/components/layout/BackToTop";

export default function DashboardRoutesLayout({
  children,
}: {
  children: React.ReactNode;
}) {
  return (
    <>
      {children}
      <BackToTop />
    </>
  );
}
