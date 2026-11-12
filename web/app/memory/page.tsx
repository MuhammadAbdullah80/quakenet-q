import type { Metadata } from "next";
import { Suspense } from "react";
import { ModuleProbe } from "@/components/ModuleProbe";
import { Loading } from "@/components/States";
import { loadUnspecified } from "@/lib/data";

export const metadata: Metadata = { title: "Memory" };

export default function MemoryPage() {
  return (
    <>
      <h1>Memory</h1>
      <p className="lede">
        What the agent keeps between earthquakes: stored circuit angles, model weights and its
        track record.
      </p>
      <Suspense fallback={<Loading label="Asking the backend" />}>
        <MemoryContent />
      </Suspense>
    </>
  );
}

async function MemoryContent() {
  const result = await loadUnspecified("/memory");
  return <ModuleProbe result={result} what="The memory module" />;
}
