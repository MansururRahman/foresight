import type { Metadata } from "next";
import { Suspense } from "react";

import { Benefits } from "@/components/landing/Benefits";
import { Hero } from "@/components/landing/Hero";
import { HowItWorks } from "@/components/landing/HowItWorks";
import { LandingFooter } from "@/components/landing/LandingFooter";
import { LandingHeader } from "@/components/landing/LandingHeader";
import { LeadForm } from "@/components/landing/LeadForm";
import { Offer } from "@/components/landing/Offer";
import { Problem } from "@/components/landing/Problem";
import { landing } from "@/content/landing";

// Signed-in visitors never reach this page: proxy.ts redirects `/` to `/w` when the session hint is set.
export const metadata: Metadata = {
  metadataBase: new URL(process.env.SITE_URL ?? "http://localhost:3000"),
  title: { absolute: landing.meta.title },
  description: landing.meta.description,
  openGraph: {
    title: landing.meta.title,
    description: landing.meta.description,
    images: [{ url: "/landing/calibration.png", width: 1280, height: 800 }],
  },
};

export default function LandingPage() {
  return (
    <>
      <LandingHeader />
      <main>
        <Hero />
        <Problem />
        <HowItWorks />
        <Benefits />
        <Offer>
          {/* LeadForm reads ?ref= via useSearchParams, which needs a Suspense boundary on a prerendered page. */}
          <Suspense fallback={<div className="h-96" aria-busy="true" />}>
            <LeadForm />
          </Suspense>
        </Offer>
      </main>
      <LandingFooter />
    </>
  );
}
