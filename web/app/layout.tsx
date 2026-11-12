import type { Metadata } from "next";
import { IBM_Plex_Mono, IBM_Plex_Sans, IBM_Plex_Sans_Condensed } from "next/font/google";
import Link from "next/link";
import type { ReactNode } from "react";
import { Nav } from "@/components/Nav";
import "./globals.css";

// next/font self-hosts these files, so the CSP's font-src 'self' still holds.
const plexHead = IBM_Plex_Sans_Condensed({
  subsets: ["latin"],
  weight: ["500", "600", "700"],
  variable: "--font-head",
});
const plexBody = IBM_Plex_Sans({
  subsets: ["latin"],
  weight: ["400", "500", "600"],
  variable: "--font-body",
});
const plexMono = IBM_Plex_Mono({
  subsets: ["latin"],
  weight: ["400", "500"],
  variable: "--font-mono",
});

export const metadata: Metadata = {
  title: { default: "QuakeNet-Q test console", template: "%s | QuakeNet-Q test console" },
  description:
    "Test console for QuakeNet-Q: choosing where 4 portable seismometers go out of 10 candidate sites after an earthquake.",
  robots: { index: false, follow: false },
};

export default function RootLayout({ children }: { children: ReactNode }) {
  return (
    <html lang="en" className={`${plexHead.variable} ${plexBody.variable} ${plexMono.variable}`}>
      <body>
        <a className="skip-link" href="#main">
          Skip to content
        </a>
        <header className="site-header">
          <div className="site-header-inner">
            <p className="brand">
              <Link href="/events">
                <span className="brand-mark" aria-hidden="true" />
                QuakeNet-Q
              </Link>
            </p>
            <p className="tagline">
              Where should 4 portable seismometers go, out of 10 candidate sites? One page per
              module.
            </p>
            <Nav />
          </div>
        </header>
        <main id="main">{children}</main>
        <footer className="site-footer">
          <div className="site-footer-inner">
            <p>
              Proof of concept. The quantum circuit runs on a simulator and claims no speedup.
            </p>
            <p>
              Earthquake data: U.S. Geological Survey. Station data: EarthScope. Elevation: Mapzen
              Terrain Tiles on AWS, data courtesy of the U.S. Geological Survey.
            </p>
          </div>
        </footer>
      </body>
    </html>
  );
}
