import { landing } from "@/content/landing";

export function Offer({ children }: { children: React.ReactNode }) {
  const { heading, body, gives, asks } = landing.offer;
  return (
    <section id="apply" className="mx-auto max-w-3xl scroll-mt-8 px-4 py-12">
      <h2 className="text-2xl font-semibold tracking-tight">{heading}</h2>
      <p className="mt-2 text-muted-foreground">{body}</p>
      <div className="mt-6 grid gap-6 sm:grid-cols-2">
        <div>
          <h3 className="text-sm font-medium">You get</h3>
          <ul className="mt-2 list-disc space-y-1 pl-5 text-sm text-muted-foreground">
            {gives.map((g) => (
              <li key={g}>{g}</li>
            ))}
          </ul>
        </div>
        <div>
          <h3 className="text-sm font-medium">We ask</h3>
          <ul className="mt-2 list-disc space-y-1 pl-5 text-sm text-muted-foreground">
            {asks.map((a) => (
              <li key={a}>{a}</li>
            ))}
          </ul>
        </div>
      </div>
      <div className="relative mt-8 rounded-xl border p-6">
        <h3 className="mb-4 text-lg font-semibold">{landing.form.heading}</h3>
        {children}
      </div>
    </section>
  );
}
