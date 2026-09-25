import { landing } from "@/content/landing";

export function Benefits() {
  return (
    <section className="mx-auto max-w-5xl px-4 py-12">
      <h2 className="text-center text-2xl font-semibold tracking-tight">{landing.benefits.heading}</h2>
      <dl className="mt-8 grid gap-6 sm:grid-cols-2">
        {landing.benefits.items.map((item) => (
          <div key={item.title} className="rounded-lg border p-5">
            <dt className="font-medium">{item.title}</dt>
            <dd className="mt-1 text-sm text-muted-foreground">{item.body}</dd>
          </div>
        ))}
      </dl>
    </section>
  );
}
