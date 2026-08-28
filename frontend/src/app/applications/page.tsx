"use client";

import { useState } from "react";
import Link from "next/link";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { api, type ApplicationCreate } from "@/lib/api";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Textarea } from "@/components/ui/textarea";
import { Skeleton } from "@/components/ui/skeleton";
import {
  Dialog, DialogContent, DialogDescription, DialogFooter,
  DialogHeader, DialogTitle, DialogTrigger,
} from "@/components/ui/dialog";
import { Compass, Plus, Loader2, ArrowRight, Globe } from "lucide-react";
import { toast } from "@/components/ui/use-toast";
import { formatDate } from "@/lib/utils";

export default function ApplicationsPage() {
  const qc = useQueryClient();
  const [open, setOpen] = useState(false);
  const [form, setForm] = useState<ApplicationCreate>({
    name: "",
    base_url: "",
    description: "",
    login_hint: "",
  });

  const { data: apps, isLoading } = useQuery({
    queryKey: ["applications"],
    queryFn: () => api.listApplications(),
  });

  const createMut = useMutation({
    mutationFn: () =>
      api.createApplication({
        name: form.name.trim(),
        base_url: form.base_url.trim(),
        description: form.description?.trim() || undefined,
        login_hint: form.login_hint?.trim() || undefined,
      }),
    onSuccess: (app) => {
      toast({ title: "Application connected", description: app.name });
      qc.invalidateQueries({ queryKey: ["applications"] });
      setOpen(false);
      setForm({ name: "", base_url: "", description: "", login_hint: "" });
    },
    onError: (e: Error) =>
      toast({ title: "Could not connect app", description: e.message, variant: "destructive" }),
  });

  const canSubmit = form.name.trim() && /^https?:\/\//.test(form.base_url.trim());

  return (
    <div className="space-y-6">
      <div className="flex items-start justify-between flex-wrap gap-4">
        <div>
          <h1 className="text-2xl font-semibold tracking-tight flex items-center gap-2">
            <Compass className="w-6 h-6 text-primary" /> Applications
          </h1>
          <p className="text-sm text-muted-foreground mt-1">
            Connect an app and let Leaka explore it — discover pages, forms, and
            flows, then see what&apos;s untested.
          </p>
        </div>

        <Dialog open={open} onOpenChange={setOpen}>
          <DialogTrigger asChild>
            <Button><Plus className="w-4 h-4 mr-2" />Connect application</Button>
          </DialogTrigger>
          <DialogContent>
            <DialogHeader>
              <DialogTitle>Connect an application</DialogTitle>
              <DialogDescription>
                Leaka will autonomously explore this app to build a map of its
                pages and flows. It only observes — it never submits forms,
                completes purchases, or performs destructive actions.
              </DialogDescription>
            </DialogHeader>
            <div className="space-y-4 py-2">
              <div>
                <Label>Name</Label>
                <Input
                  className="mt-1"
                  placeholder="e.g. Acme Store"
                  value={form.name}
                  onChange={(e) => setForm((f) => ({ ...f, name: e.target.value }))}
                />
              </div>
              <div>
                <Label>Base URL</Label>
                <Input
                  className="mt-1 font-mono"
                  placeholder="https://www.saucedemo.com"
                  value={form.base_url}
                  onChange={(e) => setForm((f) => ({ ...f, base_url: e.target.value }))}
                />
              </div>
              <div>
                <Label>Description (optional)</Label>
                <Textarea
                  className="mt-1 text-sm"
                  rows={2}
                  placeholder="What is this app? What are its most important flows?"
                  value={form.description ?? ""}
                  onChange={(e) => setForm((f) => ({ ...f, description: e.target.value }))}
                />
              </div>
              <div>
                <Label>Login hint (optional)</Label>
                <Input
                  className="mt-1"
                  placeholder="e.g. Log in with standard_user / secret_sauce"
                  value={form.login_hint ?? ""}
                  onChange={(e) => setForm((f) => ({ ...f, login_hint: e.target.value }))}
                />
                <p className="text-xs text-muted-foreground mt-1">
                  Helps the explorer reach authenticated areas. Use test credentials only.
                </p>
              </div>
            </div>
            <DialogFooter>
              <Button variant="outline" onClick={() => setOpen(false)}>Cancel</Button>
              <Button disabled={!canSubmit || createMut.isPending} onClick={() => createMut.mutate()}>
                {createMut.isPending ? <Loader2 className="w-4 h-4 mr-2 animate-spin" /> : <Plus className="w-4 h-4 mr-2" />}
                Connect
              </Button>
            </DialogFooter>
          </DialogContent>
        </Dialog>
      </div>

      {isLoading ? (
        <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
          {Array.from({ length: 4 }).map((_, i) => <Skeleton key={i} className="h-32 w-full rounded-lg" />)}
        </div>
      ) : !apps?.length ? (
        <EmptyApps onConnect={() => setOpen(true)} />
      ) : (
        <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
          {apps.map((app) => (
            <Link key={app.id} href={`/applications/${app.id}`}>
              <Card className="hover:border-primary/40 transition-colors cursor-pointer h-full">
                <CardHeader className="pb-3">
                  <CardTitle className="text-base flex items-center gap-2">
                    <Globe className="w-4 h-4 text-primary shrink-0" />
                    {app.name}
                  </CardTitle>
                  <CardDescription className="truncate">{app.base_url}</CardDescription>
                </CardHeader>
                <CardContent>
                  {app.description && (
                    <p className="text-sm text-muted-foreground line-clamp-2">{app.description}</p>
                  )}
                  <div className="flex items-center justify-between mt-3 text-xs text-muted-foreground">
                    <span>Connected {formatDate(app.created_at)}</span>
                    <span className="inline-flex items-center gap-1 text-primary">
                      Open map <ArrowRight className="w-3 h-3" />
                    </span>
                  </div>
                </CardContent>
              </Card>
            </Link>
          ))}
        </div>
      )}
    </div>
  );
}

function EmptyApps({ onConnect }: { onConnect: () => void }) {
  return (
    <div className="text-center py-14 space-y-3">
      <div className="w-12 h-12 rounded-full bg-muted mx-auto grid place-items-center">
        <Compass className="w-6 h-6 text-muted-foreground" />
      </div>
      <div className="font-medium">No applications yet</div>
      <p className="text-sm text-muted-foreground max-w-md mx-auto">
        Connect your first application. Leaka will explore it and show you every
        page and flow — and which ones have no test coverage yet.
      </p>
      <Button className="mt-2" onClick={onConnect}>
        <Plus className="w-4 h-4 mr-2" /> Connect application
      </Button>
    </div>
  );
}
