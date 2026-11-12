import "server-only";
import { isIP } from "node:net";

/**
 * The visitor's IP as seen by the hosting platform. On Vercel these headers are
 * set by the platform, not by the visitor. Returns null when no valid address
 * is present (the X-Client-IP header is then simply not forwarded).
 */
export function clientIpFrom(headers: Headers): string | null {
  const candidates = [
    headers.get("x-vercel-forwarded-for"),
    headers.get("x-real-ip"),
    headers.get("x-forwarded-for"),
  ];
  for (const value of candidates) {
    const first = value?.split(",")[0]?.trim();
    if (first && isIP(first) !== 0) return first;
  }
  return null;
}
