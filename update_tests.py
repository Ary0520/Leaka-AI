import sys
with open('frontend/src/app/tests/page.tsx', 'r') as f: content = f.read()

# Add DropdownMenu imports if not exists
if 'DropdownMenu' not in content:
    content = content.replace('import { Button } from "@/components/ui/button";', 'import { Button } from "@/components/ui/button";\nimport { DropdownMenu, DropdownMenuContent, DropdownMenuItem, DropdownMenuTrigger } from "@/components/ui/dropdown-menu";\nimport { MoreHorizontal, ShieldAlert, ShieldCheck } from "lucide-react";')

# Add toggleQuarantine mutation
if 'toggleQuarantine' not in content:
    content = content.replace('const runMut = useMutation({', '''
  const queryClient = useQueryClient();
  const toggleMut = useMutation({
    mutationFn: (id: number) => api.toggleQuarantine(id),
    onSuccess: () => queryClient.invalidateQueries({ queryKey: ["cases"] }),
  });
  
  const runMut = useMutation({
''')

# Replace the TableCell containing the Run button to include the dropdown menu
new_cell = """
                    <TableCell className="text-right">
                      <div className="flex items-center justify-end gap-2">
                        <Button
                          size="sm"
                          disabled={runMut.isPending && runMut.variables?.id === c.id}
                          onClick={() => runMut.mutate(c)}
                        >
                          {runMut.isPending && runMut.variables?.id === c.id
                            ? <Loader2 className="w-3 h-3 mr-1 animate-spin" />
                            : <Play className="w-3 h-3 mr-1" />}
                          Run
                        </Button>
                        <DropdownMenu>
                          <DropdownMenuTrigger asChild>
                            <Button variant="ghost" size="icon" className="h-8 w-8">
                              <MoreHorizontal className="h-4 w-4" />
                            </Button>
                          </DropdownMenuTrigger>
                          <DropdownMenuContent align="end">
                            <DropdownMenuItem 
                              onClick={() => toggleMut.mutate(c.id)}
                              className={c.is_quarantined ? "text-success" : "text-destructive"}
                            >
                              {c.is_quarantined ? (
                                <><ShieldCheck className="h-4 w-4 mr-2" /> Unquarantine</>
                              ) : (
                                <><ShieldAlert className="h-4 w-4 mr-2" /> Quarantine</>
                              )}
                            </DropdownMenuItem>
                          </DropdownMenuContent>
                        </DropdownMenu>
                      </div>
                    </TableCell>
"""

import re
# Attempt to replace the exact block
content = re.sub(r'<TableCell className="text-right">.*?<Button[^>]*>.*?Run.*?<\/Button>\s*<\/TableCell>', new_cell.strip(), content, flags=re.DOTALL)

with open('frontend/src/app/tests/page.tsx', 'w') as f: f.write(content)
print("Updated tests/page.tsx!")
