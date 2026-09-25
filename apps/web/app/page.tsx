"use client";

import { useRouter } from "next/navigation";
import { useEffect } from "react";

import { useAuth } from "@/lib/auth-context";

export default function Home() {
  const { status } = useAuth();
  const router = useRouter();
  useEffect(() => {
    if (status === "authenticated") router.replace("/w");
    if (status === "anonymous") router.replace("/login");
  }, [status, router]);
  return null;
}
