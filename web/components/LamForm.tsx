import { LIMITS } from "@/lib/limits";

/** GET form that reloads the page with another risk weight. */
export function LamForm({
  action,
  eventId,
  lam,
  disabled,
}: {
  action: string;
  eventId: string;
  lam: number;
  disabled: boolean;
}) {
  return (
    <form action={action} method="get" className="panel">
      <input type="hidden" name="event" value={eventId} />
      <div className="fields">
        <div className="field">
          <label htmlFor="lam">Risk weight (lam)</label>
          <input
            id="lam"
            name="lam"
            type="number"
            required
            step="any"
            min={LIMITS.lam.min}
            max={LIMITS.lam.max}
            defaultValue={lam}
            disabled={disabled}
            aria-describedby="lam-hint"
          />
          <span className="hint" id="lam-hint">
            {LIMITS.lam.min} to {LIMITS.lam.max}. How much information one unit of access risk must
            buy. Default {LIMITS.lam.default}.
            {disabled ? " Fixed while offline: the snapshot was saved for this value." : ""}
          </span>
        </div>
        <button type="submit" disabled={disabled}>
          Recalculate
        </button>
      </div>
    </form>
  );
}
