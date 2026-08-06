"use client";

import Link from "next/link";
import { useQuery } from "@tanstack/react-query";
import { api } from "@/lib/api";
import {
  Card,
  CardContent,
  CardDescription,
  CardHeader,
  CardTitle,
} from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Skeleton } from "@/components/ui/skeleton";
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from "@/components/ui/table";
import { formatDate, truncate } from "@/lib/utils";
import { Play, Plus, FileText } from "lucide-react";

export default function TestCasesPage() {
  const { data, isLoading } = useQuery({
    queryKey: ["testcases-page"],
    queryFn: () => api.listTestCases({ limit: 200 }),
  });

  return (
    <div className="space-y-6">
      <div className="flex items-start justify-between flex-wrap gap-4">
        <div>
          <h1 className="text-2xl font-semibold tracking-tight">Test Cases</h1>
          <p className="text-sm text-muted-foreground mt-1">
            Reusable prompts you can run instantly or trigger from CI.
          </p>
        </div>
        <Button asChild>
          <Link href="/new">
            <Plus className="w-4 h-4 mr-2" />
            New case
          </Link>
        </Button>
      </div>

      <Card>
        <CardHeader>
          <CardTitle className="text-lg">All cases</CardTitle>
          <CardDescription>
            Cases are stored in Postgres. Run any case with one click.
          </CardDescription>
        </CardHeader>
        <CardContent>
          {isLoading ? (
            <div className="space-y-2">
              {Array.from({ length: 5 }).map((_, i) => (
                <Skeleton key={i} className="h-10 w-full" />
              ))}
            </div>
          ) : !data?.length ? (
            <div className="text-center py-10 space-y-3">
              <div className="w-12 h-12 rounded-full bg-muted mx-auto grid place-items-center">
                <FileText className="w-6 h-6 text-muted-foreground" />
              </div>
              <div className="font-medium">No cases saved yet</div>
              <p className="text-sm text-muted-foreground max-w-md mx-auto">
                Create a reusable test case from the Run a Test screen. Cases
                let you run the same prompt many times without retyping.
              </p>
              <Button asChild className="mt-2">
                <Link href="/new">Create a case</Link>
              </Button>
            </div>
          ) : (
            <Table>
              <TableHeader>
                <TableRow>
                  <TableHead>Name</TableHead>
                  <TableHead>Prompt</TableHead>
                  <TableHead>Target URL</TableHead>
                  <TableHead>Updated</TableHead>
                  <TableHead className="text-right">Run</TableHead>
                </TableRow>
              </TableHeader>
              <TableBody>
                {data.map((c) => (
                  <TableRow key={c.id}>
                    <TableCell className="font-medium">{c.name}</TableCell>
                    <TableCell className="text-sm text-muted-foreground max-w-md truncate">
                      {truncate(c.prompt, 100)}
                    </TableCell>
                    <TableCell className="text-sm text-muted-foreground max-w-[220px] truncate">
                      {c.target_url || "—"}
                    </TableCell>
                    <TableCell className="text-sm text-muted-foreground">
                      {formatDate(c.updated_at)}
                    </TableCell>
                    <TableCell className="text-right">
                      <Button
                        asChild
                        size="sm"
                        onClick={async (e) => {
                          e.preventDefault();
                          const r = await api.enqueueRun({
                            name: c.name,
                            prompt: c.prompt,
                            target_url: c.target_url,
                            success_criteria: c.success_criteria,
                            test_case_id: c.id,
                            use_vision: true,
                            max_steps: 100,
                          });
                          window.location.href = `/runs/${r.job_id}`;
                        }}
                      >
                        <a href="#">
                          <Play className="w-3 h-3 mr-1" />
                          Run
                        </a>
                      </Button>
                    </TableCell>
                  </TableRow>
                ))}
              </TableBody>
            </Table>
          )}
        </CardContent>
      </Card>
    </div>
  );
}
