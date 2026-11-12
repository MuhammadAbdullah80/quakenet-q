"use client";

export default function ErrorPage({ reset }: { error: Error & { digest?: string }; reset: () => void }) {
  return (
    <div className="notice notice-error" role="alert" aria-live="assertive">
      <p className="notice-title">Something went wrong on this page</p>
      <p>The details were written to the server log. You can try again.</p>
      <p>
        <button type="button" onClick={() => reset()}>
          Try again
        </button>
      </p>
    </div>
  );
}
