# =======================================================================
# app/main.py (Final Correction)
# =======================================================================
from fastapi import FastAPI, Depends, HTTPException
from sqlalchemy.orm import Session
from app.orchestration import MessageOrchestrator
from app.schemas import MessageRequest, MessageResponse
import uuid
import logging
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from config import AppConfig
# Import the services that need to be initialized or shut down
from app.services import prompt_engine_service, global_intent_classifier, llm_service

logging.basicConfig(level=logging.INFO)

config = AppConfig.from_env()
engine = create_engine(config.prompt_engine.supabase_connection_string)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

app = FastAPI()

# --- FIXED: Add Startup and Shutdown Events ---
@app.on_event("startup")
async def startup_event():
    """
    Initializes the necessary services when the application starts.
    """
    logging.info("Application startup: Initializing services...")
    await prompt_engine_service.initialize()
    logging.info("Services initialized.")

@app.on_event("shutdown")
async def shutdown_event():
    """
    Shuts down services gracefully when the application stops.
    """
    logging.info("Application shutdown: Closing service connections...")
    await prompt_engine_service.shutdown()
    await global_intent_classifier.shutdown()
    await llm_service.shutdown()
    logging.info("Service connections closed.")
# --- End of Fix ---

def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()

def get_current_user():
    return {"user_id": "a0eebc99-9c0b-4ef8-bb6d-6bb9bd380a11", "chat_id": "b1eebc99-9c0b-4ef8-bb6d-6bb9bd380a22"}

@app.post("/chat", response_model=MessageResponse)
async def chat_endpoint(request: MessageRequest, db: Session = Depends(get_db), current_user: dict = Depends(get_current_user)):
    try:
        user_id = uuid.UUID(current_user["user_id"])
        chat_id = uuid.UUID(current_user["chat_id"])
    except (ValueError, KeyError) as e:
        raise HTTPException(status_code=400, detail=f"Invalid user credentials in token: {e}")

    orchestrator = MessageOrchestrator(db)
    try:
        return await orchestrator.process_message(request, user_id, chat_id)
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))