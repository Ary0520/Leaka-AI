"use client";

import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import { ShieldAlert, ShieldCheck, Clock } from "lucide-react";
import { formatDistanceToNow } from "date-fns";
import Link from "next/link";

import { api } from "@/lib/api";
import { Card, CardContent } from "@/components/ui/card";
import { Skeleton } from "@/components/ui/skeleton";
import { Button } from "@/components/ui/button";

export default function QuarantinePage() {
  const queryClient = useQueryClient();

  const { data: tests, isLoading } = useQuery({
    queryKey: ["quarantine"],
    queryFn: () => api.listQuarantined(),
  });

  const toggleMutation = useMutation({
    mutationFn: (id: number) => api.toggleQuarantine(id),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["quarantine"] });
    },
  });

  return (
    <div className="space-y-6 max-w-5xl">
      <div>
        <h1 className="text-2xl font-semibold tracking-tight">Quarantined Tests</h1>
        <p className="text-sm text-muted-foreground mt-1">
          Tests that are muted to prevent blocking the CI pipeline. They will still run to gather data.
        </p>
      </div>

      {isLoading ? (
        <div className="space-y-4">
          {[1, 2, 3].map((i) => (
            <Skeleton key={i} className="h-16 w-full" />
          ))}
        </div>
      ) : tests?.length === 0 ? (
        <Card className="border-dashed bg-muted/30">
          <CardContent className="flex flex-col items-center justify-center py-12 text-center">
            <div className="h-12 w-12 rounded-full bg-primary/10 flex items-center justify-center mb-4">
              <ShieldCheck className="h-6 w-6 text-primary" />
            </div>
            <h3 className="text-lg font-semibold mb-1">No quarantined tests</h3>
            <p className="text-sm text-muted-foreground max-w-sm">
              Your pipeline is clean. When tests become extremely flaky, you can quarantine them from the Test Cases page.
            </p>
          </CardContent>
        </Card>
      ) : (
        <div className="space-y-4">
          {tests?.map((test) => (
            <Card key={test.id} className="hover:bg-muted/50 transition-colors border-l-4 border-l-orange-500 overflow-hidden">
              <CardContent className="p-4 flex items-center justify-between">
                <div className="flex items-center gap-4">
                  <ShieldAlert className="h-5 w-5 text-orange-500" />
                  <div>
                    <Link href={`/tests`} className="font-medium hover:underline">
                      {test.name}
                    </Link>
                    <div className="flex items-center gap-2 text-xs text-muted-foreground mt-1">
                      <Clock className="h-3 w-3" />
                      Muted {formatDistanceToNow(new Date(test.updated_at), { addSuffix: true })}
                    </div>
                  </div>
                </div>

                <Button 
                  variant="outline" 
                  size="sm"
                  onClick={() => toggleMutation.mutate(test.id)}
                  disabled={toggleMutation.isPending}
                >
                  {toggleMutation.isPending ? "Restoring..." : "Restore to Pipeline"}
                </Button>
              </CardContent>
            </Card>
          ))}
        </div>
      )}
    </div>
  );
}
