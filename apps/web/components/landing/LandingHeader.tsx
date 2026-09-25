import Link from "next/link";

import { buttonVariants } from "@/components/ui/button";
import { landing } from "@/content/landing";

export function LandingHeader() {
  return (
    <header className="mx-auto flex max-w-5xl items-center justify-between px-4 py-4">
      <span className="text-lg font-semibold tracking-tight">Foresight</span>
      <nav className="flex items-center gap-2">
        <Link href="/login" className={buttonVariants({ variant: "ghost" })}>
          {landing.nav.login}
        </Link>
        <a href="#apply" className={buttonVariants()}>
          {landing.nav.cta}
        </a>
      </nav>
    </header>
  );
}
