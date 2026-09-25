import { landing } from "@/content/landing";

export function LandingFooter() {
  const { contactEmail, privacy } = landing.footer;
  return (
    <footer className="mx-auto max-w-5xl border-t px-4 py-8 text-sm text-muted-foreground">
      <div className="flex flex-col justify-between gap-2 sm:flex-row">
        <span>© {new Date().getFullYear()} Foresight</span>
        <a href={`mailto:${contactEmail}`} className="underline underline-offset-4">
          {contactEmail}
        </a>
      </div>
      <p className="mt-2">{privacy}</p>
    </footer>
  );
}
