import os
from dotenv import load_dotenv
load_dotenv('backend/.env')

import psycopg2
from urllib.parse import urlparse

db_url = os.getenv('DATABASE_URL')
u = urlparse(db_url)
conn = psycopg2.connect(
    host=u.hostname, port=u.port or 5432,
    dbname=u.path.lstrip('/'), user=u.username,
    password=u.password, sslmode='require'
)
cur = conn.cursor()

# Check exactly which columns already exist on all affected tables
for table in ['test_runs', 'test_cases', 'environments', 'user_settings']:
    cur.execute(
        "SELECT column_name FROM information_schema.columns "
        f"WHERE table_schema='public' AND table_name='{table}' ORDER BY ordinal_position;"
    )
    cols = [r[0] for r in cur.fetchall()]
    print(f'{table}: {cols}')

cur.close()
conn.close()
