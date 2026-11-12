"use client";

import { useEffect, useState } from "react";

// Table of contents that marks the section being read.
export function GuideToc({ sections }: { sections: readonly { id: string; title: string }[] }) {
  const [active, setActive] = useState<string>(sections[0]?.id ?? "");

  useEffect(() => {
    const els = sections
      .map((s) => document.getElementById(s.id))
      .filter((el): el is HTMLElement => el !== null);
    const io = new IntersectionObserver(
      (entries) => {
        const seen = entries.filter((e) => e.isIntersecting);
        if (seen.length) {
          seen.sort((a, b) => a.boundingClientRect.top - b.boundingClientRect.top);
          setActive(seen[0].target.id);
        }
      },
      { rootMargin: "-15% 0px -70% 0px" },
    );
    els.forEach((el) => io.observe(el));
    return () => io.disconnect();
  }, [sections]);

  return (
    <ol>
      {sections.map((s) => (
        <li key={s.id}>
          <a href={`#${s.id}`} aria-current={active === s.id ? "location" : undefined}>
            {s.title}
          </a>
        </li>
      ))}
    </ol>
  );
}
