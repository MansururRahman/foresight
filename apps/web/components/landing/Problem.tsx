import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { landing } from "@/content/landing";

export function Problem() {
  return (
    <section className="mx-auto max-w-5xl px-4 py-12">
      <h2 className="text-center text-2xl font-semibold tracking-tight">{landing.problem.heading}</h2>
      <div className="mt-8 grid gap-4 md:grid-cols-3">
        {landing.problem.items.map((item) => (
          <Card key={item.title}>
            <CardHeader>
              <CardTitle>{item.title}</CardTitle>
            </CardHeader>
            <CardContent className="text-sm text-muted-foreground">{item.body}</CardContent>
          </Card>
        ))}
      </div>
    </section>
  );
}
