import sys
with open('backend/app/routers/runner.py', 'r') as f: content = f.read()

content = content.replace('f"You are an expert QA engineer', 'f"""You are an expert QA engineer')
content = content.replace('{run.error_message}\n"', '{run.error_message}\n"""')

with open('backend/app/routers/runner.py', 'w') as f: f.write(content)
