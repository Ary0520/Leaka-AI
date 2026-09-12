"use client";

import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import React, { createContext, useContext, useEffect, useState } from "react";
import { createClient } from "@/lib/supabase/client";
import type { Session, User } from "@supabase/supabase-js";
import { setAuthToken } from "@/lib/api";

// ── Auth context ──────────────────────────────────────────────────────────────
interface AuthContextValue {
  user: User | null;
  session: Session | null;
  loading: boolean;
}

const AuthContext = createContext<AuthContextValue>({
  user: null,
  session: null,
  loading: true,
});

export function useAuth() {
  return useContext(AuthContext);
}

// ── Workspace context ─────────────────────────────────────────────────────────
interface WorkspaceContextValue {
  activeWorkspaceId: string;
  setActiveWorkspaceId: (id: string) => void;
}

const WorkspaceContext = createContext<WorkspaceContextValue>({
  activeWorkspaceId: "personal",
  setActiveWorkspaceId: () => {},
});

export function useWorkspace() {
  return useContext(WorkspaceContext);
}

// ── Providers ─────────────────────────────────────────────────────────────────
export function ReactQueryProvider({ children }: { children: React.ReactNode }) {
  const [qc] = useState(
    () =>
      new QueryClient({
        defaultOptions: {
          queries: {
            staleTime: 1_000,
            refetchOnWindowFocus: false,
            retry: 1,
          },
        },
      }),
  );

  const [authState, setAuthState] = useState<AuthContextValue>({
    user: null,
    session: null,
    loading: true,
  });

  useEffect(() => {
    const supabase = createClient();

    // Get initial session
    supabase.auth.getSession().then(({ data: { session } }) => {
      setAuthState({ user: session?.user ?? null, session, loading: false });
      setAuthToken(session?.access_token ?? null);
    });

    // Listen for auth changes (login, logout, token refresh)
    const { data: { subscription } } = supabase.auth.onAuthStateChange(
      (_event, session) => {
        setAuthState({ user: session?.user ?? null, session, loading: false });
        setAuthToken(session?.access_token ?? null);
      },
    );

    return () => subscription.unsubscribe();
  }, []);

  const [activeWorkspaceId, setActiveWorkspaceIdState] = useState<string>("personal");

  useEffect(() => {
    const saved = localStorage.getItem("leaka_workspace_id");
    if (saved) {
      setActiveWorkspaceIdState(saved);
    }
  }, []);

  const setActiveWorkspaceId = (id: string) => {
    setActiveWorkspaceIdState(id);
    localStorage.setItem("leaka_workspace_id", id);
    // Note: To force React Query to refetch on workspace change, you'd ideally invalidate queries here.
    // For now, reloading the page ensures a clean state switch for the dashboard.
    // window.location.reload(); 
  };

  return (
    <AuthContext.Provider value={authState}>
      <WorkspaceContext.Provider value={{ activeWorkspaceId, setActiveWorkspaceId }}>
        <QueryClientProvider client={qc}>{children}</QueryClientProvider>
      </WorkspaceContext.Provider>
    </AuthContext.Provider>
  );
}
