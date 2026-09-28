"use client";

import { useState } from "react";
import { useQuery } from "@tanstack/react-query";
import { api } from "@/lib/api";
import { Plug, Copy, Terminal, CheckCircle2, ChevronRight, Zap, Shield, Blocks } from "lucide-react";
import { Button } from "@/components/ui/button";
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select";
import { toast } from "@/components/ui/use-toast";
import Link from "next/link";

export default function McpIntegrationHub() {
  const { data: apiKeys, isLoading: apiKeysLoading } = useQuery({
    queryKey: ["api-keys"],
    queryFn: () => api.listApiKeys(),
  });

  const [selectedKey, setSelectedKey] = useState<string>("YOUR_API_KEY");
  const [copiedSection, setCopiedSection] = useState<string | null>(null);

  const developerKeys = apiKeys?.filter((k: any) => k.scope === "developer") || [];

  const handleCopy = (text: string, section: string) => {
    navigator.clipboard.writeText(text);
    setCopiedSection(section);
    toast({ title: "Copied to clipboard" });
    setTimeout(() => setCopiedSection(null), 2000);
  };

  const configSnippet = `{
  "mcpServers": {
    "leaka-ai": {
      "type": "sse",
      "url": "https://api.leaka.live/api/mcp/sse",
      "env": {
        "LEAKA_API_KEY": "${selectedKey}"
      }
    }
  }
}`;

  return (
    <div className="max-w-4xl space-y-10 pb-12 animate-in fade-in duration-500">
      {/* Header */}
      <div className="flex flex-col gap-2">
        <div className="inline-flex items-center gap-2 px-3 py-1 rounded-full bg-indigo-500/10 text-indigo-400 w-fit text-xs font-semibold tracking-wide uppercase border border-indigo-500/20 mb-2">
          <Zap className="w-3.5 h-3.5" /> Next-Gen DevEx
        </div>
        <h1 className="text-3xl font-semibold tracking-tight text-foreground flex items-center gap-3">
          IDE Integrations <span className="text-muted-foreground font-normal">(MCP)</span>
        </h1>
        <p className="text-base text-muted-foreground mt-1 max-w-2xl leading-relaxed">
          Supercharge your local AI editors (Cursor, Windsurf, Claude Desktop) to orchestrate Leaka AI tests, quarantine flaky builds, and trace failures autonomously—without ever leaving your terminal.
        </p>
      </div>

      <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
        {/* Left Column: Setup Instructions */}
        <div className="lg:col-span-2 space-y-6">
          <div className="bg-[#161922] border border-muted/20 rounded-xl overflow-hidden relative shadow-lg">
            <div className="absolute top-0 left-0 w-full h-1 bg-gradient-to-r from-indigo-500 to-purple-500" />
            <div className="p-6">
              <h3 className="text-lg font-medium flex items-center gap-2 mb-6">
                <Terminal className="w-5 h-5 text-indigo-400" /> Connecting your IDE
              </h3>
              
              <div className="space-y-8">
                {/* Step 1 */}
                <div className="relative pl-8">
                  <div className="absolute left-0 top-0.5 flex h-6 w-6 items-center justify-center rounded-full bg-indigo-500/20 text-xs font-bold text-indigo-300 ring-4 ring-[#161922]">1</div>
                  <h4 className="text-sm font-semibold text-foreground">Select your Developer Key</h4>
                  <p className="text-xs text-muted-foreground mt-1 mb-3">Choose the API key your IDE will use to authenticate requests.</p>
                  
                  {apiKeysLoading ? (
                    <div className="h-10 w-full md:w-2/3 animate-pulse bg-[#0B0E14] rounded-md border border-muted/10" />
                  ) : developerKeys.length > 0 ? (
                    <Select value={selectedKey} onValueChange={setSelectedKey}>
                      <SelectTrigger className="w-full md:w-2/3 bg-[#0B0E14] border-muted/20 h-10">
                        <SelectValue placeholder="Select an API Key" />
                      </SelectTrigger>
                      <SelectContent>
                        {developerKeys.map((key: any) => (
                          <SelectItem key={key.id} value={`leaka_dev_... (Key ${key.id})`}>
                            {key.name}
                          </SelectItem>
                        ))}
                      </SelectContent>
                    </Select>
                  ) : (
                    <div className="p-3 bg-amber-500/10 border border-amber-500/20 rounded-md flex items-center justify-between">
                      <p className="text-sm text-amber-400">No Developer API Keys found.</p>
                      <Link href="/settings">
                        <Button variant="outline" size="sm" className="h-8 border-amber-500/30 text-amber-300 hover:bg-amber-500/20">Generate Key</Button>
                      </Link>
                    </div>
                  )}
                </div>

                {/* Step 2 */}
                <div className="relative pl-8">
                  <div className="absolute left-0 top-0.5 flex h-6 w-6 items-center justify-center rounded-full bg-indigo-500/20 text-xs font-bold text-indigo-300 ring-4 ring-[#161922]">2</div>
                  <div className="absolute left-3 top-8 -bottom-10 w-px bg-border/50" />
                  <h4 className="text-sm font-semibold text-foreground">Add to your IDE Configuration</h4>
                  <p className="text-xs text-muted-foreground mt-1 mb-4">Paste this JSON into your Cursor, Windsurf, or Claude Desktop MCP settings file.</p>
                  
                  <div className="relative group">
                    <div className="absolute top-3 right-3 z-10">
                      <Button 
                        size="icon" 
                        variant="ghost" 
                        className="h-8 w-8 bg-[#161922]/80 hover:bg-[#161922] border border-border/50 text-muted-foreground"
                        onClick={() => handleCopy(configSnippet, "json")}
                      >
                        {copiedSection === "json" ? <CheckCircle2 className="h-4 w-4 text-emerald-400" /> : <Copy className="h-4 w-4" />}
                      </Button>
                    </div>
                    <pre className="p-4 rounded-lg bg-[#0B0E14] border border-muted/20 text-sm font-mono text-muted-foreground overflow-x-auto selection:bg-indigo-500/30">
                      <code className="text-indigo-200">
{`{
  "mcpServers": {
    "leaka-ai": {
      "type": "sse",
      "url": "https://api.leaka.live/api/mcp/sse",
      "env": {
        "LEAKA_API_KEY": "${selectedKey.includes('leaka_dev_') ? 'YOUR_ACTUAL_KEY_HERE' : selectedKey}"
      }
    }
  }
}`}
                      </code>
                    </pre>
                    <p className="text-[10px] text-muted-foreground mt-2 flex items-center gap-1.5">
                      <Shield className="w-3 h-3" /> Security Note: For actual usage, replace the placeholder with the raw key you copied during generation.
                    </p>
                  </div>
                </div>

                {/* Step 3 */}
                <div className="relative pl-8">
                  <div className="absolute left-0 top-0.5 flex h-6 w-6 items-center justify-center rounded-full bg-indigo-500/20 text-xs font-bold text-indigo-300 ring-4 ring-[#161922]">3</div>
                  <h4 className="text-sm font-semibold text-foreground">Prompt your Agent</h4>
                  <p className="text-xs text-muted-foreground mt-1 mb-4">Once connected, just ask your IDE's agent naturally:</p>
                  
                  <div className="p-4 rounded-lg bg-indigo-500/5 border border-indigo-500/20">
                    <p className="text-sm text-indigo-200 italic">"Hey, please use the Leaka MCP server to trigger the smoke test suite and let me know if it passes. Use my API key."</p>
                  </div>
                </div>
              </div>
            </div>
          </div>
        </div>

        {/* Right Column: Available Tools & Docs */}
        <div className="space-y-6">
          <div className="bg-[#161922] border border-muted/20 rounded-xl p-6">
            <h3 className="text-base font-medium flex items-center gap-2 mb-4">
              <Blocks className="w-4 h-4 text-purple-400" /> Available Tools
            </h3>
            
            <div className="space-y-4">
              <div className="group">
                <code className="text-xs font-mono text-emerald-400 bg-emerald-400/10 px-1.5 py-0.5 rounded">trigger_test_suite</code>
                <p className="text-xs text-muted-foreground mt-1.5">Triggers a test suite dynamically against your local/staging environment.</p>
              </div>
              <div className="group">
                <code className="text-xs font-mono text-emerald-400 bg-emerald-400/10 px-1.5 py-0.5 rounded">get_test_status</code>
                <p className="text-xs text-muted-foreground mt-1.5">Polls real-time execution status and results.</p>
              </div>
              <div className="group">
                <code className="text-xs font-mono text-emerald-400 bg-emerald-400/10 px-1.5 py-0.5 rounded">analyze_failure</code>
                <p className="text-xs text-muted-foreground mt-1.5">Retrieves DOM snapshots, console logs, and failure traces directly into your editor.</p>
              </div>
              <div className="group">
                <code className="text-xs font-mono text-emerald-400 bg-emerald-400/10 px-1.5 py-0.5 rounded">create_test_case</code>
                <p className="text-xs text-muted-foreground mt-1.5">Generates new resilient tests using natural language.</p>
              </div>
              <div className="group">
                <code className="text-xs font-mono text-emerald-400 bg-emerald-400/10 px-1.5 py-0.5 rounded">quarantine_test</code>
                <p className="text-xs text-muted-foreground mt-1.5">Flags flaky tests to unblock CI/CD pipelines instantly.</p>
              </div>
            </div>
          </div>
        </div>
      </div>
    </div>
  );
}
