"use client";

import { useState } from "react";
import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import { api, type EnvironmentOut, type TestFixtureOut } from "@/lib/api";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Textarea } from "@/components/ui/textarea";
import { Skeleton } from "@/components/ui/skeleton";
import { Plus, Database, Server, Key, RefreshCw, Shield, Trash2, Edit2 } from "lucide-react";
import { toast } from "@/components/ui/use-toast";
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
  DialogTrigger,
} from "@/components/ui/dialog";

export function ConfigurationTab({ appId }: { appId: number }) {
  const qc = useQueryClient();

  const { data: envs, isLoading: envsLoading } = useQuery({
    queryKey: ["environments", appId],
    queryFn: () => api.listEnvironments(appId),
  });

  const { data: fixtures, isLoading: fixLoading } = useQuery({
    queryKey: ["fixtures", appId],
    queryFn: () => api.listFixtures(appId),
  });

  // Environment form state
  const [envOpen, setEnvOpen] = useState(false);
  const [editingEnvId, setEditingEnvId] = useState<number | null>(null);
  const [envName, setEnvName] = useState("");
  const [envBaseUrl, setEnvBaseUrl] = useState("");
  const [envExecutionLocation, setEnvExecutionLocation] = useState("cloud");
  const [envVars, setEnvVars] = useState("");
  const [envPolicies, setEnvPolicies] = useState("");
  const [envAuthStrategy, setEnvAuthStrategy] = useState("none");
  const [envAuthApiUrl, setEnvAuthApiUrl] = useState("");
  const [envAuthHeaders, setEnvAuthHeaders] = useState("");
  const [envAuthPayload, setEnvAuthPayload] = useState("");
  const [envAuthTokenPath, setEnvAuthTokenPath] = useState("");
  const [envAuthTarget, setEnvAuthTarget] = useState("localStorage");
  const [envAuthKey, setEnvAuthKey] = useState("");
  const [envAuthDomain, setEnvAuthDomain] = useState("");
  const [envAuthStateTemplate, setEnvAuthStateTemplate] = useState("");

  const envMut = useMutation({
    mutationFn: () => {
      let stateTemplate = envAuthStateTemplate || undefined;
      
      if (envAuthStrategy === "api_injection") {
        const cleanDomain = envAuthDomain.replace(/^(https?:\/\/)/, "").replace(/\/$/, "");
        if (envAuthTarget === "localStorage") {
          stateTemplate = JSON.stringify({
            cookies: [],
            origins: [{
              origin: `https://${cleanDomain}`,
              localStorage: [{
                name: envAuthKey,
                value: "{{token}}"
              }]
            }]
          }, null, 2);
        } else {
          stateTemplate = JSON.stringify({
            cookies: [{
              name: envAuthKey,
              value: "{{token}}",
              domain: cleanDomain,
              path: "/",
              secure: true
            }],
            origins: []
          }, null, 2);
        }
      }

      const payload = {
        name: envName,
        base_url: envBaseUrl,
        execution_location: envExecutionLocation,
        variables: envVars || undefined,
        policies: envPolicies || undefined,
        auth_strategy: envAuthStrategy !== "none" ? envAuthStrategy : undefined,
        auth_api_url: envAuthApiUrl || undefined,
        auth_api_headers: envAuthHeaders || undefined,
        auth_payload: envAuthPayload || undefined,
        auth_token_path: envAuthTokenPath || undefined,
        auth_state_template: stateTemplate,
      };

      if (editingEnvId) {
        return api.updateEnvironment(appId, editingEnvId, payload);
      }
      return api.createEnvironment(appId, payload);
    },
    onSuccess: () => {
      toast({ title: editingEnvId ? "Environment updated" : "Environment created" });
      setEnvOpen(false);
      qc.invalidateQueries({ queryKey: ["environments", appId] });
    },
  });

  const handleOpenNewEnv = () => {
    setEditingEnvId(null);
    setEnvName(""); setEnvBaseUrl(""); setEnvVars(""); setEnvPolicies("");
    setEnvAuthStrategy("none"); setEnvAuthApiUrl(""); setEnvAuthHeaders(""); setEnvAuthPayload(""); setEnvAuthTokenPath(""); setEnvAuthStateTemplate("");
    setEnvAuthTarget("localStorage"); setEnvAuthKey(""); setEnvAuthDomain("");
    setEnvOpen(true);
  };

  const handleEditEnv = (env: EnvironmentOut) => {
    setEditingEnvId(env.id);
    setEnvName(env.name);
    setEnvBaseUrl(env.base_url);
    setEnvExecutionLocation(env.execution_location || "cloud");
    setEnvVars(env.variables || "");
    setEnvPolicies(env.policies || "");
    setEnvAuthStrategy(env.auth_strategy || "none");
    setEnvAuthApiUrl(env.auth_api_url || "");
    setEnvAuthHeaders(env.auth_api_headers || "");
    setEnvAuthPayload(env.auth_payload || "");
    setEnvAuthTokenPath(env.auth_token_path || "");
    setEnvAuthStateTemplate(env.auth_state_template || "");
    
    if (env.auth_state_template && env.auth_strategy === "api_injection") {
      try {
        const parsed = JSON.parse(env.auth_state_template);
        if (parsed.cookies && parsed.cookies.length > 0) {
          setEnvAuthTarget("cookie");
          setEnvAuthKey(parsed.cookies[0].name);
          setEnvAuthDomain(parsed.cookies[0].domain);
        } else if (parsed.origins && parsed.origins.length > 0 && parsed.origins[0].localStorage?.length > 0) {
          setEnvAuthTarget("localStorage");
          setEnvAuthKey(parsed.origins[0].localStorage[0].name);
          setEnvAuthDomain(parsed.origins[0].origin.replace("https://", ""));
        }
      } catch (e) {}
    } else {
      setEnvAuthTarget("localStorage"); setEnvAuthKey(""); setEnvAuthDomain("");
    }
    setEnvOpen(true);
  };

  const envDeleteMut = useMutation({
    mutationFn: (envId: number) => api.deleteEnvironment(appId, envId),
    onSuccess: () => {
      toast({ title: "Environment deleted" });
      qc.invalidateQueries({ queryKey: ["environments", appId] });
    },
  });

  const handleDeleteEnv = (id: number, name: string) => {
    if (window.confirm(`Are you sure you want to permanently delete the environment "${name}"?`)) {
      envDeleteMut.mutate(id);
    }
  };

  // Fixture form state
  const [fixOpen, setFixOpen] = useState(false);
  const [fixName, setFixName] = useState("");
  const [fixSetupUrl, setFixSetupUrl] = useState("");
  const [fixSetupPayload, setFixSetupPayload] = useState("");
  const [fixTeardownUrl, setFixTeardownUrl] = useState("");
  const [fixTeardownPayload, setFixTeardownPayload] = useState("");

  const fixMut = useMutation({
    mutationFn: () => api.createFixture(appId, {
      name: fixName,
      setup_api_url: fixSetupUrl,
      setup_payload: fixSetupPayload || undefined,
      teardown_api_url: fixTeardownUrl || undefined,
      teardown_payload: fixTeardownPayload || undefined,
    }),
    onSuccess: () => {
      toast({ title: "Fixture created" });
      setFixOpen(false);
      setFixName(""); setFixSetupUrl(""); setFixSetupPayload(""); setFixTeardownUrl(""); setFixTeardownPayload("");
      qc.invalidateQueries({ queryKey: ["fixtures", appId] });
    },
  });

  return (
    <div className="space-y-6">
      <Card>
        <CardHeader className="flex flex-row items-center justify-between">
          <div>
            <CardTitle className="text-xl flex items-center gap-2">
              <Server className="w-5 h-5 text-primary" />
              Environments
            </CardTitle>
            <CardDescription>
              Define base URLs and credentials for different deployment stages.
            </CardDescription>
          </div>
          <Dialog open={envOpen} onOpenChange={setEnvOpen}>
            <DialogTrigger asChild>
              <Button size="sm" onClick={handleOpenNewEnv}><Plus className="w-4 h-4 mr-2" />New Environment</Button>
            </DialogTrigger>
            <DialogContent>
              <DialogHeader>
                <DialogTitle>{editingEnvId ? "Edit Environment" : "New Environment"}</DialogTitle>
                <DialogDescription>Define a reusable target environment.</DialogDescription>
              </DialogHeader>
              <div className="space-y-4 py-4 max-h-[60vh] overflow-y-auto px-2">
                <div className="space-y-2">
                  <Label>Name</Label>
                  <Input placeholder="e.g. Staging" value={envName} onChange={e => setEnvName(e.target.value)} />
                </div>
                <div className="space-y-2">
                  <Label>Base URL</Label>
                  <Input placeholder="https://staging.myapp.com" value={envBaseUrl} onChange={e => setEnvBaseUrl(e.target.value)} />
                </div>
                <div className="space-y-2">
                  <Label>Variables (JSON)</Label>
                  <Textarea placeholder={'{"API_KEY": "xxx"}'} value={envVars} onChange={e => setEnvVars(e.target.value)} className="font-mono text-sm" />
                </div>
                <div className="space-y-2">
                  <Label className="flex items-center gap-2">
                    <Shield className="w-4 h-4 text-amber-500" />
                    AI Policies (Natural Language)
                  </Label>
                  <Textarea placeholder="e.g. Do not submit any forms with 'Delete' in the title." value={envPolicies} onChange={e => setEnvPolicies(e.target.value)} className="text-sm h-20" />
                  <p className="text-xs text-muted-foreground">Governable AI: The agent will explicitly evaluate these rules before executing actions.</p>
                </div>
                <div className="space-y-2 pt-4 border-t border-muted">
                  <h4 className="font-medium text-sm">Enterprise Authentication</h4>
                  <p className="text-xs text-muted-foreground">Automatically inject session state to bypass UI logins.</p>
                  
                  <div className="space-y-4 pt-2">
                    <div className="space-y-2">
                      <Label>Execution Location</Label>
                      <select 
                        value={envExecutionLocation} 
                        onChange={e => setEnvExecutionLocation(e.target.value)}
                        className="flex h-10 w-full items-center justify-between rounded-md border border-input bg-background px-3 py-2 text-sm ring-offset-background placeholder:text-muted-foreground focus:outline-none focus:ring-2 focus:ring-ring focus:ring-offset-2 disabled:cursor-not-allowed disabled:opacity-50"
                      >
                        <option value="cloud">Leaka Cloud (Azure Serverless)</option>
                        <option value="self_hosted">Self-Hosted Runner (CI/CD, VPC)</option>
                      </select>
                      <p className="text-xs text-muted-foreground">
                        {envExecutionLocation === "cloud" ? 
                          "Tests run instantly on our Azure infrastructure. Best for public URLs." : 
                          "Tests will queue and wait for your local CI/CD CLI runner to pick them up. Best for private localhost or VPNs."}
                      </p>
                    </div>

                    <div className="space-y-2">
                      <Label>Auth Strategy</Label>
                      <select 
                        value={envAuthStrategy} 
                        onChange={e => setEnvAuthStrategy(e.target.value)}
                        className="flex h-10 w-full items-center justify-between rounded-md border border-input bg-background px-3 py-2 text-sm ring-offset-background placeholder:text-muted-foreground focus:outline-none focus:ring-2 focus:ring-ring focus:ring-offset-2 disabled:cursor-not-allowed disabled:opacity-50"
                      >
                        <option value="none">None (Standard UI Login)</option>
                        <option value="api_injection">API Session Injection</option>
                        <option value="state_cache">Golden State Cache</option>
                      </select>
                    </div>

                    {envAuthStrategy === "api_injection" && (
                      <div className="space-y-6 pt-2">
                        <div className="space-y-4 p-4 border rounded-md bg-muted/10 border-primary/20">
                          <h4 className="font-semibold text-sm text-primary">1. Auth Request</h4>
                          <div className="space-y-2">
                            <Label className="text-xs">API Endpoint</Label>
                            <Input placeholder="https://api.app.com/v1/auth/login" value={envAuthApiUrl} onChange={e => setEnvAuthApiUrl(e.target.value)} />
                          </div>
                          <div className="space-y-2">
                            <Label className="text-xs">Headers (JSON)</Label>
                            <Textarea placeholder={'{"apikey": "...", "Content-Type": "application/json"}'} value={envAuthHeaders} onChange={e => setEnvAuthHeaders(e.target.value)} className="font-mono text-xs h-20" />
                          </div>
                          <div className="space-y-2">
                            <Label className="text-xs">JSON Payload</Label>
                            <Textarea placeholder={'{"email": "...", "password": "..."}'} value={envAuthPayload} onChange={e => setEnvAuthPayload(e.target.value)} className="font-mono text-xs h-24" />
                          </div>
                        </div>

                        <div className="space-y-4 p-4 border rounded-md bg-muted/10 border-primary/20">
                          <h4 className="font-semibold text-sm text-primary">2. Token Extraction</h4>
                          <div className="space-y-2">
                            <Label className="text-xs">JSON Path to Token</Label>
                            <Input placeholder="data.access_token" value={envAuthTokenPath} onChange={e => setEnvAuthTokenPath(e.target.value)} />
                            <p className="text-[10px] text-muted-foreground">Leave empty to inject the entire JSON response object.</p>
                          </div>
                        </div>
                        
                        <div className="space-y-4 p-4 border rounded-md bg-muted/10 border-primary/20">
                          <h4 className="font-semibold text-sm text-primary">3. Browser Injection</h4>
                          <div className="grid grid-cols-2 gap-4">
                            <div className="space-y-2">
                              <Label className="text-xs">Target</Label>
                              <select 
                                value={envAuthTarget} 
                                onChange={e => setEnvAuthTarget(e.target.value)}
                                className="flex h-10 w-full items-center justify-between rounded-md border border-input bg-background px-3 py-2 text-sm ring-offset-background placeholder:text-muted-foreground focus:outline-none focus:ring-2 focus:ring-ring focus:ring-offset-2"
                              >
                                <option value="localStorage">LocalStorage</option>
                                <option value="cookie">Cookie</option>
                              </select>
                            </div>
                            <div className="space-y-2">
                              <Label className="text-xs">Key Name</Label>
                              <Input placeholder="e.g. auth-token" value={envAuthKey} onChange={e => setEnvAuthKey(e.target.value)} />
                            </div>
                            <div className="col-span-2 space-y-2">
                              <Label className="text-xs">Domain</Label>
                              <Input placeholder="app.acme.com" value={envAuthDomain} onChange={e => setEnvAuthDomain(e.target.value)} />
                            </div>
                          </div>
                        </div>
                      </div>
                    )}

                    {envAuthStrategy === "state_cache" && (
                      <div className="space-y-4 p-4 border rounded-md bg-muted/10">
                        <div className="space-y-2">
                          <Label className="text-xs">Golden State JSON (Playwright format)</Label>
                          <Textarea placeholder={'{"cookies": [...], "origins": [...]}'} value={envAuthStateTemplate} onChange={e => setEnvAuthStateTemplate(e.target.value)} className="font-mono text-xs h-40" />
                          <p className="text-[10px] text-muted-foreground">Paste your pre-authenticated Playwright storage state here.</p>
                        </div>
                      </div>
                    )}
                  </div>
                </div>

              </div>
              <DialogFooter>
                <Button variant="outline" onClick={() => setEnvOpen(false)}>Cancel</Button>
                <Button onClick={() => envMut.mutate()} disabled={envMut.isPending || !envName || !envBaseUrl}>
                  Save
                </Button>
              </DialogFooter>
            </DialogContent>
          </Dialog>
        </CardHeader>
        <CardContent>
          {envsLoading ? <Skeleton className="h-20 w-full" /> : (
            <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
              {envs?.length === 0 && <p className="text-sm text-muted-foreground col-span-full">No environments defined.</p>}
              {envs?.map(env => (
                <Card key={env.id} className="overflow-hidden border-t-4 border-t-primary">
                  <CardHeader className="p-4 bg-muted/30 pb-2">
                    <CardTitle className="text-base flex justify-between items-center">
                      {env.name}
                      <div className="flex gap-1">
                        <Button variant="ghost" size="icon" className="h-7 w-7 text-muted-foreground hover:text-primary" onClick={() => handleEditEnv(env)}>
                          <Edit2 className="w-4 h-4" />
                        </Button>
                        <Button variant="ghost" size="icon" className="h-7 w-7 text-muted-foreground hover:text-destructive" onClick={() => handleDeleteEnv(env.id, env.name)}>
                          <Trash2 className="w-4 h-4" />
                        </Button>
                      </div>
                    </CardTitle>
                  </CardHeader>
                  <CardContent className="p-4 pt-3 space-y-3">
                    <div className="text-sm truncate font-mono text-muted-foreground bg-muted p-2 rounded" title={env.base_url}>
                      {env.base_url}
                    </div>
                    
                    <div className="flex items-center gap-2 text-xs font-medium bg-secondary/50 p-2 rounded text-secondary-foreground border border-border/50">
                      <Server className="w-3 h-3" /> 
                      {env.execution_location === 'self_hosted' ? 'Self-Hosted Runner (VPC/CI)' : 'Leaka Cloud (Azure)'}
                    </div>

                    {env.variables && (
                      <div className="flex items-center gap-2 text-xs text-emerald-600 dark:text-emerald-400 font-medium bg-emerald-500/10 p-2 rounded">
                        <Key className="w-3 h-3" /> Secure variables injected
                      </div>
                    )}
                    {env.policies && (
                      <div className="flex flex-col gap-1 text-xs text-amber-600 dark:text-amber-500 font-medium bg-amber-500/10 p-2 rounded border border-amber-500/20">
                        <div className="flex items-center gap-2">
                          <Shield className="w-3 h-3" /> Active Policies
                        </div>
                        <span className="font-normal text-muted-foreground line-clamp-2" title={env.policies}>{env.policies}</span>
                      </div>
                    )}
                  </CardContent>
                </Card>
              ))}
            </div>
          )}
        </CardContent>
      </Card>

      <Card>
        <CardHeader className="flex flex-row items-center justify-between">
          <div>
            <CardTitle className="text-xl flex items-center gap-2">
              <Database className="w-5 h-5 text-primary" />
              Test Fixtures
            </CardTitle>
            <CardDescription>
              Provision and teardown test data via your API.
            </CardDescription>
          </div>
          <Dialog open={fixOpen} onOpenChange={setFixOpen}>
            <DialogTrigger asChild>
              <Button size="sm"><Plus className="w-4 h-4 mr-2" />New Fixture</Button>
            </DialogTrigger>
            <DialogContent className="max-w-2xl">
              <DialogHeader>
                <DialogTitle>New Test Fixture</DialogTitle>
                <DialogDescription>Configure webhook endpoints to provision temporary test data.</DialogDescription>
              </DialogHeader>
              <div className="grid grid-cols-2 gap-4 py-4 max-h-[60vh] overflow-y-auto px-2">
                <div className="col-span-2 space-y-2">
                  <Label>Fixture Name</Label>
                  <Input placeholder="e.g. Fresh Pro User" value={fixName} onChange={e => setFixName(e.target.value)} />
                </div>
                
                {/* Setup */}
                <div className="space-y-4 p-4 border rounded-md bg-muted/10">
                  <h4 className="font-semibold text-sm">Setup (Pre-flight)</h4>
                  <div className="space-y-2">
                    <Label className="text-xs">POST URL</Label>
                    <Input placeholder="https://api.app.com/test/seed" value={fixSetupUrl} onChange={e => setFixSetupUrl(e.target.value)} />
                  </div>
                  <div className="space-y-2">
                    <Label className="text-xs">JSON Payload</Label>
                    <Textarea placeholder={'{"plan": "pro"}'} value={fixSetupPayload} onChange={e => setFixSetupPayload(e.target.value)} className="font-mono text-xs h-24" />
                  </div>
                </div>

                {/* Teardown */}
                <div className="space-y-4 p-4 border rounded-md bg-muted/10">
                  <h4 className="font-semibold text-sm">Teardown (Post-flight)</h4>
                  <div className="space-y-2">
                    <Label className="text-xs">POST URL (Optional)</Label>
                    <Input placeholder="https://api.app.com/test/cleanup" value={fixTeardownUrl} onChange={e => setFixTeardownUrl(e.target.value)} />
                  </div>
                  <div className="space-y-2">
                    <Label className="text-xs">JSON Payload (Optional)</Label>
                    <Textarea placeholder={'{"action": "delete"}'} value={fixTeardownPayload} onChange={e => setFixTeardownPayload(e.target.value)} className="font-mono text-xs h-24" />
                  </div>
                </div>
              </div>
              <DialogFooter>
                <Button variant="outline" onClick={() => setFixOpen(false)}>Cancel</Button>
                <Button onClick={() => fixMut.mutate()} disabled={fixMut.isPending || !fixName || !fixSetupUrl}>
                  Save Fixture
                </Button>
              </DialogFooter>
            </DialogContent>
          </Dialog>
        </CardHeader>
        <CardContent>
          {fixLoading ? <Skeleton className="h-20 w-full" /> : (
            <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
              {fixtures?.length === 0 && <p className="text-sm text-muted-foreground col-span-full">No fixtures defined.</p>}
              {fixtures?.map(fix => (
                <Card key={fix.id} className="overflow-hidden">
                  <CardHeader className="p-4 bg-muted/30 pb-2">
                    <CardTitle className="text-base flex justify-between items-center">
                      {fix.name}
                      <Button variant="ghost" size="sm" className="h-7 px-2 text-xs">
                        <RefreshCw className="w-3 h-3 mr-1" /> Test Fixture
                      </Button>
                    </CardTitle>
                  </CardHeader>
                  <CardContent className="p-4 space-y-3">
                    <div className="space-y-1">
                      <div className="text-xs font-semibold text-muted-foreground">SETUP</div>
                      <div className="text-sm truncate font-mono">{fix.setup_api_url}</div>
                    </div>
                    {fix.teardown_api_url && (
                      <div className="space-y-1">
                        <div className="text-xs font-semibold text-muted-foreground">TEARDOWN</div>
                        <div className="text-sm truncate font-mono">{fix.teardown_api_url}</div>
                      </div>
                    )}
                  </CardContent>
                </Card>
              ))}
            </div>
          )}
        </CardContent>
      </Card>
    </div>
  );
}
