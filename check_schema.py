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

# Check current columns in environments table to find missing auth columns
cur.execute(
    "SELECT column_name FROM information_schema.columns "
    "WHERE table_name='environments' ORDER BY ordinal_position;"
)
env_cols = [r[0] for r in cur.fetchall()]
print('environments columns:', env_cols)

# Check applications table too
cur.execute(
    "SELECT column_name FROM information_schema.columns "
    "WHERE table_name='applications' ORDER BY ordinal_position;"
)
app_cols = [r[0] for r in cur.fetchall()]
print('applications columns:', app_cols)

# Check users table for onboarding_completed
cur.execute(
    "SELECT column_name FROM information_schema.columns "
    "WHERE table_name='users' ORDER BY ordinal_position;"
)
user_cols = [r[0] for r in cur.fetchall()]
print('users columns:', user_cols)

cur.close()
conn.close()
