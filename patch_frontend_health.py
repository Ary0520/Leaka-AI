import re

def patch_frontend(filepath):
    with open(filepath, 'r', encoding='utf-8') as f:
        content = f.read()

    # Find dashboardHealth
    old_health = "dashboardHealth: (limit = 14) =>"
    new_health = "dashboardHealth: (workspaceId?: string, limit = 14) =>"
    
    old_health_url = "request<Array<{"
    
    content = content.replace(old_health, new_health)
    
    # We need to change the URL string inside dashboardHealth.
    # It was: }>>(`/api/dashboard/health?limit=${limit}`),
    old_url = "}>>(`/api/dashboard/health?limit=${limit}`),"
    new_url = "}>>(workspaceId && workspaceId !== 'personal' ? `/api/dashboard/health?workspace_id=${workspaceId}&limit=${limit}` : `/api/dashboard/health?limit=${limit}`),"
    
    content = content.replace(old_url, new_url)

    with open(filepath, 'w', encoding='utf-8') as f:
        f.write(content)
    print("Patched frontend dashboardHealth API!")

if __name__ == "__main__":
    patch_frontend(r"C:\Users\aryan\Desktop\WEB3 PROJECTS\Leaka AI\frontend\src\lib\api.ts")
