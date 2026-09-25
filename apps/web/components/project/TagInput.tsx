"use client";

import { X } from "lucide-react";
import { useState } from "react";

import { Badge } from "@/components/ui/badge";
import { Input } from "@/components/ui/input";

const MAX_TAGS = 20;
const MAX_TAG_LEN = 40;

export function normalizeTag(raw: string): string {
  return raw.trim().toLowerCase().split(/\s+/).join(" ").slice(0, MAX_TAG_LEN);
}

type Props = {
  value: string[];
  onChange: (tags: string[]) => void;
  placeholder?: string;
  id?: string;
};

export function TagInput({ value, onChange, placeholder = "vendor, timeline…", id }: Props) {
  const [draft, setDraft] = useState("");

  const commit = (raw: string) => {
    const tag = normalizeTag(raw);
    setDraft("");
    if (!tag || value.includes(tag) || value.length >= MAX_TAGS) return;
    onChange([...value, tag]);
  };

  return (
    <div className="flex flex-wrap items-center gap-1.5 rounded-md border border-input bg-background px-2 py-1.5 focus-within:ring-2 focus-within:ring-ring/50">
      {value.map((tag) => (
        <Badge key={tag} variant="secondary" className="gap-1 pr-1">
          {tag}
          <button
            type="button"
            aria-label={`Remove ${tag}`}
            className="rounded-sm p-0.5 hover:bg-foreground/10"
            onClick={() => onChange(value.filter((t) => t !== tag))}
          >
            <X className="size-3" aria-hidden />
          </button>
        </Badge>
      ))}
      <Input
        id={id}
        aria-label="Add tag"
        value={draft}
        placeholder={value.length ? "" : placeholder}
        className="h-7 min-w-24 flex-1 border-0 bg-transparent px-1 shadow-none focus-visible:ring-0"
        onChange={(e) => {
          const v = e.target.value;
          if (v.endsWith(",")) commit(v.slice(0, -1));
          else setDraft(v);
        }}
        onKeyDown={(e) => {
          if (e.key === "Enter") {
            e.preventDefault();
            commit(draft);
          } else if (e.key === "Backspace" && draft === "" && value.length) {
            onChange(value.slice(0, -1));
          }
        }}
        onBlur={() => draft.trim() && commit(draft)}
      />
    </div>
  );
}
