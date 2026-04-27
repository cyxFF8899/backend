from sqlalchemy import create_engine, text
from app.config import Settings

def add_admin_field():
    settings = Settings.from_env()
    engine = create_engine(settings.database_url)
    
    with engine.connect() as conn:
        print(f"Connecting to {settings.database_url}")
        
        try:
            result = conn.execute(text("DESCRIBE users"))
            columns = {col[0]: col for col in result.fetchall()}
            
            if 'is_admin' not in columns:
                print("Adding 'is_admin' column to users table...")
                conn.execute(text("ALTER TABLE users ADD COLUMN is_admin BOOLEAN DEFAULT FALSE AFTER is_active"))
                
                print("Setting user with ID 1 as admin for testing...")
                conn.execute(text("UPDATE users SET is_admin = TRUE WHERE id = 1"))
            
            conn.commit()
            print("Admin field migration completed successfully.")
            
        except Exception as e:
            print(f"Error during migration: {e}")
            conn.rollback()

if __name__ == "__main__":
    add_admin_field()
