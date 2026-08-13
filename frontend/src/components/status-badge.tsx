"use client";

import { Badge } from "@/components/ui/badge";
import {
  CheckCircle2,
  CircleDashed,
  Loader2,
  XCircle,
  Ban,
} from "lucide-react";
import { cn } from "@/lib/utils";
import type { RunStatus } from "@/lib/api";

export function StatusBadge({ status }: { status: RunStatus }) {
  switch (status) {
    case "pending":
      return (
        <Badge
          variant="outline"
          className="rounded-full bg-muted/40 text-muted-foreground border-border uppercase tracking-widest text-[9px] font-semibold px-2.5 py-0.5"
        >
          PENDING
        </Badge>
      );
    case "running":
      return (
        <Badge
          variant="secondary"
          className="gap-1.5 rounded-full bg-blue-500/10 text-blue-400 border-blue-500/20 uppercase tracking-widest text-[9px] font-semibold px-2.5 py-0.5"
        >
          <Loader2 className="w-3 h-3 animate-spin" />
          RUNNING
        </Badge>
      );
    case "completed":
      return (
        <Badge
          variant="secondary"
          className="rounded-full bg-emerald-500/10 text-emerald-400 border border-emerald-500/20 uppercase tracking-widest text-[9px] font-semibold px-2.5 py-0.5"
        >
          PASSED
        </Badge>
      );
    case "failed":
      return (
        <Badge
          variant="destructive"
          className="rounded-full bg-rose-500/10 text-rose-400 border border-rose-500/20 uppercase tracking-widest text-[9px] font-semibold px-2.5 py-0.5"
        >
          FAILED
        </Badge>
      );
    case "cancelled":
      return (
        <Badge variant="outline" className="rounded-full uppercase tracking-widest text-[9px] font-semibold px-2.5 py-0.5">
          CANCELLED
        </Badge>
      );
  }
}
