# app/orchestration.py (FIXED)
from sqlalchemy.orm import Session
from app.schemas import MessageRequest, MessageResponse
from app.handlers import initial, distress, global_intent, normal_flow
from app.handlers import database as db_handler
import uuid
import logging

class MessageOrchestrator:
    def __init__(self, db: Session):
        self.db = db
        self.logger = logging.getLogger(__name__)

    async def process_message(self, request: MessageRequest, user_id: uuid.UUID, chat_id: uuid.UUID) -> MessageResponse:
        try:
            # ADD THESE DEBUG LOGS:
            print(f"🚨 TEST: Orchestrator called with reflection_id: {request.reflection_id}")
            self.logger.info(f"🔍 ORCHESTRATOR: Processing request with reflection_id: {request.reflection_id}")
            self.logger.info(f"🔍 ORCHESTRATOR: Message: '{request.message}'")
            
            # FIXED: Handle initial flow properly
            if not request.reflection_id:
                self.logger.info(f"🔍 ORCHESTRATOR: No reflection_id - going to initial flow")
                return await initial.handle_initial_flow(self.db, request, user_id, chat_id)

            self.logger.info(f"🔍 ORCHESTRATOR: Has reflection_id - entering core flow")
            
            # FIXED: Add validation for reflection_id before processing
            try:
                uuid.UUID(request.reflection_id)  # Validate it's a proper UUID
            except (ValueError, TypeError):
                self.logger.error(f"Invalid reflection_id format: {request.reflection_id}")
                return MessageResponse(success=False, sarthi_message="Invalid reflection ID format.")
            
            # ADD THIS DEBUG - Check the reflection's current stage:
            reflection = db_handler.get_reflection_by_id(self.db, uuid.UUID(request.reflection_id))
            if reflection:
                self.logger.info(f"🔍 ORCHESTRATOR: Found reflection with current_stage: {reflection.current_stage}, flow_type: {reflection.flow_type}")
            else:
                self.logger.info(f"🔍 ORCHESTRATOR: No reflection found!")
            
            self.logger.info(f"🔍 ORCHESTRATOR: Checking distress...")
            if (distress_response := await distress.handle_distress_check(self.db, request)): 
                self.logger.info(f"🔍 ORCHESTRATOR: Distress detected - returning distress response")
                return distress_response
                
            self.logger.info(f"🔍 ORCHESTRATOR: Checking global intent...")
            if (intent_response := await global_intent.handle_global_intent_check(self.db, request, chat_id)): 
                self.logger.info(f"🔍 ORCHESTRATOR: Global intent detected - returning intent response")
                return intent_response
            
            # Triage for Venting Flow
            if reflection and reflection.flow_type == 'venting':
                self.logger.info(f"🔍 ORCHESTRATOR: Venting flow detected - going to venting sanctuary")
                return await global_intent.handle_venting_sanctuary(self.db, request, chat_id)
            
            self.logger.info(f"🔍 ORCHESTRATOR: Going to normal flow")
            return await normal_flow.handle_normal_flow(self.db, request, chat_id)

        except Exception as e:
            self.logger.error(f"Orchestration error for user {user_id}: {str(e)}", exc_info=True)
            return MessageResponse(success=False, sarthi_message="An unexpected error occurred.", data=[{"error": str(e)}])