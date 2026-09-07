"use client";

import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import { Plus, Play, Layers, Clock } from "lucide-react";
import { useState } from "react";
import { formatDistanceToNow } from "date-fns";

import { api } from "@/lib/api";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { Skeleton } from "@/components/ui/skeleton";
import { Dialog, DialogContent, DialogHeader, DialogTitle, DialogFooter } from "@/components/ui/dialog";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Textarea } from "@/components/ui/textarea";

export default function SuitesPage() {
  const queryClient = useQueryClient();
  const [isCreating, setIsCreating] = useState(false);
  const [newSuite, setNewSuite] = useState({ name: "", description: "" });

  const { data: suites, isLoading } = useQuery({
    queryKey: ["suites"],
    queryFn: () => api.listSuites(),
  });

  const createMutation = useMutation({
    mutationFn: () => api.createSuite(newSuite),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["suites"] });
      setIsCreating(false);
      setNewSuite({ name: "", description: "" });
    },
  });

  const triggerMutation = useMutation({
    mutationFn: (id: number) => api.runSuite(id),
    onSuccess: () => {
      alert("Suite triggered successfully! Check the Pipeline Runs page.");
    },
    onError: (err: any) => {
      alert("Failed to trigger suite: " + err.message);
    }
  });

  return (
    <div className="space-y-6 max-w-5xl">
      <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-4">
        <div>
          <h1 className="text-2xl font-semibold tracking-tight">Test Suites</h1>
          <p className="text-sm text-muted-foreground mt-1">
            Group multiple tests together to trigger them as a single CI/CD pipeline execution.
          </p>
        </div>
        <Button onClick={() => setIsCreating(true)} className="gap-2">
          <Plus className="h-4 w-4" /> New suite
        </Button>
      </div>

      {isLoading ? (
        <div className="space-y-4">
          {[1, 2, 3].map((i) => (
            <Skeleton key={i} className="h-24 w-full" />
          ))}
        </div>
      ) : suites?.length === 0 ? (
        <Card className="border-dashed bg-muted/30">
          <CardContent className="flex flex-col items-center justify-center py-12 text-center">
            <div className="h-12 w-12 rounded-full bg-primary/10 flex items-center justify-center mb-4">
              <Layers className="h-6 w-6 text-primary" />
            </div>
            <h3 className="text-lg font-semibold mb-1">No test suites yet</h3>
            <p className="text-sm text-muted-foreground max-w-sm mb-6">
              Create a test suite to group related test cases and run them together in parallel.
            </p>
            <Button onClick={() => setIsCreating(true)}>Create your first suite</Button>
          </CardContent>
        </Card>
      ) : (
        <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-6">
          {suites?.map((suite) => (
            <Card key={suite.id} className="hover:border-primary/50 transition-colors group">
              <CardHeader className="pb-3">
                <CardTitle className="flex items-start justify-between">
                  <span className="truncate pr-4">{suite.name}</span>
                  <div className="h-8 w-8 rounded bg-primary/10 flex items-center justify-center flex-shrink-0">
                    <Layers className="h-4 w-4 text-primary" />
                  </div>
                </CardTitle>
                <CardDescription className="line-clamp-2 min-h-[40px]">
                  {suite.description || "No description provided."}
                </CardDescription>
              </CardHeader>
              <CardContent>
                <div className="flex items-center justify-between text-sm text-muted-foreground pt-4 border-t">
                  <div className="flex items-center gap-1.5">
                    <Clock className="h-3.5 w-3.5" />
                    <span>{formatDistanceToNow(new Date(suite.created_at), { addSuffix: true })}</span>
                  </div>
                  <Button 
                    variant="ghost" 
                    size="sm" 
                    className="h-8 px-2 text-primary opacity-0 group-hover:opacity-100 transition-opacity"
                    onClick={() => triggerMutation.mutate(suite.id)}
                    disabled={triggerMutation.isPending}
                  >
                    <Play className="h-4 w-4 mr-1.5" fill="currentColor" /> Run Suite
                  </Button>
                </div>
              </CardContent>
            </Card>
          ))}
        </div>
      )}

      <Dialog open={isCreating} onOpenChange={setIsCreating}>
        <DialogContent>
          <DialogHeader>
            <DialogTitle>Create a Test Suite</DialogTitle>
          </DialogHeader>
          <div className="space-y-4 py-4">
            <div className="space-y-2">
              <Label htmlFor="name">Suite Name</Label>
              <Input 
                id="name" 
                placeholder="e.g., E2E Checkout Flow" 
                value={newSuite.name}
                onChange={(e) => setNewSuite({ ...newSuite, name: e.target.value })}
              />
            </div>
            <div className="space-y-2">
              <Label htmlFor="description">Description (Optional)</Label>
              <Textarea 
                id="description" 
                placeholder="What tests are grouped here?" 
                value={newSuite.description}
                onChange={(e) => setNewSuite({ ...newSuite, description: e.target.value })}
              />
            </div>
          </div>
          <DialogFooter>
            <Button variant="outline" onClick={() => setIsCreating(false)}>Cancel</Button>
            <Button 
              onClick={() => createMutation.mutate()} 
              disabled={!newSuite.name || createMutation.isPending}
            >
              {createMutation.isPending ? "Creating..." : "Create Suite"}
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>
    </div>
  );
}
