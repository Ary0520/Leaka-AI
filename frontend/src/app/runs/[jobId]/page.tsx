"use client";

import { useMutation, useQuery } from "@tanstack/react-query";
import Link from "next/link";
import { api, BACKEND_URL, type RunStatus as RS } from "@/lib/api";
import { StatusBadge } from "@/components/status-badge";
import {
  Alert,
  AlertDescription,
  AlertTitle,
} from "@/components/ui/alert";
import {
  Card,
  CardContent,
  CardDescription,
  CardHeader,
  CardTitle,
} from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Separator } from "@/components/ui/separator";
import {
  Tabs,
  TabsContent,
  TabsList,
  TabsTrigger,
} from "@/components/ui/tabs";
import { Skeleton } from "@/components/ui/skeleton";
import {
  AlertTriangle,
  ArrowLeft,
  CheckCircle2,
  CircleDashed,
  Loader2,
  Mail,
  Ticket,
  XCircle,
  ClipboardCopy,
  X,
  CheckCheck,
  Clock,
  Image as ImageIcon,
  Bell,
} from "lucide-react";
import { formatDate, formatDuration, truncate } from "@/lib/utils";
import { useParams, useRouter } from "next/navigation";
import { useState } from "react";
import { toast } from "@/components/ui/use-toast";

const TERMINAL: RS[] = ["completed", "failed", "cancelled"];

export default function RunDetailPage() {
  const params = useParams<{ jobId: string }>();
  const router = useRouter();
  const jobId = params.jobId!;

  const { data, isLoading, isRefetching } = useQuery({
    queryKey: ["run", jobId],
    queryFn: () => api.getRunStatus(jobId),
    refetchInterval: (ctx) => {
      const s = ctx.state.data?.status;
      if (!s || TERMINAL.includes(s)) return false;
      return 3000; // match architecture spec: poll every 3s
    },
  });

  const linearMut = useMutation({
    mutationFn: () =>
      api.createLinearIssue({
        job_id: jobId,
      }),
    onSuccess: (res) => {
      if (res.success) {
        toast({
          title: "Linear ticket created",
          description: res.identifier
            ? `Created ${res.identifier}${res.title ? `: ${res.title}` : ""}`
            : "Ticket filed successfully.",
        });
      } else {
        toast({
          title: "Linear ticket failed",
          description:
            "Verify LINEAR_API_KEY and LINEAR_TEAM_ID are set on the backend.",
          variant: "destructive",
        });
      }
    },
    onError: (e: Error) =>
      toast({
        title: "Linear ticket failed",
        description: e.message,
        variant: "destructive",
      }),
  });

  const emailMut = useMutation({
    mutationFn: () =>
      api.sendFailureEmail(
        jobId,
        typeof window !== "undefined"
          ? `${window.location.origin}/runs`
          : undefined,
      ),
    onSuccess: () => toast({ title: "Failure alert email sent" }),
    onError: (e: Error) =>
      toast({
        title: "Failed to send email",
        description: e.message,
        variant: "destructive",
      }),
  });

  const slackMut = useMutation({
    mutationFn: () =>
      api.sendSlackAlert(
        jobId,
        typeof window !== "undefined"
          ? `${window.location.origin}/runs`
          : undefined,
      ),
    onSuccess: (r) =>
      toast({
        title: r.sent ? "Slack alert sent" : "Slack alert failed",
        variant: r.sent ? "default" : "destructive",
      }),
    onError: (e: Error) =>
      toast({
        title: "Failed to send Slack alert",
        description: e.message,
        variant: "destructive",
      }),
  });

  const status = data?.status;
  const isRunning = status === "running" || status === "pending";

  return (
    <div className="space-y-6">
      <div className="flex items-center gap-3 flex-wrap">
        <Button asChild variant="outline" size="sm">
          <Link href="/">
            <ArrowLeft className="w-4 h-4 mr-2" />
            Dashboard
          </Link>
        </Button>
        <h1 className="text-xl md:text-2xl font-semibold tracking-tight flex-1 truncate">
          {isLoading ? (
            <Skeleton className="h-6 w-64 inline-block align-middle" />
          ) : (
            data?.name
          )}
        </h1>
        {data && <StatusBadge status={data.status} />}
        {isRefetching && (
          <span className="text-xs text-muted-foreground inline-flex items-center gap-1">
            <Loader2 className="w-3 h-3 animate-spin" /> refreshing
          </span>
        )}
      </div>

      {isLoading && <RunSkeleton />}
      {data && <RunView data={data} onEmail={() => emailMut.mutate()} onLinear={() => linearMut.mutate()} onSlack={() => slackMut.mutate()} />}
    </div>
  );
}

function RunView({
  data,
  onEmail,
  onLinear,
  onSlack,
}: {
  data: Awaited<ReturnType<typeof api.getRunStatus>>;
  onEmail: () => void;
  onLinear: () => void;
  onSlack: () => void;
}) {
  const [copied, setCopied] = useState(false);
  const failure = data.status === "failed";
  const success = data.status === "completed";

  const copyClip = async (text: string) => {
    await navigator.clipboard.writeText(text);
    setCopied(true);
    setTimeout(() => setCopied(false), 1500);
  };

  return (
    <>
      {failure && (
        <Alert variant="destructive">
          <XCircle className="w-4 h-4" />
          <AlertTitle>Test failed</AlertTitle>
          <AlertDescription>
            The browser-use agent could not complete this run successfully.
            Review the steps, DOM state, and failure screenshot below.
          </AlertDescription>
        </Alert>
      )}
      {success && (
        <Alert className="bg-emerald-500/10 border-emerald-500/40 text-emerald-700 dark:text-emerald-300">
          <CheckCircle2 className="w-4 h-4" />
          <AlertTitle>Test passed</AlertTitle>
          <AlertDescription>
            The agent completed {data.total_steps ?? "—"} steps in{" "}
            {formatDuration(data.duration_seconds)}.
          </AlertDescription>
        </Alert>
      )}
      {data.status === "pending" && (
        <Alert>
          <CircleDashed className="w-4 h-4" />
          <AlertTitle>Awaiting worker</AlertTitle>
          <AlertDescription>
            The job has been enqueued in Redis and will be picked up by the
            next free Celery worker.
          </AlertDescription>
        </Alert>
      )}
      {data.status === "running" && (
        <Alert className="bg-blue-500/10 border-blue-500/30 text-blue-700 dark:text-blue-300">
          <Loader2 className="w-4 h-4 animate-spin" />
          <AlertTitle>
            Running · {data.progress?.stage || "executing steps"}
          </AlertTitle>
          <AlertDescription>
            {data.progress?.pct != null &&
              `Progress: ${Math.round(data.progress.pct)}% · `}
            UI refreshes every 3 seconds automatically.
          </AlertDescription>
        </Alert>
      )}

      {/* Summary */}
      <div className="grid grid-cols-1 lg:grid-cols-3 gap-4">
        <SummaryCard icon={<Clock className="w-4 h-4" />} label="Duration">
          {formatDuration(data.duration_seconds)}
        </SummaryCard>
        <SummaryCard icon={<Ticket className="w-4 h-4" />} label="Steps">
          {data.total_steps ?? 0}
        </SummaryCard>
        <SummaryCard
          icon={<AlertTriangle className="w-4 h-4" />}
          label="Visual proof"
        >
          {data.screenshots.length > 0 ? (
            <span className="text-emerald-600 dark:text-emerald-400">
              {data.screenshots.length} screenshots
            </span>
          ) : (
            <span className="text-muted-foreground">none</span>
          )}
        </SummaryCard>
      </div>

      <Tabs defaultValue="overview" className="space-y-4">
        <TabsList>
          <TabsTrigger value="overview">Overview</TabsTrigger>
          <TabsTrigger value="screenshots">
            Screenshots
            {data.screenshots.length > 0 && (
              <span className="ml-2 text-xs text-muted-foreground">
                ({data.screenshots.length})
              </span>
            )}
          </TabsTrigger>
          <TabsTrigger value="integrations">Integrations</TabsTrigger>
        </TabsList>

        <TabsContent value="overview" className="space-y-4">
          <Card>
            <CardHeader>
              <CardTitle className="text-base flex items-center gap-2">
                <ClipboardCopy className="w-4 h-4" />
                Prompt
              </CardTitle>
            </CardHeader>
            <CardContent className="space-y-4">
              <div className="relative">
                <pre className="whitespace-pre-wrap text-sm bg-muted/50 p-4 rounded-md border font-mono">
                  {data.prompt}
                </pre>
                <Button
                  variant="outline"
                  size="sm"
                  className="absolute top-2 right-2"
                  onClick={() => copyClip(data.prompt)}
                >
                  {copied ? (
                    <>
                      <CheckCheck className="w-3 h-3 mr-1" /> Copied
                    </>
                  ) : (
                    <>
                      <ClipboardCopy className="w-3 h-3 mr-1" /> Copy
                    </>
                  )}
                </Button>
              </div>

              <div className="grid grid-cols-1 md:grid-cols-3 text-sm gap-3">
                <Field label="Job ID" value={<code className="text-xs">{data.job_id}</code>} />
                <Field
                  label="Started"
                  value={formatDate(data.started_at ?? data.created_at)}
                />
                <Field
                  label="Completed"
                  value={formatDate(data.completed_at)}
                />
                <Field
                  label="Target URL"
                  value="N/A"
                  override={
                    data.target_url
                      ? (
                        <a
                          className="underline truncate"
                          target="_blank"
                          rel="noreferrer"
                          href={data.target_url}
                        >
                          {truncate(data.target_url, 60)}
                        </a>
                      )
                      : undefined
                  }
                />
              </div>
            </CardContent>
          </Card>

          {data.final_result && (
            <Card>
              <CardHeader>
                <CardTitle className="text-base">Final result</CardTitle>
                <CardDescription>
                  Extracted by the agent when the task completed.
                </CardDescription>
              </CardHeader>
              <CardContent>
                <pre className="whitespace-pre-wrap text-sm bg-muted/50 p-4 rounded-md border font-mono">
                  {data.final_result}
                </pre>
              </CardContent>
            </Card>
          )}

          {data.error_message && (
            <Card className="border-destructive/40">
              <CardHeader>
                <CardTitle className="text-base text-destructive flex items-center gap-2">
                  <XCircle className="w-4 h-4" />
                  Error
                </CardTitle>
              </CardHeader>
              <CardContent>
                <pre className="whitespace-pre-wrap text-sm bg-destructive/5 text-destructive/90 p-4 rounded-md border border-destructive/30 font-mono max-h-80 overflow-auto">
                  {data.error_message}
                </pre>
              </CardContent>
            </Card>
          )}
        </TabsContent>

        <TabsContent value="screenshots">
          <Card>
            <CardHeader>
              <CardTitle className="text-base">Screenshots</CardTitle>
              <CardDescription>
                Captured at each step by the browser-use agent. The last shot
                is flagged on failure.
              </CardDescription>
            </CardHeader>
            <CardContent>
              {!data.screenshots.length ? (
                <div className="text-sm text-muted-foreground py-10 text-center">
                  No screenshots captured yet.
                </div>
              ) : (
                <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
                  {data.screenshots.map((s) => (
                    <div
                      key={s.id}
                      className={
                        "rounded-md border overflow-hidden " +
                        (s.is_failure_point
                          ? "ring-2 ring-destructive/60"
                          : "")
                      }
                    >
                      <div className="flex items-center justify-between px-3 py-2 bg-muted/50 border-b text-xs">
                        <div className="flex items-center gap-2 text-muted-foreground">
                          <ImageIcon className="w-3 h-3" />
                          Step {s.step_index ?? "—"}
                          {s.is_failure_point && (
                            <span className="ml-1 inline-flex items-center gap-1 text-destructive font-medium">
                              <X className="w-3 h-3" /> failure point
                            </span>
                          )}
                        </div>
                        {s.caption && (
                          <span className="truncate max-w-[280px]">
                            {truncate(s.caption, 50)}
                          </span>
                        )}
                      </div>
                      <a
                        href={`${BACKEND_URL}/api/screenshots/${s.id}`}
                        target="_blank"
                        rel="noreferrer"
                        className="block bg-black/5"
                      >
                        {/* eslint-disable-next-line @next/next/no-img-element */}
                        <img
                          src={`${BACKEND_URL}/api/screenshots/${s.id}`}
                          alt={`step ${s.step_index ?? ""}`}
                          className="w-full h-auto max-h-[480px] object-contain bg-muted cursor-zoom-in"
                        />
                      </a>
                    </div>
                  ))}
                </div>
              )}
            </CardContent>
          </Card>
        </TabsContent>

        <TabsContent value="integrations">
          <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
            <Card>
              <CardHeader>
                <CardTitle className="text-base flex items-center gap-2">
                  <Ticket className="w-4 h-4" />
                  Linear ticket
                </CardTitle>
                <CardDescription>
                  File a bug ticket with reproduction steps and a link to this
                  run.
                </CardDescription>
              </CardHeader>
              <CardContent>
                <Button variant="outline" onClick={onLinear}>
                  <Ticket className="w-4 h-4 mr-2" />
                  Create Linear ticket
                </Button>
              </CardContent>
            </Card>

            <Card>
              <CardHeader>
                <CardTitle className="text-base flex items-center gap-2">
                  <Mail className="w-4 h-4" />
                  Email alert
                </CardTitle>
                <CardDescription>
                  Send a failure alert to the configured address. Includes the
                  failure-point screenshot as attachment.
                </CardDescription>
              </CardHeader>
              <CardContent>
                <Button variant="outline" onClick={onEmail}>
                  <Mail className="w-4 h-4 mr-2" />
                  Send failure alert
                </Button>
              </CardContent>
            </Card>

            <Card>
              <CardHeader>
                <CardTitle className="text-base flex items-center gap-2">
                  <Bell className="w-4 h-4" />
                  Slack alert
                </CardTitle>
                <CardDescription>
                  Post a failure block message to the configured Slack incoming
                  webhook with step count, duration, and error details.
                </CardDescription>
              </CardHeader>
              <CardContent>
                <Button variant="outline" onClick={onSlack}>
                  <Bell className="w-4 h-4 mr-2" />
                  Send Slack alert
                </Button>
              </CardContent>
            </Card>
          </div>
        </TabsContent>
      </Tabs>
    </>
  );
}

function SummaryCard({
  icon,
  label,
  children,
}: {
  icon: React.ReactNode;
  label: string;
  children: React.ReactNode;
}) {
  return (
    <Card>
      <CardContent className="pt-6">
        <div className="flex items-center gap-2 text-xs text-muted-foreground uppercase tracking-wide">
          <span className="text-primary">{icon}</span>
          {label}
        </div>
        <div className="mt-1 text-2xl font-semibold">{children}</div>
      </CardContent>
    </Card>
  );
}

function Field({
  label,
  value,
  override,
}: {
  label: string;
  value?: React.ReactNode;
  override?: React.ReactNode;
}) {
  return (
    <div>
      <div className="text-xs text-muted-foreground uppercase tracking-wide mb-1">
        {label}
      </div>
      <div>{override ?? value}</div>
    </div>
  );
}

function RunSkeleton() {
  return (
    <div className="space-y-4">
      <Skeleton className="h-12 w-full" />
      <div className="grid grid-cols-1 lg:grid-cols-3 gap-4">
        <Skeleton className="h-20" />
        <Skeleton className="h-20" />
        <Skeleton className="h-20" />
      </div>
      <Skeleton className="h-72 w-full" />
    </div>
  );
}
