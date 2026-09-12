"use client";

import { useWorkspace } from "@/app/providers";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select";
import { Users, Mail, Loader2, UserPlus, Shield } from "lucide-react";
import { useState } from "react";
import { toast } from "@/components/ui/use-toast";

export default function TeamPage() {
  const { activeWorkspaceId } = useWorkspace();
  const [email, setEmail] = useState("");
  const [role, setRole] = useState("EDITOR");
  const [isInviting, setIsInviting] = useState(false);

  const handleInvite = async () => {
    if (!email.trim()) return;
    setIsInviting(true);
    try {
      // In a real implementation, this would POST /api/workspaces/{id}/invite
      await new Promise(r => setTimeout(r, 1000));
      toast({ title: "Invitation Sent", description: `An invite was sent to ${email}` });
      setEmail("");
    } catch (e: any) {
      toast({ title: "Failed to invite", description: e.message, variant: "destructive" });
    } finally {
      setIsInviting(false);
    }
  };

  if (activeWorkspaceId === "personal") {
    return (
      <div className="space-y-6">
        <div>
          <h1 className="text-2xl font-semibold tracking-tight flex items-center gap-2">
            <Users className="w-6 h-6 text-primary" /> Team & Workspaces
          </h1>
          <p className="text-sm text-muted-foreground mt-1">
            Manage your team members and roles.
          </p>
        </div>
        <Card className="bg-[#161922] border-muted/10">
          <CardContent className="py-12 flex flex-col items-center justify-center text-center">
            <Users className="w-12 h-12 text-muted-foreground mb-4" />
            <h3 className="text-lg font-medium">You are in your Personal Workspace</h3>
            <p className="text-sm text-muted-foreground mt-2 max-w-sm">
              Team collaboration requires a dedicated Workspace. Use the dropdown in the sidebar to create one, then you can invite members.
            </p>
          </CardContent>
        </Card>
      </div>
    );
  }

  return (
    <div className="space-y-6">
      <div>
        <h1 className="text-2xl font-semibold tracking-tight flex items-center gap-2">
          <Users className="w-6 h-6 text-primary" /> Team & Workspaces
        </h1>
        <p className="text-sm text-muted-foreground mt-1">
          Manage your team members and roles for this workspace.
        </p>
      </div>

      <div className="grid gap-6 md:grid-cols-2">
        <Card className="bg-[#161922] border-muted/10">
          <CardHeader>
            <CardTitle className="text-base flex items-center gap-2">
              <UserPlus className="w-4 h-4 text-primary" /> Invite Member
            </CardTitle>
            <CardDescription>
              Invite a colleague to collaborate in this workspace.
            </CardDescription>
          </CardHeader>
          <CardContent className="space-y-4">
            <div className="space-y-2">
              <Label>Email Address</Label>
              <Input 
                type="email" 
                placeholder="colleague@acme.com" 
                value={email}
                onChange={e => setEmail(e.target.value)}
              />
            </div>
            <div className="space-y-2">
              <Label>Role</Label>
              <Select value={role} onValueChange={setRole}>
                <SelectTrigger>
                  <SelectValue />
                </SelectTrigger>
                <SelectContent>
                  <SelectItem value="ADMIN">Admin (Full access)</SelectItem>
                  <SelectItem value="EDITOR">Editor (Can run tests)</SelectItem>
                  <SelectItem value="VIEWER">Viewer (Read-only)</SelectItem>
                </SelectContent>
              </Select>
            </div>
            <Button className="w-full mt-2" onClick={handleInvite} disabled={!email || isInviting}>
              {isInviting ? <Loader2 className="w-4 h-4 animate-spin mr-2" /> : <Mail className="w-4 h-4 mr-2" />}
              Send Invitation
            </Button>
          </CardContent>
        </Card>

        <Card className="bg-[#161922] border-muted/10">
          <CardHeader>
            <CardTitle className="text-base flex items-center gap-2">
              <Shield className="w-4 h-4 text-emerald-500" /> Active Members
            </CardTitle>
            <CardDescription>
              People with access to this workspace.
            </CardDescription>
          </CardHeader>
          <CardContent>
            <div className="space-y-4">
              <div className="flex items-center justify-between p-3 rounded-md bg-accent/30 border border-muted/10">
                <div className="flex items-center gap-3">
                  <div className="w-8 h-8 rounded-full bg-primary/20 flex items-center justify-center text-primary font-medium text-xs">
                    ME
                  </div>
                  <div>
                    <div className="text-sm font-medium">You</div>
                    <div className="text-xs text-muted-foreground">Workspace Owner</div>
                  </div>
                </div>
                <div className="text-xs font-semibold text-emerald-500 bg-emerald-500/10 px-2 py-1 rounded">ADMIN</div>
              </div>
              <p className="text-xs text-muted-foreground text-center py-4">
                No other members yet. Invite someone to see them here.
              </p>
            </div>
          </CardContent>
        </Card>
      </div>
    </div>
  );
}
