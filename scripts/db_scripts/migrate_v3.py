from sqlalchemy import create_engine, text
from app.config import Settings
from app.models import Base

def migrate_new_tables():
    settings = Settings.from_env()
    engine = create_engine(settings.database_url)
    
    print(f"Connecting to {settings.database_url}")
    
    # Create all tables defined in models.py that don't exist yet
    Base.metadata.create_all(bind=engine)
    print("New tables (ExpertConsultation, Schedule) created successfully.")

if __name__ == "__main__":
    migrate_new_tables()
