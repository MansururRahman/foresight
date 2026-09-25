"use client";

import { zodResolver } from "@hookform/resolvers/zod";
import { useEffect } from "react";
import { Controller, useForm, useWatch } from "react-hook-form";
import { z } from "zod";

import { TagInput } from "@/components/project/TagInput";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Textarea } from "@/components/ui/textarea";
import type { ProjectInput } from "@/lib/queries/projects";

const schema = z
  .object({
    title: z.string().trim().min(1, "Give the project a title").max(200),
    description: z.string().max(5000),
    tags: z.array(z.string()).max(20),
    planned_start: z.string(),
    planned_end: z.string(),
  })
  .refine((v) => !v.planned_start || !v.planned_end || v.planned_end >= v.planned_start, {
    message: "End date must not be before the start date",
    path: ["planned_end"],
  });
export type ProjectFormValues = z.infer<typeof schema>;

type Props = {
  initial?: Partial<ProjectFormValues>;
  submitLabel: string;
  pending?: boolean;
  serverError?: string | null;
  onSubmit: (values: ProjectInput) => void;
  onValuesChange?: (values: ProjectFormValues) => void;
};

export function ProjectForm({ initial, submitLabel, pending, serverError, onSubmit, onValuesChange }: Props) {
  const form = useForm<ProjectFormValues>({
    resolver: zodResolver(schema),
    defaultValues: { title: "", description: "", tags: [], planned_start: "", planned_end: "", ...initial },
  });
  const values = useWatch({ control: form.control }) as ProjectFormValues;
  const serialized = JSON.stringify(values);
  useEffect(() => {
    onValuesChange?.(values);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [serialized]);

  const err = form.formState.errors;
  return (
    <form
      className="space-y-4"
      noValidate
      onSubmit={form.handleSubmit((v) =>
        onSubmit({
          title: v.title.trim(),
          description: v.description,
          tags: v.tags,
          planned_start: v.planned_start || null,
          planned_end: v.planned_end || null,
        }),
      )}
    >
      <div className="space-y-1.5">
        <Label htmlFor="title">Title</Label>
        <Input id="title" placeholder="Vendor API integration" {...form.register("title")} />
        {err.title && <p className="text-sm text-destructive">{err.title.message}</p>}
      </div>
      <div className="space-y-1.5">
        <Label htmlFor="description">Description</Label>
        <Textarea id="description" rows={4} placeholder="What are we building, for whom, by when?" {...form.register("description")} />
      </div>
      <div className="space-y-1.5">
        <Label htmlFor="tags">Tags</Label>
        <Controller control={form.control} name="tags" render={({ field }) => <TagInput id="tags" value={field.value} onChange={field.onChange} />} />
        <p className="text-xs text-muted-foreground">Tags drive the suggestions from similar past projects.</p>
      </div>
      <div className="grid grid-cols-2 gap-3">
        <div className="space-y-1.5">
          <Label htmlFor="planned_start">Planned start</Label>
          <Input id="planned_start" type="date" {...form.register("planned_start")} />
        </div>
        <div className="space-y-1.5">
          <Label htmlFor="planned_end">Planned end</Label>
          <Input id="planned_end" type="date" {...form.register("planned_end")} />
          {err.planned_end && <p className="text-sm text-destructive">{err.planned_end.message}</p>}
        </div>
      </div>
      {serverError && (
        <p role="alert" className="text-sm text-destructive">
          {serverError}
        </p>
      )}
      <Button type="submit" disabled={pending}>
        {pending ? "Saving…" : submitLabel}
      </Button>
    </form>
  );
}
