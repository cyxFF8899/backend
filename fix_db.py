from sqlalchemy import create_engine, text
from app.config import Settings

def migrate_database():
    settings = Settings.from_env()
    engine = create_engine(settings.database_url)
    
    with engine.connect() as conn:
        print(f"Connecting to {settings.database_url}")
        
        # Check current columns
        result = conn.execute(text("DESCRIBE chat_messages"))
        columns = {col[0]: col for col in result.fetchall()}
        
        print(f"Current columns: {list(columns.keys())}")
        
        try:
            # 1. Add 'role' if missing
            if 'role' not in columns:
                print("Adding 'role' column...")
                conn.execute(text("ALTER TABLE chat_messages ADD COLUMN role VARCHAR(20) AFTER user_id"))
            
            # 2. Add 'content' if missing
            if 'content' not in columns:
                print("Adding 'content' column...")
                conn.execute(text("ALTER TABLE chat_messages ADD COLUMN content TEXT AFTER role"))
                
                # If 'query' exists, maybe move data to content? 
                # But the new system stores user and assistant as separate rows.
                # For now, let's just make it compatible.
            
            # 3. Add 'created_at' if missing
            if 'created_at' not in columns:
                print("Adding 'created_at' column...")
                conn.execute(text("ALTER TABLE chat_messages ADD COLUMN created_at DATETIME DEFAULT CURRENT_TIMESTAMP AFTER content"))
                
                # If 'time' exists, copy it
                if 'time' in columns:
                    print("Copying 'time' to 'created_at'...")
                    conn.execute(text("UPDATE chat_messages SET created_at = time"))
            
            # 4. Remove old columns if they exist to avoid confusion (Optional, but helps match model)
            # for old_col in ['query', 'answer', 'time']:
            #     if old_col in columns:
            #         print(f"Removing old column '{old_col}'...")
            #         conn.execute(text(f"ALTER TABLE chat_messages DROP COLUMN {old_col}"))

            conn.commit()
            print("Migration completed successfully.")
            
        except Exception as e:
            print(f"Error during migration: {e}")
            conn.rollback()

if __name__ == "__main__":
    migrate_database()
