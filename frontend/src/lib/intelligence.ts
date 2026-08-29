/**
 * Shared visual helpers for the Application Intelligence UI.
 *
 * These map backend risk levels / coverage states to consistent, theme-token
 * styling so every screen (graph, coverage, PR) reads the same way. We use
 * semantic Tailwind tokens where possible and a small, restrained set of
 * risk/coverage accent colors that sit well on the dark internal theme.
 */

export type RiskLevel = "Critical" | "High" | "Medium" | "Low" | "Trivial";
export type CoverageState = "covered" | "partially_covered" | "uncovered" | "undetermined";

// Risk → text/border/bg accent classes. Critical/High lean on the destructive
// token; Medium is amber; Low/Trivial recede into muted.
export function riskClasses(level?: string): {
  text: string;
  bg: string;
  border: string;
  dot: string;
} {
  switch ((level || "Trivial") as RiskLevel) {
    case "Critical":
      return {
        text: "text-destructive",
        bg: "bg-destructive/10",
        border: "border-destructive/40",
        dot: "bg-destructive",
      };
    case "High":
      return {
        text: "text-destructive/90",
        bg: "bg-destructive/5",
        border: "border-destructive/30",
        dot: "bg-destructive/80",
      };
    case "Medium":
      return {
        text: "text-amber-500",
        bg: "bg-amber-500/10",
        border: "border-amber-500/30",
        dot: "bg-amber-500",
      };
    case "Low":
      return {
        text: "text-muted-foreground",
        bg: "bg-muted",
        border: "border-border",
        dot: "bg-muted-foreground/60",
      };
    default: // Trivial
      return {
        text: "text-muted-foreground",
        bg: "bg-muted",
        border: "border-border",
        dot: "bg-muted-foreground/40",
      };
  }
}

// Coverage → label + accent. Covered=success, partial=amber, uncovered=muted-red,
// undetermined=neutral.
export function coverageMeta(state?: string): {
  label: string;
  text: string;
  bg: string;
  dot: string;
} {
  switch ((state || "undetermined") as CoverageState) {
    case "covered":
      return { label: "Covered", text: "text-success", bg: "bg-success/10", dot: "bg-success" };
    case "partially_covered":
      return { label: "Partial", text: "text-amber-500", bg: "bg-amber-500/10", dot: "bg-amber-500" };
    case "uncovered":
      return { label: "Uncovered", text: "text-destructive/80", bg: "bg-destructive/5", dot: "bg-destructive/70" };
    default:
      return { label: "Undetermined", text: "text-muted-foreground", bg: "bg-muted", dot: "bg-muted-foreground/40" };
  }
}

// Node type → a short glyph label used on graph nodes.
export function nodeTypeLabel(t?: string): string {
  const m: Record<string, string> = {
    page: "Page",
    form: "Form",
    flow: "Flow",
    action: "Action",
    role: "Role",
  };
  return m[(t || "page").toLowerCase()] || "Page";
}

// Business category → a human label + hue for grouping lanes.
export function categoryLabel(cat?: string | null): string {
  if (!cat) return "Uncategorized";
  return cat.charAt(0).toUpperCase() + cat.slice(1);
}
