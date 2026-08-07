"use client";

import { useState } from "react";
import { useMutation, useQuery } from "@tanstack/react-query";
import { api } from "@/lib/api";
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
import { Separator } from "@/components/ui/separator";
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs";
import { Badge } from "@/components/ui/badge";
import {
  CheckCheck,
  ClipboardCopy,
  GitBranch,
  Loader2,
  Play,
  Shield,
  Webhook,
  Zap,
} from "lucide-react";
import { toast } from "@/components/ui/use-toast";
import { BACKEND_URL } from "@/lib/api";

const CI_TOKEN =
  typeof process !== "undefined"
    ? process.env.CI_WEBHOOK_TOKEN || "revguard-ci-token-change-me"
    : "revguard-ci-token-change-me";

const WEBHOOK_URL = `${BACKEND_URL}/api/webhooks/ci`;

function CopyButton({ text, label = "Copy" }: { text: string; label?: string }) {
  const [copied, setCopied] = useState(false);
  return (
    <Button
      size="sm"
      variant="outline"
      className="shrink-0"
      onClick={async () => {
        await navigator.clipboard.writeText(text);
        setCopied(true);
        setTimeout(() => setCopied(false), 1500);
      }}
    >
      {copied ? (
        <>
          <CheckCheck className="w-3 h-3 mr-1" /> Copied
        </>
      ) : (
        <>
          <ClipboardCopy className="w-3 h-3 mr-1" /> {label}
        </>
      )}
    </Button>
  );
}

function CodeBlock({ code, language = "yaml" }: { code: string; language?: string }) {
  return (
    <div className="relative">
      <pre className="bg-zinc-950 text-zinc-100 text-xs p-4 rounded-lg overflow-x-auto leading-relaxed">
        <code>{code}</code>
      </pre>
      <div className="absolute top-2 right-2">
        <CopyButton text={code} label="Copy" />
      </div>
    </div>
  );
}

export default function CIPage() {
  const [testSuiteId, setTestSuiteId] = useState<string>("");
  const [testCaseIds, setTestCaseIds] = useState<string>("");

  const { data: suites } = useQuery({
    queryKey: ["suites"],
    queryFn: () => api.listSuites({ limit: 100 }),
  });

  const triggerMut = useMutation({
    mutationFn: () => {
      const suite_id = testSuiteId ? Number(testSuiteId) : undefined;
      const case_ids = testCaseIds
        .split(",")
        .map((s) => s.trim())
        .filter(Boolean)
        .map(Number)
        .filter((n) => !isNaN(n));
      return api.triggerCI({
        suite_id,
        test_case_ids: case_ids.length ? case_ids : undefined,
        branch: "manual-test",
        triggered_by: "leaka-dashboard",
      });
    },
    onSuccess: (r) => {
      toast({
        title: `CI triggered — ${r.job_ids.length} run(s) enqueued`,
        description: r.message,
      });
    },
    onError: (e: Error) =>
      toast({
        title: "CI trigger failed",
        description: e.message,
        variant: "destructive",
      }),
  });

  const githubActionsYaml = `name: Leaka AI QA Gate

on:
  push:
    branches: [main, staging]
  pull_request:
    branches: [main]

jobs:
  qa:
    name: Revenue Flow QA
    runs-on: ubuntu-latest
    steps:
      - name: Trigger Leaka AI QA suite
        id: qa
        run: |
          RESPONSE=$(curl -s -w "\\n%{http_code}" \\
            -X POST ${WEBHOOK_URL} \\
            -H "Content-Type: application/json" \\
            -H "X-CI-Token: \${{ secrets.LEAKA_CI_TOKEN }}" \\
            -d '{
              "suite_id": \${{ vars.LEAKA_SUITE_ID }},
              "branch": "\${{ github.ref_name }}",
              "commit_sha": "\${{ github.sha }}",
              "triggered_by": "github-actions"
            }')
          HTTP_CODE=\$(echo "$RESPONSE" | tail -n1)
          BODY=\$(echo "$RESPONSE" | head -n-1)
          echo "Response: $BODY"
          if [ "$HTTP_CODE" != "200" ]; then
            echo "QA trigger failed with HTTP $HTTP_CODE"
            exit 1
          fi
          echo "job_ids=\$(echo $BODY | jq -r '.job_ids | join(\",\")')" >> $GITHUB_OUTPUT

      - name: QA jobs enqueued
        run: |
          echo "✅ QA runs queued: \${{ steps.qa.outputs.job_ids }}"
          echo "Monitor at: ${BACKEND_URL}/../dashboard"`;

  const curlExample = `curl -X POST ${WEBHOOK_URL} \\
  -H "Content-Type: application/json" \\
  -H "X-CI-Token: YOUR_TOKEN_HERE" \\
  -d '{
    "suite_id": 1,
    "branch": "main",
    "commit_sha": "abc123",
    "triggered_by": "github-actions"
  }'`;

  const responseExample = `{
  "message": "Enqueued 3 test run(s) from CI.",
  "job_ids": [
    "a1b2c3d4e5f6...",
    "b2c3d4e5f6a7...",
    "c3d4e5f6a7b8..."
  ]
}`;

  return (
    <div className="space-y-6 max-w-4xl">
      <div>
        <h1 className="text-2xl font-semibold tracking-tight flex items-center gap-2">
          <Webhook className="w-6 h-6 text-primary" />
          CI / CD Integration
        </h1>
        <p className="text-sm text-muted-foreground mt-1">
          Trigger Leaka AI QA runs from GitHub Actions, GitLab CI, or any
          pipeline — block bad deploys before they hit production.
        </p>
      </div>

      {/* Key credentials */}
      <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
        <Card>
          <CardHeader className="pb-3">
            <CardTitle className="text-sm flex items-center gap-2">
              <Zap className="w-4 h-4 text-primary" />
              Webhook endpoint
            </CardTitle>
          </CardHeader>
          <CardContent>
            <div className="flex items-center gap-2">
              <code className="text-xs bg-muted px-2 py-1.5 rounded flex-1 truncate font-mono">
                POST {WEBHOOK_URL}
              </code>
              <CopyButton text={WEBHOOK_URL} />
            </div>
          </CardContent>
        </Card>

        <Card>
          <CardHeader className="pb-3">
            <CardTitle className="text-sm flex items-center gap-2">
              <Shield className="w-4 h-4 text-primary" />
              Auth token
            </CardTitle>
          </CardHeader>
          <CardContent>
            <div className="flex items-center gap-2">
              <code className="text-xs bg-muted px-2 py-1.5 rounded flex-1 truncate font-mono">
                X-CI-Token: {CI_TOKEN}
              </code>
              <CopyButton text={CI_TOKEN} />
            </div>
            <p className="text-xs text-muted-foreground mt-2">
              Set <code>CI_WEBHOOK_TOKEN</code> in backend <code>.env</code> to
              rotate this secret.
            </p>
          </CardContent>
        </Card>
      </div>

      <Tabs defaultValue="github">
        <TabsList>
          <TabsTrigger value="github">
            <GitBranch className="w-3 h-3 mr-1.5" />
            GitHub Actions
          </TabsTrigger>
          <TabsTrigger value="curl">cURL</TabsTrigger>
          <TabsTrigger value="test">Test now</TabsTrigger>
        </TabsList>

        {/* GitHub Actions */}
        <TabsContent value="github" className="space-y-4 mt-4">
          <Card>
            <CardHeader>
              <CardTitle className="text-base">GitHub Actions workflow</CardTitle>
              <CardDescription>
                Add this step to your workflow. On every push to{" "}
                <code>main</code> or{" "}
                <code>staging</code> it triggers the full QA suite before the
                deploy proceeds.
              </CardDescription>
            </CardHeader>
            <CardContent className="space-y-4">
              <CodeBlock code={githubActionsYaml} language="yaml" />

              <div className="space-y-2">
                <p className="text-sm font-medium">Required GitHub secrets</p>
                <div className="rounded-lg border divide-y text-sm">
                  <div className="flex items-center gap-4 px-4 py-2.5">
                    <code className="text-xs font-mono w-48 shrink-0 text-primary">
                      LEAKA_CI_TOKEN
                    </code>
                    <span className="text-muted-foreground">
                      The <code>CI_WEBHOOK_TOKEN</code> value from your backend{" "}
                      <code>.env</code>
                    </span>
                  </div>
                </div>
                <p className="text-sm font-medium mt-3">Required GitHub variables</p>
                <div className="rounded-lg border divide-y text-sm">
                  <div className="flex items-center gap-4 px-4 py-2.5">
                    <code className="text-xs font-mono w-48 shrink-0 text-primary">
                      LEAKA_SUITE_ID
                    </code>
                    <span className="text-muted-foreground">
                      The numeric ID of the test suite to run (find it on the
                      Suites page)
                    </span>
                  </div>
                </div>
              </div>

              {suites && suites.length > 0 && (
                <div className="rounded-lg bg-muted/50 border p-3 space-y-2">
                  <p className="text-xs font-medium text-muted-foreground uppercase tracking-wide">
                    Your suites
                  </p>
                  {suites.map((s) => (
                    <div
                      key={s.id}
                      className="flex items-center justify-between text-sm"
                    >
                      <span>{s.name}</span>
                      <div className="flex items-center gap-2">
                        <Badge variant="outline" className="font-mono text-xs">
                          ID: {s.id}
                        </Badge>
                        <CopyButton text={String(s.id)} label="Copy ID" />
                      </div>
                    </div>
                  ))}
                </div>
              )}
            </CardContent>
          </Card>
        </TabsContent>

        {/* cURL */}
        <TabsContent value="curl" className="space-y-4 mt-4">
          <Card>
            <CardHeader>
              <CardTitle className="text-base">Direct cURL call</CardTitle>
              <CardDescription>
                Works from any shell, CI system, or serverless function.
              </CardDescription>
            </CardHeader>
            <CardContent className="space-y-4">
              <CodeBlock code={curlExample} language="bash" />
              <Separator />
              <div>
                <p className="text-sm font-medium mb-2">Example response</p>
                <CodeBlock code={responseExample} language="json" />
              </div>

              <div className="space-y-2 text-sm">
                <p className="font-medium">Request body fields</p>
                <div className="rounded-lg border divide-y">
                  {[
                    {
                      field: "suite_id",
                      type: "int?",
                      desc: "Run all cases in this suite",
                    },
                    {
                      field: "test_case_ids",
                      type: "int[]?",
                      desc: "Run specific case IDs (union with suite_id)",
                    },
                    {
                      field: "branch",
                      type: "string?",
                      desc: "Git branch name — stored for traceability",
                    },
                    {
                      field: "commit_sha",
                      type: "string?",
                      desc: "Commit SHA — stored for traceability",
                    },
                    {
                      field: "triggered_by",
                      type: "string?",
                      desc: 'Label e.g. "github-actions", "gitlab-ci"',
                    },
                  ].map((r) => (
                    <div
                      key={r.field}
                      className="grid grid-cols-[120px_60px_1fr] gap-3 px-4 py-2.5 text-sm"
                    >
                      <code className="font-mono text-xs text-primary">
                        {r.field}
                      </code>
                      <span className="text-muted-foreground text-xs">
                        {r.type}
                      </span>
                      <span className="text-muted-foreground text-xs">
                        {r.desc}
                      </span>
                    </div>
                  ))}
                </div>
              </div>
            </CardContent>
          </Card>
        </TabsContent>

        {/* Live test */}
        <TabsContent value="test" className="space-y-4 mt-4">
          <Card>
            <CardHeader>
              <CardTitle className="text-base">Trigger a CI run now</CardTitle>
              <CardDescription>
                Simulate a CI trigger directly from the dashboard. Same code
                path as GitHub Actions — real runs, real results.
              </CardDescription>
            </CardHeader>
            <CardContent className="space-y-4">
              <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
                <div>
                  <Label htmlFor="suiteId">Suite ID</Label>
                  <Input
                    id="suiteId"
                    value={testSuiteId}
                    onChange={(e) => setTestSuiteId(e.target.value)}
                    placeholder="e.g. 1"
                    className="mt-1 font-mono"
                  />
                  {suites && suites.length > 0 && (
                    <p className="text-xs text-muted-foreground mt-1">
                      Your suites:{" "}
                      {suites
                        .map((s) => `${s.name} (${s.id})`)
                        .join(", ")}
                    </p>
                  )}
                </div>
                <div>
                  <Label htmlFor="caseIds">
                    Test case IDs{" "}
                    <span className="text-muted-foreground font-normal">
                      (comma-separated, optional)
                    </span>
                  </Label>
                  <Input
                    id="caseIds"
                    value={testCaseIds}
                    onChange={(e) => setTestCaseIds(e.target.value)}
                    placeholder="e.g. 1, 2, 3"
                    className="mt-1 font-mono"
                  />
                </div>
              </div>

              <Button
                disabled={
                  triggerMut.isPending ||
                  (!testSuiteId.trim() && !testCaseIds.trim())
                }
                onClick={() => triggerMut.mutate()}
              >
                {triggerMut.isPending ? (
                  <Loader2 className="w-4 h-4 mr-2 animate-spin" />
                ) : (
                  <Play className="w-4 h-4 mr-2" />
                )}
                Trigger CI run
              </Button>

              {triggerMut.isSuccess && (
                <div className="rounded-lg bg-emerald-500/10 border border-emerald-500/30 p-3 text-sm text-emerald-700 dark:text-emerald-300">
                  <p className="font-medium">
                    ✅ {triggerMut.data.job_ids.length} run(s) enqueued
                  </p>
                  <p className="text-xs mt-1 font-mono">
                    {triggerMut.data.job_ids.map((id) => id.slice(0, 12)).join(", ")}…
                  </p>
                </div>
              )}
            </CardContent>
          </Card>
        </TabsContent>
      </Tabs>
    </div>
  );
}
