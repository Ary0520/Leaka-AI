"use client";

import { useEffect, useState } from "react";
import { getAuthToken, BACKEND_URL } from "@/lib/api";
import { Loader2, ImageOff } from "lucide-react";

/**
 * AuthedImage
 * -----------
 * Renders an image from an auth-protected backend endpoint.
 *
 * A plain <img src> tag cannot attach the Authorization: Bearer header, so
 * for endpoints that now require auth (e.g. /api/screenshots/{id}) we must
 * fetch the bytes with fetch() (which does send the token) and render the
 * result as an object URL.
 *
 * The object URL is revoked on unmount / src change to avoid memory leaks.
 */
export function AuthedImage({
  path,
  alt,
  className,
}: {
  path: string; // backend path, e.g. "/api/screenshots/123"
  alt?: string;
  className?: string;
}) {
  const [objectUrl, setObjectUrl] = useState<string | null>(null);
  const [status, setStatus] = useState<"loading" | "ok" | "error">("loading");

  useEffect(() => {
    let revoked = false;
    let createdUrl: string | null = null;
    setStatus("loading");
    setObjectUrl(null);

    const url = path.startsWith("http")
      ? path
      : `${BACKEND_URL.replace(/\/$/, "")}${path.startsWith("/") ? "" : "/"}${path}`;

    const token = getAuthToken();

    fetch(url, {
      headers: token ? { Authorization: `Bearer ${token}` } : {},
    })
      .then(async (res) => {
        if (!res.ok) throw new Error(`HTTP ${res.status}`);
        const blob = await res.blob();
        if (revoked) return;
        createdUrl = URL.createObjectURL(blob);
        setObjectUrl(createdUrl);
        setStatus("ok");
      })
      .catch(() => {
        if (!revoked) setStatus("error");
      });

    return () => {
      revoked = true;
      if (createdUrl) URL.revokeObjectURL(createdUrl);
    };
  }, [path]);

  if (status === "loading") {
    return (
      <div className={`flex items-center justify-center bg-muted ${className ?? ""}`}>
        <Loader2 className="w-5 h-5 animate-spin text-muted-foreground" />
      </div>
    );
  }

  if (status === "error" || !objectUrl) {
    return (
      <div className={`flex flex-col items-center justify-center gap-1 bg-muted text-muted-foreground ${className ?? ""}`}>
        <ImageOff className="w-5 h-5" />
        <span className="text-xs">Screenshot unavailable</span>
      </div>
    );
  }

  // eslint-disable-next-line @next/next/no-img-element
  return <img src={objectUrl} alt={alt ?? ""} className={className} />;
}

/**
 * Fetch an authed resource and open it in a new tab (for the "click to enlarge"
 * behaviour). Because we can't put the token in a plain href, we fetch the blob
 * and open its object URL.
 */
export async function openAuthedInNewTab(path: string) {
  const url = path.startsWith("http")
    ? path
    : `${BACKEND_URL.replace(/\/$/, "")}${path.startsWith("/") ? "" : "/"}${path}`;
  const token = getAuthToken();
  try {
    const res = await fetch(url, {
      headers: token ? { Authorization: `Bearer ${token}` } : {},
    });
    if (!res.ok) return;
    const blob = await res.blob();
    const objectUrl = URL.createObjectURL(blob);
    window.open(objectUrl, "_blank", "noopener,noreferrer");
    // Revoke after a delay so the new tab has time to load it
    setTimeout(() => URL.revokeObjectURL(objectUrl), 60_000);
  } catch {
    /* no-op */
  }
}
