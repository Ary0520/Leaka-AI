"use client";

import React, { useEffect, useState } from "react";
import { getWorkspaces, createWorkspace, WorkspaceOut } from "@/lib/api";
import { Select, SelectContent, SelectItem, SelectSeparator, SelectTrigger, SelectValue } from "@/components/ui/select";
import { useToast } from "@/components/ui/use-toast";
import { useWorkspace } from "@/app/providers";
import { Dialog, DialogContent, DialogHeader, DialogTitle, DialogDescription, DialogFooter } from "@/components/ui/dialog";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Button } from "@/components/ui/button";
import { Loader2, PlusCircle } from "lucide-react";

export function WorkspaceSwitcher() {
  const [workspaces, setWorkspaces] = useState<WorkspaceOut[]>([]);
  const { activeWorkspaceId, setActiveWorkspaceId } = useWorkspace();
  const { toast } = useToast();
  
  const [isModalOpen, setIsModalOpen] = useState(false);
  const [newOrgName, setNewOrgName] = useState("");
  const [newWsName, setNewWsName] = useState("");
  const [isCreating, setIsCreating] = useState(false);

  const fetchWorkspaces = () => {
    getWorkspaces()
      .then((data) => setWorkspaces(data))
      .catch((err) => console.error("Failed to load workspaces", err));
  };

  useEffect(() => {
    fetchWorkspaces();
  }, []);

  const handleValueChange = (val: string) => {
    if (val === "create_new") {
      setIsModalOpen(true);
      return; // Do not switch active workspace yet
    }

    setActiveWorkspaceId(val);
    
    if (val !== "personal") {
      toast({
        title: "Workspace Switched",
        description: `You are now viewing ${workspaces.find(w => w.id.toString() === val)?.name}`,
      });
    } else {
      toast({
        title: "Workspace Switched",
        description: `You are now viewing your personal workspace`,
      });
    }
    
    window.location.reload();
  };

  const handleCreate = async () => {
    if (!newOrgName.trim() || !newWsName.trim()) return;
    setIsCreating(true);
    try {
      const created = await createWorkspace(newOrgName, newWsName);
      toast({ title: "Workspace created!" });
      setIsModalOpen(false);
      setNewOrgName("");
      setNewWsName("");
      // Switch to it immediately
      setActiveWorkspaceId(created.id.toString());
      window.location.reload();
    } catch (e: any) {
      toast({ title: "Failed to create", description: e.message, variant: "destructive" });
    } finally {
      setIsCreating(false);
    }
  };

  return (
    <>
      <div className="px-6 pb-2 mt-2">
        <div className="text-[10px] font-semibold text-muted-foreground uppercase tracking-wider mb-1 px-1">
          Active Workspace
        </div>
        <Select value={activeWorkspaceId} onValueChange={handleValueChange}>
          <SelectTrigger className="w-full h-8 text-xs bg-accent/50 border-0 focus:ring-0 rounded-md">
            <SelectValue placeholder="Select Workspace" />
          </SelectTrigger>
          <SelectContent>
            <SelectItem value="personal">Personal Workspace</SelectItem>
            {workspaces.map((ws) => (
              <SelectItem key={ws.id} value={ws.id.toString()}>
                {ws.name}
              </SelectItem>
            ))}
            <SelectSeparator />
            <SelectItem value="create_new" className="text-primary font-medium focus:bg-primary/10 focus:text-primary cursor-pointer">
              <div className="flex items-center">
                <PlusCircle className="w-3.5 h-3.5 mr-2" />
                Create Workspace
              </div>
            </SelectItem>
          </SelectContent>
        </Select>
      </div>

      <Dialog open={isModalOpen} onOpenChange={setIsModalOpen}>
        <DialogContent>
          <DialogHeader>
            <DialogTitle>Create a Team Workspace</DialogTitle>
            <DialogDescription>
              Workspaces allow you to collaborate with your team, run CI checks, and share test results.
            </DialogDescription>
          </DialogHeader>
          <div className="space-y-4 py-4">
            <div className="space-y-2">
              <Label>Organization Name</Label>
              <Input placeholder="e.g. Acme Corp" value={newOrgName} onChange={e => setNewOrgName(e.target.value)} />
            </div>
            <div className="space-y-2">
              <Label>Workspace Name</Label>
              <Input placeholder="e.g. Engineering" value={newWsName} onChange={e => setNewWsName(e.target.value)} />
            </div>
          </div>
          <DialogFooter>
            <Button variant="outline" onClick={() => setIsModalOpen(false)}>Cancel</Button>
            <Button onClick={handleCreate} disabled={!newOrgName || !newWsName || isCreating}>
              {isCreating ? <Loader2 className="w-4 h-4 animate-spin mr-2" /> : null}
              Create
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>
    </>
  );
}
