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
import { Plus, Database, Server, Key, RefreshCw, Shield } from "lucide-react";
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
  const [envName, setEnvName] = useState("");
  const [envBaseUrl, setEnvBaseUrl] = useState("");
  const [envVars, setEnvVars] = useState("");
  const [envPolicies, setEnvPolicies] = useState("");

  const envMut = useMutation({
    mutationFn: () => api.createEnvironment(appId, {
      name: envName,
      base_url: envBaseUrl,
      variables: envVars || undefined,
      policies: envPolicies || undefined,
    }),
    onSuccess: () => {
      toast({ title: "Environment created" });
      setEnvOpen(false);
      setEnvName(""); setEnvBaseUrl(""); setEnvVars(""); setEnvPolicies("");
      qc.invalidateQueries({ queryKey: ["environments", appId] });
    },
  });

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
              <Button size="sm"><Plus className="w-4 h-4 mr-2" />New Environment</Button>
            </DialogTrigger>
            <DialogContent>
              <DialogHeader>
                <DialogTitle>New Environment</DialogTitle>
                <DialogDescription>Define a reusable target environment.</DialogDescription>
              </DialogHeader>
              <div className="space-y-4 py-4">
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
                    <CardTitle className="text-base flex justify-between">
                      {env.name}
                    </CardTitle>
                  </CardHeader>
                  <CardContent className="p-4 pt-3 space-y-3">
                    <div className="text-sm truncate font-mono text-muted-foreground bg-muted p-2 rounded" title={env.base_url}>
                      {env.base_url}
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
              <div className="grid grid-cols-2 gap-4 py-4">
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
