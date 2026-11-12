import type { Metadata } from "next";
import { cookies } from "next/headers";
import { Suspense } from "react";
import { SettingsForm } from "@/components/SettingsForm";
import { Loading, OfflineBanner, Problem } from "@/components/States";
import { loadSettings } from "@/lib/data";
import { fmt } from "@/lib/format";
import { passcodeConfigured, RUN_COOKIE, runCookieValid } from "@/lib/passcode";

export const metadata: Metadata = { title: "Settings" };

export default function SettingsPage() {
  return (
    <>
      <h1>Settings</h1>
      <p className="lede">
        The numbers the agent works with, such as the earthquake size that starts it. Anyone can
        read them; saving changes needs the team passcode.
      </p>
      <Suspense fallback={<Loading label="Loading the settings" />}>
        <SettingsContent />
      </Suspense>
    </>
  );
}

async function SettingsContent() {
  const [settings, cookieStore] = await Promise.all([loadSettings(), cookies()]);
  const data = settings.state === "live" || settings.state === "snapshot" ? settings.data : null;
  return (
    <>
      <OfflineBanner results={[settings]} />
      <Problem result={settings} what="the settings" />
      {data ? (
        <>
          {typeof data.trigger_magnitude === "number" ? (
            <div className="notice notice-info">
              <p className="notice-title">Trigger magnitude: {fmt(data.trigger_magnitude, 1)}</p>
              <p>
                The agent starts on earthquakes of this magnitude or larger. Smaller earthquakes in
                the live feed are listed but ignored.
                {data.live_enabled === true
                  ? " Live mode is on, so the agent starts by itself."
                  : " Live mode is off, so the agent only starts when someone presses the button on the Live feed page."}
              </p>
            </div>
          ) : null}
          <SettingsForm
            initial={data}
            backendOnline={settings.state === "live"}
            passcodeSet={passcodeConfigured()}
            initiallyUnlocked={runCookieValid(cookieStore.get(RUN_COOKIE)?.value)}
          />
        </>
      ) : null}
    </>
  );
}
