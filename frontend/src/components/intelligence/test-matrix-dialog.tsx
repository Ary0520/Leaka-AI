"use client";

import { useState } from "react";
import { useRouter } from "next/navigation";
import { useMutation, useQueryClient } from "@tanstack/react-query";
import { api } from "@/lib/api";
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogHeader,
  DialogTitle,
} from "@/components/ui/dialog";
import { Button } from "@/components/ui/button";
import { Loader2, Sparkles, CheckCircle2 } from "lucide-react";
import { toast } from "@/components/ui/use-toast";

interface TestMatrixDialogProps {
  appId: number;
  open: boolean;
  onOpenChange: (open: boolean) => void;
  appMapNodeId?: number;
  graphNodeId?: number;
  nodeLabel?: string;
}

export function TestMatrixDialog({
  appId,
  open,
  onOpenChange,
  appMapNodeId,
  graphNodeId,
  nodeLabel,
}: TestMatrixDialogProps) {
  const router = useRouter();
  const qc = useQueryClient();

  // State to hold generated matrix
  const [matrix, setMatrix] = useState<any[] | null>(null);

  // Mutation to generate the matrix
  const generateMut = useMutation({
    mutationFn: () => api.generateTestMatrix(appId, appMapNodeId, graphNodeId),
    onSuccess: (data) => {
      setMatrix(data.test_cases);
      toast({ title: "Test matrix generated!" });
    },
    onError: (e: Error) => {
      toast({ title: "Failed to generate matrix", description: e.message, variant: "destructive" });
    },
  });

  // Automatically trigger generation when opened if no matrix exists
  // We use a safe effect approach
  if (open && !matrix && !generateMut.isPending && !generateMut.isError && !generateMut.isSuccess) {
    generateMut.mutate();
  }

  const handleClose = () => {
    onOpenChange(false);
    // Reset state after close animation
    setTimeout(() => {
      setMatrix(null);
      generateMut.reset();
    }, 300);
  };

  const handleCreateTest = (tc: any) => {
    // Send to test creation page pre-filled
    const params = new URLSearchParams();
    params.set("name", tc.name);
    params.set("prompt", tc.prompt);
    params.set("success_criteria", tc.success_criteria || "");
    params.set("app_id", String(appId));
    if (graphNodeId) params.set("node_id", String(graphNodeId));
    
    // We could pass assertions but the new page doesn't currently parse complex assertions from URL.
    router.push(`/new?${params.toString()}`);
    handleClose();
  };

  return (
    <Dialog open={open} onOpenChange={handleClose}>
      <DialogContent className="sm:max-w-[700px] max-h-[85vh] overflow-y-auto">
        <DialogHeader>
          <DialogTitle className="flex items-center gap-2">
            <Sparkles className="w-5 h-5 text-amber-500" />
            Test Matrix Drafting Engine
          </DialogTitle>
          <DialogDescription>
            {nodeLabel ? `Generating QA matrix for "${nodeLabel}"` : "Generating comprehensive test cases based on Application Graph..."}
          </DialogDescription>
        </DialogHeader>

        <div className="py-4">
          {generateMut.isPending && (
            <div className="flex flex-col items-center justify-center py-12 space-y-4">
              <Loader2 className="w-8 h-8 animate-spin text-muted-foreground" />
              <p className="text-sm text-muted-foreground animate-pulse">
                Analyzing node semantics and compiling edge cases...
              </p>
            </div>
          )}

          {generateMut.isError && (
            <div className="text-center py-8 text-rose-500">
              <p>Failed to generate tests.</p>
              <Button variant="outline" className="mt-4" onClick={() => generateMut.mutate()}>
                Retry
              </Button>
            </div>
          )}

          {matrix && (
            <div className="space-y-4">
              <p className="text-sm text-muted-foreground mb-4">
                Review the drafted test cases below. You can send any of them directly to the test builder.
              </p>
              {matrix.map((tc, i) => (
                <div key={i} className="border rounded-md p-4 space-y-3 bg-muted/20">
                  <div className="flex items-start justify-between">
                    <div>
                      <h4 className="font-semibold text-sm">{tc.name}</h4>
                    </div>
                    <Button size="sm" onClick={() => handleCreateTest(tc)}>
                      <Sparkles className="w-4 h-4 mr-2" /> Draft in Builder
                    </Button>
                  </div>
                  <div className="text-sm text-muted-foreground bg-background border p-2 rounded whitespace-pre-wrap font-mono text-xs">
                    {tc.prompt}
                  </div>
                  {tc.assertions && tc.assertions.length > 0 && (
                    <div className="flex items-center gap-2 flex-wrap mt-2">
                      <span className="text-[10px] uppercase text-muted-foreground tracking-wider font-semibold">Assertions:</span>
                      {tc.assertions.map((a: any, j: number) => (
                        <span key={j} className="text-[10px] px-1.5 py-0.5 rounded-sm bg-blue-500/10 text-blue-700 dark:text-blue-400 border border-blue-500/20">
                          {a.type} 
                        </span>
                      ))}
                    </div>
                  )}
                </div>
              ))}
            </div>
          )}
        </div>
      </DialogContent>
    </Dialog>
  );
}
