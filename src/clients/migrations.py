import psycopg
from src.clients.checkpointer import get_connection

def run_migrations(database_url: str):
    """Ensure database schema is up-to-date."""
    print("Running database migrations...")
    conn = get_connection(database_url)
    try:
        with conn.cursor() as cur:
            cur.execute("""
            CREATE TABLE IF NOT EXISTS users (
                id SERIAL PRIMARY KEY,
                email VARCHAR(255) UNIQUE NOT NULL,
                password_hash VARCHAR(255) NOT NULL,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            );
            """)
        print("Migrations completed successfully.")
    except Exception as e:
        print(f"Migration error: {str(e)}")
        raise e
