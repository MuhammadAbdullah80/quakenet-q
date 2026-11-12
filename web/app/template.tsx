import { ViewTransition, type ReactNode } from "react";
import { CountUp } from "@/components/CountUp";
import { PageTrace } from "@/components/PageTrace";
import { StepStrip } from "@/components/StepStrip";

// A template remounts on every navigation, so each page enters and leaves through this boundary.
// The nav marks a move to a later step as "nav-forward" and an earlier one as "nav-back" (the
// pages follow the pipeline in order); any other link crossfades. The header is outside it.
export default function Template({ children }: { children: ReactNode }) {
  return (
    <ViewTransition
      enter={{ "nav-forward": "nav-forward", "nav-back": "nav-back", default: "page-fade" }}
      exit={{ "nav-forward": "nav-forward", "nav-back": "nav-back", default: "page-fade" }}
      default="none"
    >
      <div className="page">
        <StepStrip />
        <CountUp />
        <PageTrace />
        {children}
      </div>
    </ViewTransition>
  );
}
