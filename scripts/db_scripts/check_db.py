from sqlalchemy import create_engine, text
from app.config import Settings

def check_db():
    settings = Settings.from_env()
    engine = create_engine(settings.database_url)
    
    with engine.connect() as conn:
        print(f"Connecting to {settings.database_url}")
        try:
            result = conn.execute(text("DESCRIBE chat_messages"))
            columns = result.fetchall()
            print("Columns in chat_messages:")
            for col in columns:
                print(col)
        except Exception as e:
            print(f"Error: {e}")

if __name__ == "__main__":
    check_db()
