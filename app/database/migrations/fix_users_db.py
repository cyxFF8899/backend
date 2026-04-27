from sqlalchemy import create_engine, text
from app.config import Settings

def fix_user_table():
    settings = Settings.from_env()
    engine = create_engine(settings.database_url)
    
    with engine.connect() as conn:
        print(f"Connecting to {settings.database_url}")
        
        result = conn.execute(text("DESCRIBE users"))
        columns = {col[0]: col for col in result.fetchall()}
        
        print(f"Current columns in users: {list(columns.keys())}")
        
        try:
            if 'is_active' not in columns:
                print("Adding 'is_active' column to users table...")
                conn.execute(text("ALTER TABLE users ADD COLUMN is_active BOOLEAN DEFAULT TRUE AFTER hashed_password"))
            
            if 'email' not in columns:
                print("Adding 'email' column to users table...")
                conn.execute(text("ALTER TABLE users ADD COLUMN email VARCHAR(100) NULL AFTER username"))

            conn.commit()
            print("Users table migration completed successfully.")
            
        except Exception as e:
            print(f"Error during migration: {e}")
            conn.rollback()

if __name__ == "__main__":
    fix_user_table()
