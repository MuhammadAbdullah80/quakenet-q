"use client";

import Link from "next/link";
import { usePathname, useSearchParams } from "next/navigation";
import { Suspense } from "react";

const PAGES = [
  { href: "/events", label: "Events" },
  { href: "/candidates", label: "Candidates" },
  { href: "/scoring", label: "Scoring" },
  { href: "/quantum", label: "Quantum" },
  { href: "/self-check", label: "Self-check" },
  { href: "/plan", label: "Plan" },
  { href: "/monitor", label: "Monitor" },
  { href: "/memory", label: "Memory" },
  { href: "/system", label: "System" },
] as const;

const EVENT_ID = /^[A-Za-z0-9_-]{1,64}$/;

function NavList({ pathname, event }: { pathname: string | null; event: string | null }) {
  const query = event && EVENT_ID.test(event) ? `?event=${event}` : "";
  return (
    <nav className="nav" aria-label="Modules">
      <ul>
        {PAGES.map((page) => (
          <li key={page.href}>
            <Link
              href={`${page.href}${query}`}
              aria-current={pathname === page.href ? "page" : undefined}
            >
              {page.label}
            </Link>
          </li>
        ))}
      </ul>
    </nav>
  );
}

/** Keeps the selected event in the links when moving between modules. */
function NavWithState() {
  const pathname = usePathname();
  const searchParams = useSearchParams();
  return <NavList pathname={pathname} event={searchParams.get("event")} />;
}

export function Nav() {
  return (
    <Suspense fallback={<NavList pathname={null} event={null} />}>
      <NavWithState />
    </Suspense>
  );
}
