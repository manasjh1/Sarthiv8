# =======================================================================
# app/main.py (Final Correction with Direct Token Auth)
# =======================================================================
from fastapi import FastAPI, Depends, HTTPException
from sqlalchemy.orm import Session
from app.orchestration import MessageOrchestrator
from app.schemas import MessageRequest, MessageResponse
import uuid
import logging
from app.database import get_db
from config import AppConfig
from app.services import prompt_engine_service, global_intent_classifier, llm_service
from app.auth.api import router as auth_router
from app.auth.utils import verify_token # <-- Import verify_token directly

logging.basicConfig(level=logging.INFO)

app = FastAPI()

# --- Startup and Shutdown Events ---
@app.on_event("startup")
async def startup_event():
    logging.info("Application startup: Initializing services...")
    await prompt_engine_service.initialize()
    logging.info("Services initialized.")

@app.on_event("shutdown")
async def shutdown_event():
    logging.info("Application shutdown: Closing service connections...")
    await prompt_engine_service.shutdown()
    await global_intent_classifier.shutdown()
    await llm_service.shutdown()
    logging.info("Service connections closed.")

# Include the authentication router
app.include_router(auth_router)

@app.post("/chat", response_model=MessageResponse)
async def chat_endpoint(
    request: MessageRequest, 
    db: Session = Depends(get_db), 
    token_data: dict = Depends(verify_token) # <-- Use verify_token dependency
):
    try:
        # The user_id and chat_id are now securely retrieved directly from the JWT token
        user_id = token_data["user_id"]
        chat_id = token_data["chat_id"]

    except (ValueError, KeyError, AttributeError) as e:
        raise HTTPException(status_code=400, detail=f"Invalid token data: {e}")

    orchestrator = MessageOrchestrator(db)
    try:
        return await orchestrator.process_message(request, user_id, chat_id)
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))