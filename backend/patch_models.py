with open(r'C:\Users\aryan\Desktop\WEB3 PROJECTS\Leaka AI\backend\app\models.py', 'r') as f:
    content = f.read()

content = content.replace(
    'owner_id = Column(String(64), nullable=True, index=True)  # Supabase user UUID\n    suite_id = Column(Integer, ForeignKey("test_suites.id"), nullable=True)',
    'owner_id = Column(String(64), nullable=True, index=True)  # Supabase user UUID\n    workspace_id = Column(Integer, ForeignKey("workspaces.id"), nullable=True, index=True)\n    suite_id = Column(Integer, ForeignKey("test_suites.id"), nullable=True)'
)

content = content.replace(
    'owner_id = Column(String(64), nullable=True, index=True)  # Supabase user UUID\n    job_id = Column(String(64), unique=True, index=True, nullable=False)',
    'owner_id = Column(String(64), nullable=True, index=True)  # Supabase user UUID\n    workspace_id = Column(Integer, ForeignKey("workspaces.id"), nullable=True, index=True)\n    job_id = Column(String(64), unique=True, index=True, nullable=False)'
)

content = content.replace(
    'owner_id = Column(String(64), nullable=True, index=True)  # Supabase user UUID\n    name = Column(String(128), nullable=False)',
    'owner_id = Column(String(64), nullable=True, index=True)  # Supabase user UUID\n    workspace_id = Column(Integer, ForeignKey("workspaces.id"), nullable=True, index=True)\n    name = Column(String(128), nullable=False)'
)

with open(r'C:\Users\aryan\Desktop\WEB3 PROJECTS\Leaka AI\backend\app\models.py', 'w') as f:
    f.write(content)

print("Patched models.py")
