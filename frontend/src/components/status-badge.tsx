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
          className={cn(
            "bg-muted/40 text-muted-foreground border-border gap-1",
          )}
        >
          <CircleDashed className="w-3 h-3" />
          Pending
        </Badge>
      );
    case "running":
      return (
        <Badge
          variant="secondary"
          className="gap-1 bg-blue-500/10 text-blue-700 dark:text-blue-300 border-blue-500/20"
        >
          <Loader2 className="w-3 h-3 animate-spin" />
          Running
        </Badge>
      );
    case "completed":
      return (
        <Badge
          variant="secondary"
          className="gap-1 bg-emerald-500/10 text-emerald-700 dark:text-emerald-300 border-emerald-500/20"
        >
          <CheckCircle2 className="w-3 h-3" />
          Passed
        </Badge>
      );
    case "failed":
      return (
        <Badge
          variant="destructive"
          className="gap-1"
        >
          <XCircle className="w-3 h-3" />
          Failed
        </Badge>
      );
    case "cancelled":
      return (
        <Badge variant="outline" className="gap-1">
          <Ban className="w-3 h-3" />
          Cancelled
        </Badge>
      );
  }
}
