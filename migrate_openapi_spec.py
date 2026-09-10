import os
from dotenv import load_dotenv
load_dotenv('backend/.env')

import psycopg2
from urllib.parse import urlparse

db_url = os.getenv('DATABASE_URL')
print('Connecting to database...')

u = urlparse(db_url)
conn = psycopg2.connect(
    host=u.hostname,
    port=u.port or 5432,
    dbname=u.path.lstrip('/'),
    user=u.username,
    password=u.password,
    sslmode='require'
)
cur = conn.cursor()

# Check if column already exists
cur.execute(
    "SELECT column_name FROM information_schema.columns "
    "WHERE table_name='applications' AND column_name='openapi_spec';"
)
result = cur.fetchone()
if result:
    print('Column openapi_spec ALREADY EXISTS. No migration needed.')
else:
    print('Column does not exist. Running ALTER TABLE...')
    cur.execute('ALTER TABLE applications ADD COLUMN openapi_spec TEXT;')
    conn.commit()
    print('SUCCESS: Column openapi_spec added to applications table.')

cur.close()
conn.close()
