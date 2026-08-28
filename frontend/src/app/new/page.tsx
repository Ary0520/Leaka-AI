"use client";

import { type FormEvent, useState, useEffect, Suspense } from "react";
import { useMutation, useQuery } from "@tanstack/react-query";
import { useRouter, useSearchParams } from "next/navigation";
import { api, type TestCaseOut, type Assertion, type AssertionType } from "@/lib/api";
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
  Link as LinkIcon,
  Lightbulb,
  Play,
  Check,
  ShieldCheck,
  Plus,
  Trash2,
} from "lucide-react";
import { toast } from "@/components/ui/use-toast";

const ASSERTION_TYPES: { value: AssertionType; label: string; placeholder: string }[] = [
  { value: "page_contains_text", label: "Page contains text", placeholder: "e.g. Thank you for your order" },
  { value: "page_not_contains_text", label: "Page does NOT contain text", placeholder: "e.g. Error" },
  { value: "url_contains", label: "Final URL contains", placeholder: "e.g. /success" },
  { value: "url_equals", label: "Final URL equals", placeholder: "e.g. https://shop.com/thank-you" },
  { value: "page_contains_regex", label: "Page matches regex", placeholder: "e.g. Order #\\d+" },
];

function NewTestContent() {
  const router = useRouter();
  const searchParams = useSearchParams();
  const preselectedSuiteId = searchParams.get("suite_id")
    ? Number(searchParams.get("suite_id"))
    : undefined;

  // Prefill from query params (e.g. "Generate test" from an application map node)
  const [name, setName] = useState(searchParams.get("name") ?? "");
  const [prompt, setPrompt] = useState(searchParams.get("prompt") ?? "");
  const [targetUrl, setTargetUrl] = useState(searchParams.get("target_url") ?? "");
  // Coverage linkage: when this page was opened from a graph node's "Generate
  // test", these carry the node identity so the saved test links back to it.
  const linkAppId = searchParams.get("app_id") ? Number(searchParams.get("app_id")) : undefined;
  const linkNodeId = searchParams.get("node_id") ? Number(searchParams.get("node_id")) : undefined;
  const [success, setSuccess] = useState("");
  const [saveAsCase, setSaveAsCase] = useState(!!preselectedSuiteId);
  const [caseName, setCaseName] = useState("");
  const [existingCaseId, setExistingCaseId] = useState<string>("");
  const [suiteId, setSuiteId] = useState<number | undefined>(preselectedSuiteId);
  const [assertions, setAssertions] = useState<Assertion[]>([]);

  const addAssertion = () =>
    setAssertions((prev) => [...prev, { type: "page_contains_text", value: "", case_sensitive: false }]);
  const updateAssertion = (i: number, patch: Partial<Assertion>) =>
    setAssertions((prev) => prev.map((a, idx) => (idx === i ? { ...a, ...patch } : a)));
  const removeAssertion = (i: number) =>
    setAssertions((prev) => prev.filter((_, idx) => idx !== i));

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

      // Only send assertions that actually have a value
      const cleanAssertions = assertions
        .map((a) => ({ ...a, value: a.value.trim() }))
        .filter((a) => a.value.length > 0);
      const assertionsPayload = cleanAssertions.length ? cleanAssertions : undefined;

      // First save as new case if requested
      let test_case_id: number | undefined = undefined;
      if (saveAsCase && caseName.trim()) {
        const saved = await api.createTestCase({
          name: caseName.trim(),
          prompt: finalPrompt,
          success_criteria: finalSuccess,
          target_url: finalUrl,
          suite_id: suiteId ?? null,
          assertions: assertionsPayload,
          application_id: linkAppId ?? null,
          node_id: linkNodeId ?? null,
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
        assertions: assertionsPayload,
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
        if (c.assertions && c.assertions.length) {
          setAssertions((prev) => (prev.length ? prev : c.assertions!));
        }
      }
    }
  };

  return (
    <div className="max-w-[1200px] mx-auto space-y-6">
      <div>
        <h1 className="text-2xl font-semibold tracking-tight text-foreground">
          Run a new QA test
        </h1>
        <p className="text-sm text-muted-foreground mt-1">
          Describe the workflow in plain English — the agent handles the rest.
        </p>
      </div>

      {/* Decorative Banner */}
      <div className="rounded-lg bg-[#161922] p-4 flex flex-col gap-3 relative overflow-hidden border border-indigo-500/10">
        <div className="flex items-center gap-3">
          <div className="relative flex h-2 w-2">
            <span className="animate-ping absolute inline-flex h-full w-full rounded-full bg-indigo-400 opacity-75"></span>
            <span className="relative inline-flex rounded-full h-2 w-2 bg-indigo-400 shadow-[0_0_8px_rgba(129,140,248,0.9)]"></span>
          </div>
          <span className="text-sm text-indigo-200 tracking-wide font-mono">
            The Agent is running<span className="animate-pulse">...</span>
          </span>
        </div>
        <div className="h-[1px] w-64 bg-indigo-900/30 relative overflow-hidden">
          <div className="absolute inset-0 w-full bg-gradient-to-r from-transparent via-indigo-400 to-transparent animate-slide" />
        </div>
      </div>

      <form onSubmit={onSubmit} className="grid grid-cols-1 lg:grid-cols-3 gap-6">
        
        {/* Left Column */}
        <div className="lg:col-span-2 space-y-6">
          
          <Card className="border-0 bg-[#161922]">
            <CardContent className="p-6">
              <Label className="text-[10px] tracking-widest font-semibold uppercase text-muted-foreground mb-4 block">
                Reuse an existing test
              </Label>
              <Select value={existingCaseId} onValueChange={pickExisting}>
                <SelectTrigger className="bg-[#0B0E14] border-transparent font-mono text-sm h-11 text-muted-foreground">
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
            </CardContent>
          </Card>

          <Card className="border-0 bg-[#161922]">
            <CardContent className="p-6 space-y-8">
              <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
                <div>
                  <Label htmlFor="name" className="text-[10px] tracking-widest font-semibold uppercase text-muted-foreground mb-3 block">
                    Run name
                  </Label>
                  <Input
                    id="name"
                    value={name}
                    onChange={(e) => setName(e.target.value)}
                    placeholder="e.g. Checkout flow — $50 item +"
                    className="bg-[#0B0E14] border-transparent font-mono text-sm h-11 text-muted-foreground"
                  />
                </div>
                <div>
                  <Label htmlFor="url" className="text-[10px] tracking-widest font-semibold uppercase text-muted-foreground mb-3 block">
                    Target URL
                  </Label>
                  <div className="relative">
                    <span className="absolute left-3 top-3.5 text-muted-foreground/50">
                      <LinkIcon className="w-4 h-4" />
                    </span>
                    <Input
                      id="url"
                      value={targetUrl}
                      onChange={(e) => setTargetUrl(e.target.value)}
                      placeholder="https://your-app.example.com"
                      className="bg-[#0B0E14] border-transparent font-mono text-sm h-11 pl-9 text-muted-foreground"
                    />
                  </div>
                </div>
              </div>

              <div>
                <div className="flex justify-between items-center mb-3">
                  <Label htmlFor="prompt" className="text-[10px] tracking-widest font-semibold uppercase text-muted-foreground block">
                    Workflow description
                  </Label>
                  <span className="text-[10px] font-semibold uppercase tracking-widest text-muted-foreground flex items-center gap-1.5 cursor-pointer hover:text-white transition-colors">
                    <Sparkles className="w-3.5 h-3.5" /> Use AI to draft
                  </span>
                </div>
                <Textarea
                  id="prompt"
                  required
                  rows={6}
                  value={prompt}
                  onChange={(e) => setPrompt(e.target.value)}
                  placeholder="Add a $50 item to cart, apply promo code WELCOME, and verify the total is $45."
                  className="bg-[#0B0E14] border-transparent font-mono text-sm min-h-[140px] p-4 resize-none text-muted-foreground focus-visible:ring-1 focus-visible:ring-indigo-500/50"
                />
                <div className="flex items-start gap-2 mt-4">
                  <Lightbulb className="w-3.5 h-3.5 text-orange-400 mt-0.5 shrink-0" />
                  <p className="text-xs text-muted-foreground font-medium leading-relaxed">
                    Tip: mention URLs explicitly, name elements by their label, and state the expected outcome clearly.
                  </p>
                </div>
              </div>

              <div>
                <Label htmlFor="success" className="text-[10px] tracking-widest font-semibold uppercase text-muted-foreground mb-3 block">
                  Success criteria (optional)
                </Label>
                <Textarea
                  id="success"
                  rows={3}
                  value={success}
                  onChange={(e) => setSuccess(e.target.value)}
                  placeholder="Order total equals $45. Promo discount applied. Confirmation email sent."
                  className="bg-[#0B0E14] border-transparent font-mono text-sm p-4 resize-none text-muted-foreground"
                />
              </div>

              {/* ── Deterministic assertions ── */}
              <div className="pt-2 border-t border-white/5">
                <div className="flex items-center justify-between mb-3">
                  <Label className="text-[10px] tracking-widest font-semibold uppercase text-muted-foreground flex items-center gap-1.5">
                    <ShieldCheck className="w-3.5 h-3.5 text-emerald-400" />
                    Assertions (optional)
                  </Label>
                  <Button type="button" size="sm" variant="outline" onClick={addAssertion}
                    className="h-7 text-xs">
                    <Plus className="w-3 h-3 mr-1" /> Add
                  </Button>
                </div>
                <p className="text-xs text-muted-foreground mb-3 leading-relaxed">
                  Machine-checked against the real final page — independent of what the
                  AI reports. A test passes only if the AI succeeds <em>and</em> every
                  assertion holds. Text checks match visible page text (ignoring HTML/scripts).
                </p>

                {assertions.length === 0 ? (
                  <div className="text-xs text-muted-foreground/60 italic py-2">
                    No assertions. The result will rely on the AI agent&apos;s judgement alone.
                  </div>
                ) : (
                  <div className="space-y-2">
                    {assertions.map((a, i) => {
                      const meta = ASSERTION_TYPES.find((t) => t.value === a.type);
                      return (
                        <div key={i} className="flex items-start gap-2 rounded-md bg-[#0B0E14] p-2">
                          <div className="flex-1 space-y-2">
                            <Select
                              value={a.type}
                              onValueChange={(v) => updateAssertion(i, { type: v as AssertionType })}
                            >
                              <SelectTrigger className="h-8 text-xs bg-[#161922] border-transparent">
                                <SelectValue />
                              </SelectTrigger>
                              <SelectContent>
                                {ASSERTION_TYPES.map((t) => (
                                  <SelectItem key={t.value} value={t.value} className="text-xs">
                                    {t.label}
                                  </SelectItem>
                                ))}
                              </SelectContent>
                            </Select>
                            <Input
                              value={a.value}
                              onChange={(e) => updateAssertion(i, { value: e.target.value })}
                              placeholder={meta?.placeholder}
                              className="h-8 text-xs bg-[#161922] border-transparent font-mono"
                            />
                            <label className="flex items-center gap-1.5 text-[11px] text-muted-foreground cursor-pointer">
                              <input
                                type="checkbox"
                                checked={a.case_sensitive ?? false}
                                onChange={(e) => updateAssertion(i, { case_sensitive: e.target.checked })}
                                className="w-3 h-3"
                              />
                              Case sensitive
                            </label>
                          </div>
                          <Button
                            type="button"
                            size="sm"
                            variant="ghost"
                            onClick={() => removeAssertion(i)}
                            className="h-7 w-7 p-0 text-muted-foreground hover:text-destructive shrink-0"
                          >
                            <Trash2 className="w-3.5 h-3.5" />
                          </Button>
                        </div>
                      );
                    })}
                  </div>
                )}
              </div>
            </CardContent>
          </Card>
        </div>

        {/* Right Column */}
        <div className="lg:col-span-1 space-y-6">
          <Card className="border-0 bg-[#161922]">
            <CardContent className="p-6">
              <label className="flex items-start gap-3 cursor-pointer group select-none">
                <div className="mt-0.5 relative">
                  <input
                    type="checkbox"
                    checked={saveAsCase}
                    onChange={(e) => setSaveAsCase(e.target.checked)}
                    className="peer sr-only"
                  />
                  <div className="w-4 h-4 rounded-sm bg-[#0B0E14] border border-muted-foreground/30 peer-checked:bg-indigo-500 peer-checked:border-indigo-500 flex items-center justify-center transition-colors group-hover:border-muted-foreground/60">
                    {saveAsCase && <Check className="w-3 h-3 text-white" />}
                  </div>
                </div>
                <div>
                  <div className="text-sm font-medium text-foreground">Save as reusable case</div>
                  <div className="text-xs text-muted-foreground mt-1.5 leading-relaxed">
                    Stored so you can re-run it from the dashboard, a suite, or your CI pipeline.
                  </div>
                </div>
              </label>

              {saveAsCase && (
                <div className="space-y-5 mt-6 pt-6 border-t border-muted-foreground/10">
                  <div>
                    <Label htmlFor="caseName" className="text-[10px] tracking-widest font-semibold uppercase text-muted-foreground mb-3 block">
                      Case name
                    </Label>
                    <Input
                      id="caseName"
                      value={caseName}
                      onChange={(e) => setCaseName(e.target.value)}
                      placeholder="e.g. Checkout: WELCOME promo applies 10% off"
                      className="bg-[#0B0E14] border-transparent font-mono text-sm h-11 text-muted-foreground"
                    />
                  </div>
                  <div>
                    <Label htmlFor="suiteSelect" className="text-[10px] tracking-widest font-semibold uppercase text-muted-foreground mb-3 block">
                      Add to suite (optional)
                    </Label>
                    <Select
                      value={suiteId ? String(suiteId) : "none"}
                      onValueChange={(v) =>
                        setSuiteId(v === "none" ? undefined : Number(v))
                      }
                    >
                      <SelectTrigger id="suiteSelect" className="bg-[#0B0E14] border-transparent font-mono text-sm h-11 text-muted-foreground">
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

          <div className="flex items-center justify-end gap-6 mt-4">
            <Button
              type="button"
              variant="ghost"
              className="text-muted-foreground hover:text-white hover:bg-transparent font-medium px-0"
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
              Save only
            </Button>
            
            <Button 
              type="submit" 
              disabled={enqueueMut.isPending}
              className="bg-indigo-300 hover:bg-indigo-400 text-indigo-950 font-semibold rounded-md px-6 h-10 transition-colors"
            >
              {enqueueMut.isPending ? (
                <>
                  <Loader2 className="w-4 h-4 mr-2 animate-spin text-indigo-950" />
                  Running…
                </>
              ) : (
                <>
                  <Play className="w-4 h-4 mr-2 fill-current" />
                  Run test
                </>
              )}
            </Button>
          </div>
          
          {/* Subtle decorative target/X at bottom right like in the screenshot */}
          <div className="mt-12 flex justify-end pr-4 opacity-5 pointer-events-none">
            <div className="w-32 h-32 rounded-full border-4 border-dashed border-white flex items-center justify-center">
              <div className="w-20 h-20 rotate-45 border-4 border-white" />
            </div>
          </div>
          
        </div>
      </form>
    </div>
  );
}

export default function NewTestPage() {
  return (
    <Suspense fallback={<div className="p-8 text-center text-muted-foreground">Loading test configuration...</div>}>
      <NewTestContent />
    </Suspense>
  );
}
