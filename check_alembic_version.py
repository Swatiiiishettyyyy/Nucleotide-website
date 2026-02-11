from database import engine
from sqlalchemy import text

with engine.connect() as conn:
    result = conn.execute(text('SELECT version_num FROM alembic_version'))
    row = result.fetchone()
    if row:
        print(f"Current database version: {row[0]}")
        print(f"Version length: {len(row[0])}")
    else:
        print("No version found in alembic_version table")
