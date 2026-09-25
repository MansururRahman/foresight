import { buttonVariants } from "@/components/ui/button";
import { landing } from "@/content/landing";

export function Hero() {
  const { headline, subhead, cta, note } = landing.hero;
  return (
    <section className="mx-auto max-w-3xl px-4 py-16 text-center sm:py-24">
      <h1 className="text-4xl font-bold tracking-tight text-balance sm:text-5xl">{headline}</h1>
      <p className="mt-6 text-lg text-pretty text-muted-foreground">{subhead}</p>
      <div className="mt-8 flex flex-col items-center gap-2">
        <a href="#apply" className={buttonVariants({ size: "lg" })}>
          {cta}
        </a>
        <p className="text-sm text-muted-foreground">{note}</p>
      </div>
    </section>
  );
}
