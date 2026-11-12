"use client";

import { useState, type FormEvent } from "react";
import { errorMessage, readJson, type Message } from "@/lib/client-api";

// Unlock form for actions that need the team passcode (starting the agent,
// saving settings). The passcode is checked by /api/passcode, which sets an
// httpOnly cookie; this component only knows whether it succeeded.

type Props = {
  /** What the passcode unlocks, for example "save settings". */
  action: string;
  backendOnline: boolean;
  passcodeSet: boolean;
  unlocked: boolean;
  onChange: (unlocked: boolean) => void;
  /** Distinguishes several gates on one page. */
  idPrefix: string;
};

export function PasscodeGate({
  action,
  backendOnline,
  passcodeSet,
  unlocked,
  onChange,
  idPrefix,
}: Props) {
  const [message, setMessage] = useState<Message | null>(null);
  const [busy, setBusy] = useState(false);

  async function submit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    const formElement = event.currentTarget;
    const passcode = String(new FormData(formElement).get("passcode") ?? "");
    setBusy(true);
    setMessage(null);
    try {
      const response = await fetch("/api/passcode", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ passcode }),
      });
      if (response.ok) {
        formElement.reset();
        onChange(true);
        setMessage({ tone: "info", text: "Passcode accepted on this browser." });
      } else {
        const body = await readJson(response);
        setMessage({
          tone: "error",
          text:
            response.status === 401
              ? "That passcode is not correct."
              : errorMessage(response.status, body, response.headers.get("retry-after")),
        });
      }
    } catch {
      setMessage({ tone: "error", text: "The request could not be sent. Check your connection." });
    } finally {
      setBusy(false);
    }
  }

  async function forget() {
    try {
      await fetch("/api/passcode", { method: "DELETE" });
    } finally {
      onChange(false);
      setMessage({ tone: "info", text: "Passcode forgotten on this browser." });
    }
  }

  if (!backendOnline) {
    return (
      <p className="notice notice-warn">
        You cannot {action} while the backend is offline.
      </p>
    );
  }
  if (!passcodeSet) {
    return (
      <p className="notice notice-warn">
        You cannot {action}: no team passcode is configured on this deployment (RUN_PASSCODE).
      </p>
    );
  }
  return (
    <div>
      {unlocked ? (
        <p className="small">
          <button type="button" className="secondary" onClick={forget}>
            Forget passcode on this browser
          </button>
        </p>
      ) : (
        <form onSubmit={submit} aria-describedby={`${idPrefix}-passcode-help`}>
          <p id={`${idPrefix}-passcode-help`}>
            To {action} you need the team passcode. Reading results does not.
          </p>
          <div className="fields">
            <div className="field">
              <label htmlFor={`${idPrefix}-passcode`}>Team passcode</label>
              <input
                id={`${idPrefix}-passcode`}
                name="passcode"
                type="password"
                autoComplete="current-password"
                required
                maxLength={200}
              />
            </div>
            <button type="submit" disabled={busy}>
              Unlock
            </button>
          </div>
        </form>
      )}
      <div aria-live="polite">
        {message ? (
          <p className={`notice ${message.tone === "error" ? "notice-error" : "notice-info"}`}>
            {message.text}
          </p>
        ) : null}
      </div>
    </div>
  );
}
