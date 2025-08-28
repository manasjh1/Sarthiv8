import asyncio
import logging
from fastapi import FastAPI, Depends, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy.orm import Session
from app.orchestration import MessageOrchestrator
from app.schemas import MessageRequest, MessageResponse
from app.database import get_db, SessionLocal
from app.services import prompt_engine_service, global_intent_classifier, llm_service
from app.auth.api import router as auth_router
from app.auth.utils import verify_token
from app.auth.storage import AuthStorage

logging.basicConfig(level=logging.INFO)

app = FastAPI()

# Add CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=[              
        "https://app.sarthi.me"
    ],
    allow_credentials=True,
    allow_methods=["GET", "POST", "PUT", "DELETE", "OPTIONS"],
    allow_headers=["*"],
)

cleanup_task = None

async def cleanup_expired_otps():
    """Background task to clean up expired OTP tokens every 5 minutes."""
    auth_storage = AuthStorage()
    
    while True:
        try:
            logging.info("Starting OTP cleanup task...")
            
            db = SessionLocal()
            try:
                cleaned_count = auth_storage.cleanup_expired_otps(db)
                if cleaned_count > 0:
                    logging.info(f"Cleaned up {cleaned_count} expired OTP records")
                else:
                    logging.info("No expired OTPs to clean up")
            finally:
                db.close()
                
        except Exception as e:
            logging.error(f"Error during OTP cleanup: {str(e)}", exc_info=True)
        
        await asyncio.sleep(300)

@app.on_event("startup")
async def startup_event():
    """Initialize services and start background tasks."""
    global cleanup_task
    
    logging.info("Application startup: Initializing services...")
    
    try:
        await prompt_engine_service.initialize()
        logging.info("Prompt Engine Service initialized")
        
        cleanup_task = asyncio.create_task(cleanup_expired_otps())
        logging.info("Background cleanup task started")
        
        logging.info("All services initialized successfully!")
        
    except Exception as e:
        logging.error(f"Failed to initialize services: {str(e)}", exc_info=True)
        raise

@app.on_event("shutdown")
async def shutdown_event():
    """Shutdown services and cleanup background tasks."""
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
        logging.info("Prompt Engine Service shutdown")
        
        await global_intent_classifier.shutdown()
        logging.info("Global Intent Classifier shutdown")
        
        await llm_service.shutdown()
        logging.info("LLM Service shutdown")
        
        logging.info("All service connections closed successfully!")
        
    except Exception as e:
        logging.error(f"Error during shutdown: {str(e)}", exc_info=True)

# Include the authentication router
app.include_router(auth_router)

# Health check endpoint (useful for deployment)
@app.get("/health")
async def health_check():
    """Simple health check endpoint"""
    return {"status": "healthy", "message": "Sarthi backend is running"}

# Main chat endpoint
@app.post("/chat", response_model=MessageResponse)
async def chat_endpoint(
    request: MessageRequest, 
    db: Session = Depends(get_db), 
    token_data: dict = Depends(verify_token)
):
    """
    Main chat endpoint that processes messages through the orchestration layer.
    Requires authentication via JWT token.
    """
    try:
        # Extract user_id and chat_id from the verified JWT token
        user_id = token_data["user_id"]
        chat_id = token_data["chat_id"]
        
        logging.info(f"Chat request - User: {user_id}, Chat: {chat_id}, Reflection: {request.reflection_id}")

    except (ValueError, KeyError, AttributeError) as e:
        logging.error(f"Invalid token data: {e}")
        raise HTTPException(status_code=400, detail=f"Invalid token data: {e}")

    # Process the message through the orchestration layer
    orchestrator = MessageOrchestrator(db)
    try:
        logging.info(f"Processing message through orchestrator...")
        response = await orchestrator.process_message(request, user_id, chat_id)
        
        if response.success:
            logging.info(f"Message processed successfully - Reflection: {response.reflection_id}")
        else:
            logging.warning(f"Message processing had issues - Reflection: {response.reflection_id}")
        
        return response
        
    except Exception as e:
        logging.error(f"Orchestrator error: {str(e)}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))