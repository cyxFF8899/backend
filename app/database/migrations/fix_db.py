from sqlalchemy import create_engine, text
from app.config import Settings

def migrate_database():
    settings = Settings.from_env()
    engine = create_engine(settings.database_url)
    
    with engine.connect() as conn:
        print(f"Connecting to {settings.database_url}")
        
        result = conn.execute(text("DESCRIBE chat_messages"))
        columns = {col[0]: col for col in result.fetchall()}
        
        print(f"Current columns: {list(columns.keys())}")
        
        try:
            if 'role' not in columns:
                print("Adding 'role' column...")
                conn.execute(text("ALTER TABLE chat_messages ADD COLUMN role VARCHAR(20) AFTER user_id"))
            
            if 'content' not in columns:
                print("Adding 'content' column...")
                conn.execute(text("ALTER TABLE chat_messages ADD COLUMN content TEXT AFTER role"))
            
            if 'created_at' not in columns:
                print("Adding 'created_at' column...")
                conn.execute(text("ALTER TABLE chat_messages ADD COLUMN created_at DATETIME DEFAULT CURRENT_TIMESTAMP AFTER content"))
                
                if 'time' in columns:
                    print("Copying 'time' to 'created_at'...")
                    conn.execute(text("UPDATE chat_messages SET created_at = time"))

            conn.commit()
            print("Migration completed successfully.")
            
        except Exception as e:
            print(f"Error during migration: {e}")
            conn.rollback()

if __name__ == "__main__":
    migrate_database()
