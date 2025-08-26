# app/database.py
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker, declarative_base
from config import AppConfig

# Load config from the central config.py file
config = AppConfig.from_env()

# Create the SQLAlchemy engine
engine = create_engine(
    config.prompt_engine.supabase_connection_string,
    echo=False,
    pool_pre_ping=True,
    pool_recycle=300,
    connect_args={"sslmode": "require"},
    execution_options={"compiled_cache": None}
)

# Create a session factory
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

# Base class for your SQLAlchemy models
Base = declarative_base()

# Dependency function to get a DB session in your API endpoints
def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()