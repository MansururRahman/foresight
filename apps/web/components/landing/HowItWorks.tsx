import Image from "next/image";

import { landing } from "@/content/landing";

export function HowItWorks() {
  const { heading, steps, screenshotAlt } = landing.howItWorks;
  return (
    <section className="mx-auto max-w-5xl px-4 py-12">
      <h2 className="text-center text-2xl font-semibold tracking-tight">{heading}</h2>
      <ol className="mt-8 grid gap-6 md:grid-cols-4">
        {steps.map((step, i) => (
          <li key={step.title} className="space-y-2">
            <span className="flex size-8 items-center justify-center rounded-full bg-primary text-sm font-semibold text-primary-foreground">
              {i + 1}
            </span>
            <h3 className="font-medium">{step.title}</h3>
            <p className="text-sm text-muted-foreground">{step.body}</p>
          </li>
        ))}
      </ol>
      <Image
        src="/landing/calibration.png"
        alt={screenshotAlt}
        width={1280}
        height={800}
        className="mt-10 w-full rounded-xl border shadow-sm"
      />
    </section>
  );
}
