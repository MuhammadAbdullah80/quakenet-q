"use client";

import { useState, type FormEvent } from "react";
import { PasscodeGate } from "@/components/PasscodeGate";
import { errorMessage, readJson, type Message } from "@/lib/client-api";
import { fmtTime } from "@/lib/format";
import type { Settings } from "@/lib/schemas";
import {
  BOOLEAN_SETTINGS,
  NUMBER_SETTINGS,
  rangeOf,
  settingsUpdateSchema,
} from "@/lib/settings-fields";

type Props = {
  initial: Settings;
  backendOnline: boolean;
  passcodeSet: boolean;
  initiallyUnlocked: boolean;
};

type Values = Record<string, number | boolean | undefined>;

export function SettingsForm({ initial, backendOnline, passcodeSet, initiallyUnlocked }: Props) {
  const [settings, setSettings] = useState<Settings>(initial);
  const [unlocked, setUnlocked] = useState(initiallyUnlocked);
  const [errors, setErrors] = useState<Record<string, string>>({});
  const [message, setMessage] = useState<Message | null>(null);
  const [saving, setSaving] = useState(false);
  // Changes after each save, so the inputs are re-created with the saved values.
  const [version, setVersion] = useState(0);

  const values = settings as unknown as Values;
  const limits = settings.limits ?? null;
  const numberFields = NUMBER_SETTINGS.filter((f) => typeof values[f.key] === "number");
  const booleanFields = BOOLEAN_SETTINGS.filter((f) => typeof values[f.key] === "boolean");
  const canSave = backendOnline && passcodeSet && unlocked && !saving;

  async function save(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    const form = new FormData(event.currentTarget);
    const body: Record<string, number | boolean> = {};
    for (const field of numberFields) {
      const raw = String(form.get(field.key) ?? "").trim();
      body[field.key] = raw === "" ? Number.NaN : Number(raw);
    }
    for (const field of booleanFields) body[field.key] = form.get(field.key) === "on";

    const parsed = settingsUpdateSchema(limits).safeParse(body);
    if (!parsed.success) {
      const next: Record<string, string> = {};
      for (const issue of parsed.error.issues) {
        const key = String(issue.path[0] ?? "");
        const field = NUMBER_SETTINGS.find((f) => f.key === key);
        if (!field || next[key]) continue;
        const [min, max] = rangeOf(field, limits);
        next[key] = `Enter ${field.integer ? "a whole number" : "a number"} from ${min} to ${max}.`;
      }
      setErrors(next);
      setMessage({
        tone: "error",
        text: "Some values are outside the allowed range. Nothing was saved.",
      });
      return;
    }

    setErrors({});
    setSaving(true);
    setMessage(null);
    try {
      const response = await fetch("/api/settings", {
        method: "PUT",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(parsed.data),
      });
      const reply = await readJson(response);
      if (response.ok && reply && typeof reply === "object") {
        setSettings(reply as Settings);
        setVersion((v) => v + 1);
        setMessage({ tone: "info", text: "Settings saved." });
      } else {
        if (response.status === 401) setUnlocked(false);
        setMessage({
          tone: "error",
          text: errorMessage(response.status, reply, response.headers.get("retry-after")),
        });
      }
    } catch {
      setMessage({ tone: "error", text: "The request could not be sent. Check your connection." });
    } finally {
      setSaving(false);
    }
  }

  return (
    <section className="panel" aria-labelledby="settings-heading">
      <h2 id="settings-heading">Agent settings</h2>
      <p className="small muted">Last saved: {fmtTime(settings.updated_utc)}</p>

      <PasscodeGate
        action="save settings"
        backendOnline={backendOnline}
        passcodeSet={passcodeSet}
        unlocked={unlocked}
        onChange={setUnlocked}
        idPrefix="settings"
      />

      <form onSubmit={save} noValidate key={version}>
        <fieldset disabled={!canSave} className="panel">
          <legend>Numbers</legend>
          <div className="fields">
            {numberFields.map((field) => {
              const [min, max] = rangeOf(field, limits);
              const error = errors[field.key];
              const hintId = `${field.key}-hint`;
              const errorId = `${field.key}-error`;
              return (
                <div className="field setting-field" key={field.key}>
                  <label htmlFor={field.key}>{field.label}</label>
                  <input
                    id={field.key}
                    name={field.key}
                    type="number"
                    required
                    step={field.integer ? 1 : "any"}
                    min={min}
                    max={max}
                    defaultValue={values[field.key] as number}
                    aria-invalid={error ? true : undefined}
                    aria-describedby={error ? `${hintId} ${errorId}` : hintId}
                  />
                  <span className="hint" id={hintId}>
                    Allowed: {min} to {max}
                    {field.integer ? ", whole number" : ""}. {field.help}
                  </span>
                  {error ? (
                    <span className="field-error" id={errorId}>
                      {error}
                    </span>
                  ) : null}
                </div>
              );
            })}
          </div>
        </fieldset>

        {booleanFields.length > 0 ? (
          <fieldset disabled={!canSave} className="panel">
            <legend>Switches</legend>
            {booleanFields.map((field) => (
              <div className="checkbox-field" key={field.key}>
                <input
                  id={field.key}
                  name={field.key}
                  type="checkbox"
                  defaultChecked={values[field.key] === true}
                  aria-describedby={`${field.key}-hint`}
                />
                <label htmlFor={field.key}>{field.label}</label>
                <span className="hint" id={`${field.key}-hint`}>
                  {field.help}
                </span>
              </div>
            ))}
          </fieldset>
        ) : null}

        <button type="submit" disabled={!canSave}>
          {saving ? "Saving" : "Save settings"}
        </button>
      </form>

      <div aria-live="polite">
        {message ? (
          <p className={`notice ${message.tone === "error" ? "notice-error" : "notice-info"}`}>
            {message.text}
          </p>
        ) : null}
      </div>
    </section>
  );
}
