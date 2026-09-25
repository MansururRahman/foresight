// Public runtime configuration. Baked into the client bundle at build time.
export const API_URL = (process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:8000").replace(/\/$/, "");
export const AUTH_URL = (process.env.NEXT_PUBLIC_AUTH_URL ?? "http://localhost:8001").replace(/\/$/, "");
