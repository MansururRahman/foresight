"use client";

import { zodResolver } from "@hookform/resolvers/zod";
import { useSearchParams } from "next/navigation";
import { useRef, useState } from "react";
import { useForm } from "react-hook-form";
import { z } from "zod";

import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Textarea } from "@/components/ui/textarea";
import { landing } from "@/content/landing";
import { ApiError } from "@/lib/api";
import { useSubmitLead } from "@/lib/queries/leads";
import { TEAM_SIZES, type TeamSize } from "@/lib/types";

const copy = landing.form;

const schema = z.object({
  name: z.string().trim().min(1, "Tell us your name").max(120, "Keep it under 120 characters"),
  email: z.string().trim().email("Enter a valid work email").max(254),
  company: z.string().trim().min(1, "Tell us where you work").max(160, "Keep it under 160 characters"),
  role: z.string().trim().min(1, "Tell us your role").max(120, "Keep it under 120 characters"),
  team_size: z.string().refine((v) => (TEAM_SIZES as readonly string[]).includes(v), "Pick a team size"),
  story: z.string().trim().max(2000, "Keep it under 2000 characters"),
  website: z.string(),
});
type Values = z.input<typeof schema>;

/** Which channel sent the visitor: `?ref=` wins over `?utm_source=`. */
export function readSource(params: { get(name: string): string | null }): string | null {
  const raw = (params.get("ref") ?? params.get("utm_source") ?? "").trim();
  return raw ? raw.slice(0, 100) : null;
}

function FieldError({ message }: { message?: string }) {
  return message ? <p className="text-sm text-destructive">{message}</p> : null;
}

export function LeadForm() {
  const params = useSearchParams();
  const submit = useSubmitLead();
  const inFlight = useRef(false);
  const [done, setDone] = useState(false);
  const [serverError, setServerError] = useState<string | null>(null);
  const form = useForm<Values>({
    resolver: zodResolver(schema),
    defaultValues: { name: "", email: "", company: "", role: "", team_size: "", story: "", website: "" },
  });
  const errors = form.formState.errors;

  const send = async (v: Values) => {
    setServerError(null);
    try {
      await submit.mutateAsync({
        name: v.name,
        email: v.email.toLowerCase(),
        company: v.company,
        role: v.role,
        team_size: v.team_size as TeamSize,
        story: v.story || null,
        source: readSource(params),
        website: v.website,
      });
      setDone(true);
    } catch (e) {
      setServerError(e instanceof ApiError && e.status === 429 ? copy.errors.rateLimited : copy.errors.generic);
    }
  };

  // Guards against repeat submits (e.g. Enter pressed twice) before the disabled state renders.
  const onSubmit = async (e: React.FormEvent<HTMLFormElement>) => {
    e.preventDefault();
    if (inFlight.current) return;
    inFlight.current = true;
    try {
      await form.handleSubmit(send)(e);
    } finally {
      inFlight.current = false;
    }
  };

  if (done) {
    return (
      <p role="status" className="rounded-lg border bg-muted/40 p-6 text-center font-medium">
        {copy.success}
      </p>
    );
  }

  const pending = form.formState.isSubmitting || submit.isPending;

  return (
    <form onSubmit={onSubmit} className="space-y-4" noValidate>
      <div className="grid gap-4 sm:grid-cols-2">
        <div className="space-y-1.5">
          <Label htmlFor="lead-name">{copy.labels.name}</Label>
          <Input id="lead-name" autoComplete="name" {...form.register("name")} />
          <FieldError message={errors.name?.message} />
        </div>
        <div className="space-y-1.5">
          <Label htmlFor="lead-email">{copy.labels.email}</Label>
          <Input id="lead-email" type="email" autoComplete="email" {...form.register("email")} />
          <FieldError message={errors.email?.message} />
        </div>
        <div className="space-y-1.5">
          <Label htmlFor="lead-company">{copy.labels.company}</Label>
          <Input id="lead-company" autoComplete="organization" {...form.register("company")} />
          <FieldError message={errors.company?.message} />
        </div>
        <div className="space-y-1.5">
          <Label htmlFor="lead-role">{copy.labels.role}</Label>
          <Input id="lead-role" autoComplete="organization-title" {...form.register("role")} />
          <FieldError message={errors.role?.message} />
        </div>
      </div>
      <div className="space-y-1.5">
        <Label htmlFor="lead-team-size">{copy.labels.teamSize}</Label>
        <select
          id="lead-team-size"
          className="h-8 w-full rounded-lg border border-input bg-transparent px-2.5 text-sm outline-none focus-visible:border-ring focus-visible:ring-3 focus-visible:ring-ring/50 dark:bg-input/30 sm:w-48"
          {...form.register("team_size")}
        >
          <option value="">{copy.labels.teamSizePlaceholder}</option>
          {TEAM_SIZES.map((size) => (
            <option key={size} value={size}>
              {size}
            </option>
          ))}
        </select>
        <FieldError message={errors.team_size?.message} />
      </div>
      <div className="space-y-1.5">
        <Label htmlFor="lead-story">
          {copy.labels.story} <span className="font-normal text-muted-foreground">({copy.labels.storyHint})</span>
        </Label>
        <Textarea id="lead-story" rows={4} {...form.register("story")} />
        <FieldError message={errors.story?.message} />
      </div>
      {/* Honeypot: off-screen and hidden from assistive tech; only bots fill it in. */}
      <div aria-hidden="true" className="absolute -left-[10000px] h-px w-px overflow-hidden">
        <label htmlFor="lead-website">Website</label>
        <input id="lead-website" tabIndex={-1} autoComplete="off" {...form.register("website")} />
      </div>
      {serverError && (
        <p role="alert" className="text-sm text-destructive">
          {serverError}
        </p>
      )}
      <Button type="submit" size="lg" className="w-full sm:w-auto" disabled={pending}>
        {pending ? copy.submitting : copy.submit}
      </Button>
    </form>
  );
}
