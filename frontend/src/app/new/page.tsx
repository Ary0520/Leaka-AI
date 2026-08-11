"use client";

import { type FormEvent, useState, useEffect } from "react";
import { useMutation, useQuery } from "@tanstack/react-query";
import { useRouter, useSearchParams } from "next/navigation";
import { api, type TestCaseOut } from "@/lib/api";
import { Button } from "@/components/ui/button";
import {
  Card,
  CardContent,
  CardDescription,
  CardHeader,
  CardTitle,
} from "@/components/ui/card";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Textarea } from "@/components/ui/textarea";
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select";
import {
  Loader2,
  Save,
  Sparkles,
} from "lucide-react";
import { toast } from "@/components/ui/use-toast";

export default function NewTestPage() {
  const router = useRouter();
  const searchParams = useSearchParams();
  const preselectedSuiteId = searchParams.get("suite_id")
    ? Number(searchParams.get("suite_id"))
    : undefined;

  const [name, setName] = useState("");
  const [prompt, setPrompt] = useState("");
  const [targetUrl, setTargetUrl] = useState("");
  const [success, setSuccess] = useState("");
  const [saveAsCase, setSaveAsCase] = useState(!!preselectedSuiteId);
  const [caseName, setCaseName] = useState("");
  const [existingCaseId, setExistingCaseId] = useState<string>("");
  const [suiteId, setSuiteId] = useState<number | undefined>(preselectedSuiteId);

  // If suite_id lands from URL, auto-enable save-as-case
  useEffect(() => {
    if (preselectedSuiteId) {
      setSaveAsCase(true);
      setSuiteId(preselectedSuiteId);
    }
  }, [preselectedSuiteId]);

  const { data: cases } = useQuery({
    queryKey: ["testcases"],
    queryFn: () => api.listTestCases({ limit: 100 }),
  });

  const { data: suites } = useQuery({
    queryKey: ["suites"],
    queryFn: () => api.listSuites({ limit: 100 }),
  });

  const enqueueMut = useMutation({
    mutationFn: async () => {
      if (!prompt.trim()) throw new Error("Please write a test prompt.");

      // If user picked an existing case, pull name / success criteria from it
      let resolvedCase = cases?.find((c) => String(c.id) === existingCaseId);

      const finalName =
        name.trim() ||
        resolvedCase?.name ||
        `Run ${new Date().toLocaleTimeString()}`;
      const finalPrompt = prompt.trim();
      const finalUrl = targetUrl.trim() || resolvedCase?.target_url || undefined;
      const finalSuccess =
        success.trim() || resolvedCase?.success_criteria || undefined;

      // First save as new case if requested
      let test_case_id: number | undefined = undefined;
      if (saveAsCase && caseName.trim()) {
        const saved = await api.createTestCase({
          name: caseName.trim(),
          prompt: finalPrompt,
          success_criteria: finalSuccess,
          target_url: finalUrl,
          suite_id: suiteId ?? null,
        });
        test_case_id = saved.id;
      } else if (resolvedCase) {
        test_case_id = resolvedCase.id;
      }

      return api.enqueueRun({
        name: finalName,
        prompt: finalPrompt,
        target_url: finalUrl,
        success_criteria: finalSuccess,
        test_case_id,
        use_vision: true,
        max_steps: 50,
      });
    },
    onSuccess: (r) => {
      toast({
        title: "Test enqueued",
        description: `Job ${r.job_id.slice(0, 8)} running in background.`,
      });
      router.push(`/runs/${r.job_id}`);
    },
    onError: (e: Error) => {
      toast({
        title: "Could not enqueue test",
        description: e.message,
        variant: "destructive",
      });
    },
  });

  const onSubmit = (e: FormEvent) => {
    e.preventDefault();
    enqueueMut.mutate();
  };

  const pickExisting = (id: string) => {
    setExistingCaseId(id);
    if (id) {
      const c = cases?.find((x) => String(x.id) === id);
      if (c) {
        setName((n) => n || c.name);
        setPrompt((p) => p || c.prompt);
        setTargetUrl((u) => u || c.target_url || "");
        setSuccess((s) => s || c.success_criteria || "");
      }
    }
  };

  return (
    <div className="max-w-3xl mx-auto space-y-6">
      <div>
        <h1 className="text-2xl font-semibold tracking-tight">
          Run a new QA test
        </h1>
        <p className="text-sm text-muted-foreground mt-1">
          Describe the workflow in natural language. The browser-use agent will
          execute it headlessly.
        </p>
      </div>

      <form onSubmit={onSubmit} className="space-y-6">
        <Card>
          <CardHeader>
            <CardTitle className="text-lg">Test case</CardTitle>
            <CardDescription>
              Optionally reuse an existing saved case, or write one below.
            </CardDescription>
          </CardHeader>
          <CardContent className="space-y-4">
            <div>
              <Label>Existing test case</Label>
              <Select value={existingCaseId} onValueChange={pickExisting}>
                <SelectTrigger className="mt-1">
                  <SelectValue placeholder="None — write a new one" />
                </SelectTrigger>
                <SelectContent>
                  {cases?.length ? (
                    cases.map((c) => (
                      <SelectItem key={c.id} value={String(c.id)}>
                        {c.name}
                      </SelectItem>
                    ))
                  ) : (
                    <div className="p-3 text-xs text-muted-foreground">
                      No saved cases yet.
                    </div>
                  )}
                </SelectContent>
              </Select>
            </div>
          </CardContent>
        </Card>

        <Card>
          <CardHeader>
            <CardTitle className="text-lg">Test details</CardTitle>
            <CardDescription>
              Give the run a name, a target URL, and the natural-language
              prompt to execute.
            </CardDescription>
          </CardHeader>
          <CardContent className="space-y-4">
            <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
              <div>
                <Label htmlFor="name">Run name</Label>
                <Input
                  id="name"
                  value={name}
                  onChange={(e) => setName(e.target.value)}
                  placeholder="e.g. Checkout flow — $50 item + WELCOME promo"
                  className="mt-1"
                />
              </div>
              <div>
                <Label htmlFor="url">Target URL (optional)</Label>
                <Input
                  id="url"
                  value={targetUrl}
                  onChange={(e) => setTargetUrl(e.target.value)}
                  placeholder="https://your-app.example.com"
                  className="mt-1"
                />
              </div>
            </div>

            <div>
              <Label htmlFor="prompt">
                Prompt <span className="text-destructive">*</span>
              </Label>
              <Textarea
                id="prompt"
                required
                rows={7}
                value={prompt}
                onChange={(e) => setPrompt(e.target.value)}
                placeholder={`Add a $50 item to cart, apply promo code WELCOME, and verify the total is $45.`}
                className="mt-1 font-mono text-sm"
              />
              <p className="text-xs text-muted-foreground mt-1">
                Tips: mention URLs explicitly, name elements by label, state
                expected outcomes.
              </p>
            </div>

            <div>
              <Label htmlFor="success">Success criteria (optional)</Label>
              <Textarea
                id="success"
                rows={3}
                value={success}
                onChange={(e) => setSuccess(e.target.value)}
                placeholder="Order total equals $45. Promo discount applied. Order confirmation email listed."
                className="mt-1 text-sm"
              />
            </div>
          </CardContent>
        </Card>

        <Card>
          <CardHeader>
            <CardTitle className="text-lg">Save this as a reusable case?</CardTitle>
            <CardDescription>
              Save prompts you plan to run again (CI, scheduled suites, etc.).
            </CardDescription>
          </CardHeader>
          <CardContent className="space-y-3">
            <label className="flex items-start gap-3 text-sm cursor-pointer select-none">
              <input
                type="checkbox"
                checked={saveAsCase}
                onChange={(e) => setSaveAsCase(e.target.checked)}
                className="mt-1"
              />
              <div>
                <div className="font-medium">Save as test case</div>
                <div className="text-muted-foreground text-xs">
                  Stored in Postgres so you can re-run it from the dashboard or
                  via CI webhook.
                </div>
              </div>
            </label>
            {saveAsCase && (
              <div className="space-y-3">
                <div>
                  <Label htmlFor="caseName">Case name</Label>
                  <Input
                    id="caseName"
                    value={caseName}
                    onChange={(e) => setCaseName(e.target.value)}
                    placeholder="e.g. Checkout: WELCOME promo applies 10% off"
                    className="mt-1"
                  />
                </div>
                <div>
                  <Label htmlFor="suiteSelect">Add to suite (optional)</Label>
                  <Select
                    value={suiteId ? String(suiteId) : "none"}
                    onValueChange={(v) =>
                      setSuiteId(v === "none" ? undefined : Number(v))
                    }
                  >
                    <SelectTrigger id="suiteSelect" className="mt-1">
                      <SelectValue placeholder="No suite" />
                    </SelectTrigger>
                    <SelectContent>
                      <SelectItem value="none">No suite</SelectItem>
                      {suites?.map((s) => (
                        <SelectItem key={s.id} value={String(s.id)}>
                          {s.name}
                        </SelectItem>
                      ))}
                    </SelectContent>
                  </Select>
                </div>
              </div>
            )}
          </CardContent>
        </Card>

        <div className="flex items-center justify-end gap-3">
          <Button
            type="button"
            variant="outline"
            onClick={() => {
              if (saveAsCase && caseName.trim()) {
                api
                  .createTestCase({
                    name: caseName.trim(),
                    prompt: prompt.trim(),
                    success_criteria: success.trim() || undefined,
                    target_url: targetUrl.trim() || undefined,
                    suite_id: suiteId ?? null,
                  })
                  .then((c) => {
                    toast({ title: "Case saved", description: c.name });
                    setExistingCaseId(String(c.id));
                    setSaveAsCase(false);
                  });
              }
            }}
            disabled={!(saveAsCase && caseName.trim())}
          >
            <Save className="w-4 h-4 mr-2" />
            Save only
          </Button>
          <Button type="submit" disabled={enqueueMut.isPending}>
            {enqueueMut.isPending ? (
              <>
                <Loader2 className="w-4 h-4 mr-2 animate-spin" />
                Enqueuing…
              </>
            ) : (
              <>
                <Sparkles className="w-4 h-4 mr-2" />
                Run test
              </>
            )}
          </Button>
        </div>
      </form>
    </div>
  );
}
