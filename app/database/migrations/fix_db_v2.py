from sqlalchemy import create_engine, text
from app.config import Settings

def fix_db_final():
    settings = Settings.from_env()
    engine = create_engine(settings.database_url)
    
    with engine.connect() as conn:
        print(f"Connecting to {settings.database_url}")
        
        try:
            print("Allowing NULL for 'query' column...")
            conn.execute(text("ALTER TABLE chat_messages MODIFY COLUMN query TEXT NULL"))
            
            print("Allowing NULL for 'answer' column...")
            conn.execute(text("ALTER TABLE chat_messages MODIFY COLUMN answer TEXT NULL"))
            
            print("Allowing NULL for 'time' column...")
            conn.execute(text("ALTER TABLE chat_messages MODIFY COLUMN time DATETIME NULL"))

            conn.commit()
            print("Database fix completed successfully.")
            
        except Exception as e:
            print(f"Error during database fix: {e}")
            conn.rollback()

if __name__ == "__main__":
    fix_db_final()
