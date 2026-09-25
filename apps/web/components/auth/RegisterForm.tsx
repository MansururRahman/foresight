"use client";

import { zodResolver } from "@hookform/resolvers/zod";
import Link from "next/link";
import { useRouter } from "next/navigation";
import { useState } from "react";
import { useForm } from "react-hook-form";
import { z } from "zod";

import { Button } from "@/components/ui/button";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { AuthError, register as registerAccount } from "@/lib/auth";
import { useAuth } from "@/lib/auth-context";

const schema = z.object({
  name: z.string().trim().min(1, "Tell us your name").max(80),
  email: z.string().trim().min(3, "Enter your email").max(254),
  password: z.string().min(8, "At least 8 characters").max(128),
});
type Values = z.infer<typeof schema>;

export function RegisterForm() {
  const router = useRouter();
  const { signedIn } = useAuth();
  const [serverError, setServerError] = useState<string | null>(null);
  const form = useForm<Values>({ resolver: zodResolver(schema), defaultValues: { name: "", email: "", password: "" } });

  const onSubmit = form.handleSubmit(async (values) => {
    setServerError(null);
    try {
      const user = await registerAccount(values.email, values.name, values.password);
      signedIn(user);
      router.replace("/w");
    } catch (e) {
      setServerError(e instanceof AuthError ? e.message : "Could not create the account. Is the auth service running?");
    }
  });

  const err = form.formState.errors;
  return (
    <Card>
      <CardHeader>
        <CardTitle>Create your account</CardTitle>
        <CardDescription>Then create or join a workspace.</CardDescription>
      </CardHeader>
      <CardContent>
        <form onSubmit={onSubmit} className="space-y-4" noValidate>
          <div className="space-y-1.5">
            <Label htmlFor="name">Name</Label>
            <Input id="name" autoComplete="name" {...form.register("name")} />
            {err.name && <p className="text-sm text-destructive">{err.name.message}</p>}
          </div>
          <div className="space-y-1.5">
            <Label htmlFor="email">Email</Label>
            <Input id="email" type="email" autoComplete="email" {...form.register("email")} />
            {err.email && <p className="text-sm text-destructive">{err.email.message}</p>}
          </div>
          <div className="space-y-1.5">
            <Label htmlFor="password">Password</Label>
            <Input id="password" type="password" autoComplete="new-password" {...form.register("password")} />
            {err.password && <p className="text-sm text-destructive">{err.password.message}</p>}
          </div>
          {serverError && (
            <p role="alert" className="text-sm text-destructive">
              {serverError}
            </p>
          )}
          <Button type="submit" className="w-full" disabled={form.formState.isSubmitting}>
            {form.formState.isSubmitting ? "Creating…" : "Create account"}
          </Button>
          <p className="text-center text-sm text-muted-foreground">
            Already registered?{" "}
            <Link href="/login" className="underline underline-offset-4">
              Sign in
            </Link>
          </p>
        </form>
      </CardContent>
    </Card>
  );
}
