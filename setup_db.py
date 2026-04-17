"""
PostgreSQL Database Setup Script
Creates database and user for MedGuide Platform
"""
import os
import sys

try:
    import psycopg2
    from psycopg2.extensions import ISOLATION_LEVEL_AUTOCOMMIT
except ImportError:
    print("Installing psycopg2-binary...")
    os.system("pip install psycopg2-binary")
    import psycopg2
    from psycopg2.extensions import ISOLATION_LEVEL_AUTOCOMMIT

# PostgreSQL connection details
PG_HOST = os.getenv("PG_HOST", "localhost")
PG_PORT = os.getenv("PG_PORT", "5432")
PG_USER = os.getenv("PG_USER", "postgres")
PG_PASSWORD = os.getenv("PG_PASSWORD", "sachin111@rathor")
DB_NAME = os.getenv("DB_NAME", "medguide")

def create_database():
    """Create PostgreSQL database if it doesn't exist."""
    try:
        # Connect to default postgres database
        conn = psycopg2.connect(
            host=PG_HOST,
            port=PG_PORT,
            user=PG_USER,
            password=PG_PASSWORD,
            dbname="postgres"
        )
        conn.set_isolation_level(ISOLATION_LEVEL_AUTOCOMMIT)
        cursor = conn.cursor()
        
        # Check if database exists
        cursor.execute("SELECT 1 FROM pg_database WHERE datname = %s", (DB_NAME,))
        exists = cursor.fetchone()
        
        if exists:
            print(f"Database '{DB_NAME}' already exists")
        else:
            cursor.execute(f'CREATE DATABASE {DB_NAME}')
            print(f"Database '{DB_NAME}' created successfully")
        
        cursor.close()
        conn.close()
        return True
        
    except psycopg2.Error as e:
        print(f"Error creating database: {e}")
        return False

def test_connection():
    """Test PostgreSQL connection."""
    try:
        conn = psycopg2.connect(
            host=PG_HOST,
            port=PG_PORT,
            user=PG_USER,
            password=PG_PASSWORD,
            dbname=DB_NAME
        )
        cursor = conn.cursor()
        cursor.execute("SELECT version();")
        version = cursor.fetchone()
        print(f"PostgreSQL Connection Successful!")
        print(f"Version: {version[0]}")
        cursor.close()
        conn.close()
        return True
    except Exception as e:
        print(f"Connection failed: {e}")
        return False

if __name__ == "__main__":
    print("=" * 50)
    print("MedGuide PostgreSQL Setup")
    print("=" * 50)
    print(f"Host: {PG_HOST}:{PG_PORT}")
    print(f"User: {PG_USER}")
    print(f"Database: {DB_NAME}")
    print("=" * 50)
    
    # Create database
    if create_database():
        # Test connection
        test_connection()
        print("\nSetup complete! You can now run: python main.py")
    else:
        print("\nSetup failed. Please check your PostgreSQL installation and credentials.")
        sys.exit(1)
