from sqlalchemy import create_engine, inspect
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker
import os

DATABASE_URL = os.getenv("DATABASE_URL", "postgresql://beacon_user:beacon_password@db:5432/beacon_telematics")

# PostgreSQL engine configuration
engine = create_engine(DATABASE_URL)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

Base = declarative_base()

def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()

def init_db():
    """Initialize database tables - skip if tables already exist (e.g., from backup restore)"""
    inspector = inspect(engine)
    existing_tables = inspector.get_table_names()
    
    # If tables already exist, database is already initialized
    if existing_tables:
        print(f"Database already initialized with {len(existing_tables)} tables. Skipping init_db().")
        return
    
    # Create tables only if database is empty
    Base.metadata.create_all(bind=engine)
