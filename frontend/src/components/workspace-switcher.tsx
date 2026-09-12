"use client";

import React, { useEffect, useState } from "react";
import { getWorkspaces, WorkspaceOut } from "@/lib/api";
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select";
import { useToast } from "@/components/ui/use-toast";

export function WorkspaceSwitcher() {
  const [workspaces, setWorkspaces] = useState<WorkspaceOut[]>([]);
  const [activeWorkspace, setActiveWorkspace] = useState<string>("personal");
  const { toast } = useToast();

  useEffect(() => {
    getWorkspaces()
      .then((data) => {
        setWorkspaces(data);
      })
      .catch((err) => {
        console.error("Failed to load workspaces", err);
      });
  }, []);

  const handleValueChange = (val: string) => {
    setActiveWorkspace(val);
    if (val !== "personal") {
      toast({
        title: "Workspace Switched",
        description: `You are now viewing ${workspaces.find(w => w.id.toString() === val)?.name}`,
      });
      // In a real app, we would update global context/URL here
    }
  };

  return (
    <div className="px-6 pb-2 mt-2">
      <div className="text-[10px] font-semibold text-muted-foreground uppercase tracking-wider mb-1 px-1">
        Active Workspace
      </div>
      <Select value={activeWorkspace} onValueChange={handleValueChange}>
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
        </SelectContent>
      </Select>
    </div>
  );
}
