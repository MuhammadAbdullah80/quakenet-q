"use client";

import Link, { useLinkStatus } from "next/link";
import { usePathname, useSearchParams } from "next/navigation";
import { Suspense, useEffect, useRef, type CSSProperties } from "react";

const PAGES = [
  { href: "/events", label: "Events" },
  { href: "/feed", label: "Live feed" },
  { href: "/candidates", label: "Candidates" },
  { href: "/scoring", label: "Scoring" },
  { href: "/quantum", label: "Quantum" },
  { href: "/self-check", label: "Self-check" },
  { href: "/plan", label: "Plan" },
  { href: "/monitor", label: "Monitor" },
  { href: "/memory", label: "Memory" },
  { href: "/noise", label: "Noise study" },
  { href: "/settings", label: "Settings" },
  { href: "/system", label: "System" },
  { href: "/guide", label: "Guide" },
] as const;

const EVENT_ID = /^[A-Za-z0-9_-]{1,64}$/;

/** A lime dot that pulses while the clicked page loads, like a sensor recording. */
function Pending() {
  const { pending } = useLinkStatus();
  return <span aria-hidden="true" className={pending ? "nav-pending is-on" : "nav-pending"} />;
}

function NavList({ pathname, event }: { pathname: string | null; event: string | null }) {
  const query = event && EVENT_ID.test(event) ? `?event=${event}` : "";
  const here = PAGES.findIndex((page) => page.href === pathname);
  const listRef = useRef<HTMLUListElement>(null);

  // One indicator glides to the current page; a highlight follows the pointer or keyboard focus.
  // Positions go straight to CSS variables, so nothing re-renders while it moves.
  useEffect(() => {
    const list = listRef.current;
    if (!list) return;
    const place = (name: "ind" | "hov", el: HTMLElement | null) => {
      if (!el) {
        list.style.setProperty(`--${name}-o`, "0");
        return;
      }
      list.style.setProperty(`--${name}-x`, `${el.offsetLeft}px`);
      list.style.setProperty(`--${name}-w`, `${el.offsetWidth}px`);
      list.style.setProperty(`--${name}-o`, "1");
    };
    const current = () => list.querySelector<HTMLElement>('a[aria-current="page"]');
    const sync = () => place("ind", current());
    sync();
    list.dataset.ready = "true";
    // Keep the current page in view when the list scrolls sideways on phones.
    const active = current();
    if (active && list.scrollWidth > list.clientWidth) {
      const reduce = window.matchMedia("(prefers-reduced-motion: reduce)").matches;
      list.scrollTo({
        left: active.offsetLeft - (list.clientWidth - active.offsetWidth) / 2,
        behavior: reduce ? "auto" : "smooth",
      });
    }
    const over = (e: Event) => {
      const a = (e.target as HTMLElement).closest("a");
      if (a && list.contains(a)) place("hov", a);
    };
    const out = (e: PointerEvent | FocusEvent) => {
      const next = e.relatedTarget as Node | null;
      if (!next || !list.contains(next)) place("hov", null);
    };
    const edges = () => {
      list.dataset.start = String(list.scrollLeft < 4);
      list.dataset.end = String(list.scrollLeft + list.clientWidth > list.scrollWidth - 4);
    };
    edges();
    const ro = new ResizeObserver(() => {
      sync();
      edges();
    });
    ro.observe(list);
    list.addEventListener("pointerover", over);
    list.addEventListener("focusin", over);
    list.addEventListener("pointerout", out);
    list.addEventListener("focusout", out);
    list.addEventListener("scroll", edges, { passive: true });
    return () => {
      ro.disconnect();
      list.removeEventListener("pointerover", over);
      list.removeEventListener("focusin", over);
      list.removeEventListener("pointerout", out);
      list.removeEventListener("focusout", out);
      list.removeEventListener("scroll", edges);
    };
  }, [pathname]);

  return (
    <nav className="nav" aria-label="Modules">
      <ul ref={listRef} style={{ "--ind-o": 0, "--hov-o": 0 } as CSSProperties}>
        {PAGES.map((page, i) => (
          <li key={page.href}>
            <Link
              href={`${page.href}${query}`}
              aria-current={pathname === page.href ? "page" : undefined}
              // Later steps slide in from the right, earlier ones from the left.
              transitionTypes={
                here < 0 || i === here ? undefined : [i > here ? "nav-forward" : "nav-back"]
              }
            >
              {page.label}
              <Pending />
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
