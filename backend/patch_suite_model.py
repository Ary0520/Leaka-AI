import re

with open(r'C:\Users\aryan\Desktop\WEB3 PROJECTS\Leaka AI\backend\app\models.py', 'r') as f:
    content = f.read()

content = content.replace(
    'class TestSuite(Base):\n    __tablename__ = "test_suites"\n\n    id = Column(Integer, primary_key=True, index=True)\n    owner_id = Column(String(64), nullable=True, index=True)  # Supabase user UUID\n    name = Column(String(255), nullable=False)',
    'class TestSuite(Base):\n    __tablename__ = "test_suites"\n\n    id = Column(Integer, primary_key=True, index=True)\n    owner_id = Column(String(64), nullable=True, index=True)  # Supabase user UUID\n    workspace_id = Column(Integer, ForeignKey("workspaces.id"), nullable=True, index=True)\n    name = Column(String(255), nullable=False)'
)

with open(r'C:\Users\aryan\Desktop\WEB3 PROJECTS\Leaka AI\backend\app\models.py', 'w') as f:
    f.write(content)

print("Patched models.py TestSuite")
