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

# The onboarding_completed column is on the settings/profile table, not auth.users
# Let's find which table it should be on
cur.execute(
    "SELECT table_name, column_name FROM information_schema.columns "
    "WHERE column_name='onboarding_completed';"
)
results = cur.fetchall()
print('Tables with onboarding_completed:', results)

# Also check the leaka/revguard-specific tables (not auth.users)
cur.execute(
    "SELECT table_name FROM information_schema.tables "
    "WHERE table_schema='public' ORDER BY table_name;"
)
tables = [r[0] for r in cur.fetchall()]
print('Public schema tables:', tables)

cur.close()
conn.close()
