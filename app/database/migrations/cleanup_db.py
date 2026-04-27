from sqlalchemy import create_engine, text
from app.config import Settings
from datetime import datetime

def cleanup_database_schema():
    settings = Settings.from_env()
    engine = create_engine(settings.database_url)
    
    with engine.connect() as conn:
        print(f"Connecting to {settings.database_url}")
        
        try:
            result = conn.execute(text("SELECT id, user_id, query, answer, time FROM chat_messages WHERE query IS NOT NULL"))
            old_rows = result.fetchall()
            
            if old_rows:
                print(f"Found {len(old_rows)} old turn-based records. Migrating...")
                for row in old_rows:
                    row_id, user_id, query, answer, time_val = row
                    conn.execute(text(
                        "INSERT INTO chat_messages (user_id, role, content, created_at) VALUES (:u, 'user', :c, :t)"
                    ), {"u": user_id, "c": query, "t": time_val or datetime.utcnow()})
                    
                    conn.execute(text(
                        "INSERT INTO chat_messages (user_id, role, content, created_at) VALUES (:u, 'assistant', :c, :t)"
                    ), {"u": user_id, "c": answer, "t": time_val or datetime.utcnow()})
                    
                    conn.execute(text("DELETE FROM chat_messages WHERE id = :id"), {"id": row_id})
                print("Data migration completed.")
            
            print("Dropping old columns: query, answer, time...")
            conn.execute(text("ALTER TABLE chat_messages DROP COLUMN query"))
            conn.execute(text("ALTER TABLE chat_messages DROP COLUMN answer"))
            conn.execute(text("ALTER TABLE chat_messages DROP COLUMN time"))
            
            conn.commit()
            print("Database schema cleanup successful.")
            
        except Exception as e:
            print(f"Error during cleanup: {e}")
            conn.rollback()

if __name__ == "__main__":
    cleanup_database_schema()
