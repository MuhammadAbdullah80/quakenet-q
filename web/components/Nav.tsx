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
  { href: "/guide", label: "Guide" },
] as const;

// Less used pages sit under "More" so the main row stays short.
const MORE = [
  { href: "/demo", label: "Demo" },
  { href: "/memory", label: "Memory" },
  { href: "/noise", label: "Noise study" },
  { href: "/settings", label: "Settings" },
  { href: "/system", label: "System" },
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
    const current = () =>
      list.querySelector<HTMLElement>(':scope > li > a[aria-current="page"]') ??
      list.querySelector<HTMLElement>(".nav-more[data-current] > summary");
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
      // Only items in the main row get the highlight, not links inside the More menu.
      const a = (e.target as HTMLElement).closest<HTMLElement>("a, summary");
      if (!a) return;
      const item = a.tagName === "SUMMARY" ? a : a.parentElement?.parentElement === list ? a : null;
      if (item) place("hov", item);
    };
    // The More menu: fixed position so the scrolling row does not clip it; closes on navigation,
    // outside click and Escape.
    const more = list.querySelector<HTMLDetailsElement>("details.nav-more");
    more?.removeAttribute("open");
    const placeMenu = () => {
      const menu = more?.querySelector<HTMLElement>(".nav-more-list");
      const summary = more?.querySelector<HTMLElement>("summary");
      if (!more?.open || !menu || !summary) return;
      const r = summary.getBoundingClientRect();
      menu.style.top = `${Math.round(r.bottom + 6)}px`;
      menu.style.left = `${Math.round(Math.min(r.left, window.innerWidth - menu.offsetWidth - 12))}px`;
    };
    const onToggle = () => placeMenu();
    const onDocClick = (e: MouseEvent) => {
      if (more?.open && !more.contains(e.target as Node)) more.removeAttribute("open");
    };
    const onKey = (e: KeyboardEvent) => {
      if (e.key === "Escape" && more?.open) {
        more.removeAttribute("open");
        more.querySelector("summary")?.focus();
      }
    };
    more?.addEventListener("toggle", onToggle);
    document.addEventListener("click", onDocClick);
    document.addEventListener("keydown", onKey);
    window.addEventListener("scroll", placeMenu, { passive: true });
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
      more?.removeEventListener("toggle", onToggle);
      document.removeEventListener("click", onDocClick);
      document.removeEventListener("keydown", onKey);
      window.removeEventListener("scroll", placeMenu);
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
        <li>
          <details
            className="nav-more"
            data-current={MORE.some((page) => page.href === pathname) ? "" : undefined}
          >
            <summary>
              More
              <span className="nav-more-chevron" aria-hidden="true" />
            </summary>
            <ul className="nav-more-list">
              {MORE.map((page) => (
                <li key={page.href}>
                  <Link
                    href={`${page.href}${query}`}
                    aria-current={pathname === page.href ? "page" : undefined}
                  >
                    {page.label}
                    <Pending />
                  </Link>
                </li>
              ))}
            </ul>
          </details>
        </li>
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
