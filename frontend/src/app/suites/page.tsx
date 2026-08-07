"use client";

import { useState } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import Link from "next/link";
import { useRouter } from "next/navigation";
import {
  api,
  type TestSuiteOut,
  type TestCaseOut,
  type TestSuiteCreate,
} from "@/lib/api";
import {
  Card,
  CardContent,
  CardDescription,
  CardHeader,
  CardTitle,
} from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Textarea } from "@/components/ui/textarea";
import { Skeleton } from "@/components/ui/skeleton";
import { Separator } from "@/components/ui/separator";
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from "@/components/ui/table";
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
  DialogTrigger,
} from "@/components/ui/dialog";
import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuItem,
  DropdownMenuTrigger,
} from "@/components/ui/dropdown-menu";
import {
  Loader2,
  Plus,
  Play,
  Trash2,
  MoreHorizontal,
  Layers,
  FileText,
  ChevronRight,
  CheckCircle2,
  AlertCircle,
} from "lucide-react";
import { toast } from "@/components/ui/use-toast";
import { formatDate, truncate } from "@/lib/utils";

export default function SuitesPage() {
  const router = useRouter();
  const qc = useQueryClient();
  const [createOpen, setCreateOpen] = useState(false);
  const [suiteName, setSuiteName] = useState("");
  const [suiteDesc, setSuiteDesc] = useState("");

  const { data: suites, isLoading } = useQuery({
    queryKey: ["suites"],
    queryFn: () => api.listSuites({ limit: 100 }),
  });

  const createMut = useMutation({
    mutationFn: (body: TestSuiteCreate) => api.createSuite(body),
    onSuccess: (s) => {
      qc.invalidateQueries({ queryKey: ["suites"] });
      toast({ title: "Suite created", description: s.name });
      setSuiteName("");
      setSuiteDesc("");
      setCreateOpen(false);
    },
    onError: (e: Error) =>
      toast({
        title: "Failed to create suite",
        description: e.message,
        variant: "destructive",
      }),
  });

  const deleteMut = useMutation({
    mutationFn: (id: number) => api.deleteSuite(id),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ["suites"] });
      toast({ title: "Suite deleted" });
    },
    onError: (e: Error) =>
      toast({
        title: "Delete failed",
        description: e.message,
        variant: "destructive",
      }),
  });

  const runMut = useMutation({
    mutationFn: (id: number) => api.runSuite(id, { use_vision: true, max_steps: 100 }),
    onSuccess: (res) => {
      toast({
        title: `Suite enqueued — ${res.count} run(s)`,
        description: `Job IDs: ${res.job_ids.slice(0, 3).map((j) => j.slice(0, 8)).join(", ")}…`,
      });
      // Navigate to first job
      if (res.job_ids[0]) router.push(`/runs/${res.job_ids[0]}`);
    },
    onError: (e: Error) =>
      toast({
        title: "Failed to run suite",
        description: e.message,
        variant: "destructive",
      }),
  });

  return (
    <div className="space-y-6">
      <div className="flex items-start justify-between flex-wrap gap-4">
        <div>
          <h1 className="text-2xl font-semibold tracking-tight">Test Suites</h1>
          <p className="text-sm text-muted-foreground mt-1">
            Group related test cases and run them all with one click or from CI.
          </p>
        </div>
        <Dialog open={createOpen} onOpenChange={setCreateOpen}>
          <DialogTrigger asChild>
            <Button>
              <Plus className="w-4 h-4 mr-2" />
              New suite
            </Button>
          </DialogTrigger>
          <DialogContent>
            <DialogHeader>
              <DialogTitle>Create test suite</DialogTitle>
              <DialogDescription>
                Give your suite a name and optional description. You can add test
                cases to it afterwards.
              </DialogDescription>
            </DialogHeader>
            <div className="space-y-4 py-2">
              <div>
                <Label htmlFor="sname">Suite name</Label>
                <Input
                  id="sname"
                  value={suiteName}
                  onChange={(e) => setSuiteName(e.target.value)}
                  placeholder="e.g. Checkout & Payments smoke suite"
                  className="mt-1"
                />
              </div>
              <div>
                <Label htmlFor="sdesc">Description (optional)</Label>
                <Textarea
                  id="sdesc"
                  rows={3}
                  value={suiteDesc}
                  onChange={(e) => setSuiteDesc(e.target.value)}
                  placeholder="What revenue flows does this suite protect?"
                  className="mt-1 text-sm"
                />
              </div>
            </div>
            <DialogFooter>
              <Button
                variant="outline"
                onClick={() => setCreateOpen(false)}
              >
                Cancel
              </Button>
              <Button
                disabled={!suiteName.trim() || createMut.isPending}
                onClick={() =>
                  createMut.mutate({
                    name: suiteName.trim(),
                    description: suiteDesc.trim() || undefined,
                  })
                }
              >
                {createMut.isPending ? (
                  <Loader2 className="w-4 h-4 mr-2 animate-spin" />
                ) : (
                  <Plus className="w-4 h-4 mr-2" />
                )}
                Create
              </Button>
            </DialogFooter>
          </DialogContent>
        </Dialog>
      </div>

      {isLoading ? (
        <div className="space-y-3">
          {Array.from({ length: 3 }).map((_, i) => (
            <Skeleton key={i} className="h-24 w-full rounded-lg" />
          ))}
        </div>
      ) : !suites?.length ? (
        <EmptySuites onCreate={() => setCreateOpen(true)} />
      ) : (
        <div className="space-y-4">
          {suites.map((suite) => (
            <SuiteCard
              key={suite.id}
              suite={suite}
              onRun={() => runMut.mutate(suite.id)}
              onDelete={() => deleteMut.mutate(suite.id)}
              isRunning={runMut.isPending && runMut.variables === suite.id}
            />
          ))}
        </div>
      )}
    </div>
  );
}

function SuiteCard({
  suite,
  onRun,
  onDelete,
  isRunning,
}: {
  suite: TestSuiteOut;
  onRun: () => void;
  onDelete: () => void;
  isRunning: boolean;
}) {
  const router = useRouter();
  const [expanded, setExpanded] = useState(false);

  return (
    <Card>
      <CardHeader className="pb-3">
        <div className="flex items-start justify-between gap-3 flex-wrap">
          <div className="flex-1 min-w-0">
            <CardTitle className="text-base flex items-center gap-2">
              <Layers className="w-4 h-4 text-primary flex-shrink-0" />
              {suite.name}
            </CardTitle>
            {suite.description && (
              <CardDescription className="mt-1 text-sm">
                {suite.description}
              </CardDescription>
            )}
            <div className="text-xs text-muted-foreground mt-2 flex items-center gap-3">
              <span>
                {suite.tests.length} test case
                {suite.tests.length !== 1 ? "s" : ""}
              </span>
              <span>Created {formatDate(suite.created_at)}</span>
            </div>
          </div>

          <div className="flex items-center gap-2">
            <Button
              size="sm"
              disabled={isRunning || suite.tests.length === 0}
              onClick={onRun}
              title={suite.tests.length === 0 ? "Add test cases first" : undefined}
            >
              {isRunning ? (
                <Loader2 className="w-3 h-3 mr-1 animate-spin" />
              ) : (
                <Play className="w-3 h-3 mr-1" />
              )}
              Run all
            </Button>

            <Button
              size="sm"
              variant="outline"
              onClick={() => setExpanded((x) => !x)}
            >
              <ChevronRight
                className={`w-3 h-3 transition-transform ${expanded ? "rotate-90" : ""}`}
              />
              {expanded ? "Hide" : "Cases"}
            </Button>

            <DropdownMenu>
              <DropdownMenuTrigger asChild>
                <Button size="sm" variant="ghost">
                  <MoreHorizontal className="w-4 h-4" />
                </Button>
              </DropdownMenuTrigger>
              <DropdownMenuContent align="end">
                <DropdownMenuItem
                  onClick={() =>
                    router.push(`/new?suite_id=${suite.id}`)
                  }
                >
                  <Plus className="w-4 h-4 mr-2" />
                  Add test case
                </DropdownMenuItem>
                <DropdownMenuItem
                  onClick={onDelete}
                  className="text-destructive focus:text-destructive"
                >
                  <Trash2 className="w-4 h-4 mr-2" />
                  Delete suite
                </DropdownMenuItem>
              </DropdownMenuContent>
            </DropdownMenu>
          </div>
        </div>
      </CardHeader>

      {expanded && (
        <>
          <Separator />
          <CardContent className="pt-4">
            {suite.tests.length === 0 ? (
              <div className="text-sm text-muted-foreground py-4 text-center">
                No test cases yet.{" "}
                <Link
                  href={`/new?suite_id=${suite.id}`}
                  className="underline"
                >
                  Add one from the Run page
                </Link>
                .
              </div>
            ) : (
              <Table>
                <TableHeader>
                  <TableRow>
                    <TableHead>Name</TableHead>
                    <TableHead>Prompt</TableHead>
                    <TableHead>Target URL</TableHead>
                    <TableHead className="text-right">Action</TableHead>
                  </TableRow>
                </TableHeader>
                <TableBody>
                  {suite.tests.map((tc: TestCaseOut) => (
                    <TableRow key={tc.id}>
                      <TableCell className="font-medium text-sm">
                        {tc.name}
                      </TableCell>
                      <TableCell className="text-sm text-muted-foreground max-w-xs truncate">
                        {truncate(tc.prompt, 80)}
                      </TableCell>
                      <TableCell className="text-sm text-muted-foreground max-w-[180px] truncate">
                        {tc.target_url ? (
                          <a
                            href={tc.target_url}
                            target="_blank"
                            rel="noreferrer"
                            className="underline"
                          >
                            {truncate(tc.target_url, 40)}
                          </a>
                        ) : (
                          "—"
                        )}
                      </TableCell>
                      <TableCell className="text-right">
                        <Button
                          size="sm"
                          variant="outline"
                          onClick={async () => {
                            const r = await api.enqueueRun({
                              name: tc.name,
                              prompt: tc.prompt,
                              target_url: tc.target_url,
                              success_criteria: tc.success_criteria,
                              test_case_id: tc.id,
                              use_vision: true,
                              max_steps: 100,
                            });
                            router.push(`/runs/${r.job_id}`);
                          }}
                        >
                          <Play className="w-3 h-3 mr-1" />
                          Run
                        </Button>
                      </TableCell>
                    </TableRow>
                  ))}
                </TableBody>
              </Table>
            )}
          </CardContent>
        </>
      )}
    </Card>
  );
}

function EmptySuites({ onCreate }: { onCreate: () => void }) {
  return (
    <div className="text-center py-12 space-y-3">
      <div className="w-12 h-12 rounded-full bg-muted mx-auto grid place-items-center">
        <Layers className="w-6 h-6 text-muted-foreground" />
      </div>
      <div className="font-medium">No suites yet</div>
      <p className="text-sm text-muted-foreground max-w-md mx-auto">
        Group test cases into suites to run your full checkout, onboarding, or
        pricing flow in one click — or trigger from GitHub Actions.
      </p>
      <Button onClick={onCreate} className="mt-2">
        <Plus className="w-4 h-4 mr-2" />
        Create your first suite
      </Button>
    </div>
  );
}
