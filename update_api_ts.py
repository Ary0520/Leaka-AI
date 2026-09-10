import sys

with open('frontend/src/lib/api.ts', 'r', encoding='utf-8') as f:
    content = f.read()

update_env_string = '''
  updateEnvironment: (appId: number, envId: number, body: Partial<EnvironmentCreate>) =>
    request<EnvironmentOut>(/api/applications//environments/, {
      method: "PUT",
      body: JSON.stringify(body),
    }),
'''

content = content.replace(
    '  listEnvironments: (appId: number) =>\n    request<EnvironmentOut[]>(/api/applications//environments),',
    '  listEnvironments: (appId: number) =>\n    request<EnvironmentOut[]>(/api/applications//environments),' + update_env_string
)

with open('frontend/src/lib/api.ts', 'w', encoding='utf-8') as f:
    f.write(content)
print('Updated api.ts')
