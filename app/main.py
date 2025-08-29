# app/main.py

import asyncio
import logging
from fastapi import FastAPI, Depends, HTTPException, APIRouter
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy.orm import Session
from app.orchestration import MessageOrchestrator
from app.schemas import MessageRequest, MessageResponse
from app.database import get_db, SessionLocal
from app.services import prompt_engine_service, global_intent_classifier, llm_service
from app.auth.utils import verify_token
from app.auth.storage import AuthStorage

# --- Import routers from their specific locations ---
from app.auth.api import router as auth_router
from app.endpoints import invite, user, reflection

logging.basicConfig(level=logging.INFO)

app = FastAPI(
    title="Sarthi V8 API",
    description="The backend service for Sarthi",
    version="8.0.2" # Version Bump
)

# Add CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["https://app.sarthi.me"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# --- Include all routers with their correct prefixes ---
# 1. The auth_router from app/auth/api.py already has its prefix defined.
app.include_router(auth_router)

# 2. The routers from the 'endpoints' directory.
app.include_router(invite.router)
app.include_router(user.router)
app.include_router(reflection.router)


@app.get("/health")
async def health_check():
    """Simple health check endpoint"""
    return {"status": "healthy", "message": "Sarthi backend is running"}

@app.post("/chat", response_model=MessageResponse)
async def chat_endpoint(
    request: MessageRequest,
    db: Session = Depends(get_db),
    token_data: dict = Depends(verify_token)
):
    """Main chat endpoint that processes messages."""
    user_id = token_data["user_id"]
    chat_id = token_data["chat_id"]
    
    orchestrator = MessageOrchestrator(db)
    try:
        return await orchestrator.process_message(request, user_id, chat_id)
    except Exception as e:
        logging.error(f"Orchestrator error: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))


# --- Startup and Shutdown Events ---

cleanup_task = None

async def cleanup_expired_otps():
    """Background task to clean up expired OTP tokens every 5 minutes."""
    auth_storage = AuthStorage()
    
    while True:
        try:
            db = SessionLocal()
            try:
                cleaned_count = auth_storage.cleanup_expired_otps(db)
                if cleaned_count > 0:
                    logging.info(f"Cleaned up {cleaned_count} expired OTP records")
            finally:
                db.close()
                
        except Exception as e:
            logging.error(f"Error during OTP cleanup: {str(e)}", exc_info=True)
        
        await asyncio.sleep(300)

@app.on_event("startup")
async def startup_event():
    global cleanup_task
    logging.info("Application startup: Initializing services...")
    try:
        await prompt_engine_service.initialize()
        cleanup_task = asyncio.create_task(cleanup_expired_otps())
        logging.info("All services initialized successfully!")
    except Exception as e:
        logging.error(f"Failed to initialize services: {str(e)}", exc_info=True)
        raise

@app.on_event("shutdown")
async def shutdown_event():
    global cleanup_task
    logging.info("Application shutdown: Closing service connections...")
    try:
        if cleanup_task and not cleanup_task.done():
            cleanup_task.cancel()
            try:
                await cleanup_task
            except asyncio.CancelledError:
                logging.info("Background cleanup task cancelled")
        
        await prompt_engine_service.shutdown()
        await global_intent_classifier.shutdown()
        await llm_service.shutdown()
        logging.info("All service connections closed successfully!")
    except Exception as e:
        logging.error(f"Error during shutdown: {str(e)}", exc_info=True)