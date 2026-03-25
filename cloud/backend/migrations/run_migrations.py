"""
Run database migrations for IntelliOptics.

Usage:
    python -m migrations.run_migrations

Or from the backend directory:
    python migrations/run_migrations.py
"""
import os
import sys
from pathlib import Path

# Add parent directory to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent))

from sqlalchemy import text
from app.database import engine


def run_migrations():
    """Execute all SQL migration files in order."""
    migrations_dir = Path(__file__).parent
    sql_files = sorted(migrations_dir.glob("*.sql"))

    if not sql_files:
        print("No migration files found.")
        return

    with engine.connect() as conn:
        for sql_file in sql_files:
            print(f"Running migration: {sql_file.name}")
            try:
                sql_content = sql_file.read_text()
                # Split by semicolon and execute each statement
                statements = [s.strip() for s in sql_content.split(';') if s.strip() and not s.strip().startswith('--')]
                for statement in statements:
                    if statement:
                        conn.execute(text(statement))
                conn.commit()
                print(f"  ✓ {sql_file.name} completed")
            except Exception as e:
                print(f"  ✗ {sql_file.name} failed: {e}")
                # Continue with other migrations
                conn.rollback()

    print("\nMigrations complete.")


if __name__ == "__main__":
    run_migrations()
