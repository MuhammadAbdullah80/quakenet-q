import type { Metadata } from "next";
import type { ReactNode } from "react";
import { Nav } from "@/components/Nav";
import "./globals.css";

export const metadata: Metadata = {
  title: { default: "QuakeNet-Q test console", template: "%s | QuakeNet-Q test console" },
  description:
    "Test console for QuakeNet-Q: choosing where 4 portable seismometers go out of 10 candidate sites after an earthquake.",
  robots: { index: false, follow: false },
};

export default function RootLayout({ children }: { children: ReactNode }) {
  return (
    <html lang="en">
      <body>
        <a className="skip-link" href="#main">
          Skip to content
        </a>
        <header className="site-header">
          <p className="brand">QuakeNet-Q test console</p>
          <p className="tagline">
            Where should 4 portable seismometers go, out of 10 candidate sites? One page per module.
          </p>
          <Nav />
        </header>
        <main id="main">{children}</main>
        <footer className="site-footer">
          Proof of concept. No quantum speedup is claimed. The quantum circuit is run by the Python
          API on the team laptop.
        </footer>
      </body>
    </html>
  );
}
