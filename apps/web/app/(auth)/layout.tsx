export default function AuthLayout({ children }: { children: React.ReactNode }) {
  return (
    <main className="flex min-h-screen flex-col items-center justify-center px-4 py-12">
      <div className="mb-8 text-center">
        <div className="text-2xl font-semibold tracking-tight">Foresight</div>
        <p className="mt-1 text-sm text-muted-foreground">Predict. Seal. Grade. Learn.</p>
      </div>
      <div className="w-full max-w-sm">{children}</div>
    </main>
  );
}
