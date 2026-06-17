"use client";

import * as React from "react";
import { useRouter } from "next/navigation";
import { useAuth } from "@/components/auth/auth-provider";
import { Loader2 } from "lucide-react";

/**
 * Lands here after Google OAuth. The backend appends the access token to the URL
 * fragment (`#access_token=…`) — fragments never reach a server or logs. We read
 * it, adopt the session, and forward to the dashboard.
 */
export default function OAuthCallbackPage() {
  const router = useRouter();
  const { adoptToken } = useAuth();

  React.useEffect(() => {
    const hash = window.location.hash.replace(/^#/, "");
    const token = new URLSearchParams(hash).get("access_token");
    if (!token) {
      router.replace("/login?error=oauth_failed");
      return;
    }
    // Strip the token from the address bar before doing anything else.
    window.history.replaceState(null, "", "/auth/callback");
    adoptToken(token)
      .then(() => router.replace("/dashboard"))
      .catch(() => router.replace("/login?error=oauth_failed"));
  }, [adoptToken, router]);

  return (
    <div className="flex min-h-screen flex-col items-center justify-center gap-3">
      <Loader2 className="h-6 w-6 animate-spin text-primary" />
      <p className="font-mono text-xs uppercase tracking-[0.2em] text-muted-foreground">
        Completing sign-in…
      </p>
    </div>
  );
}
