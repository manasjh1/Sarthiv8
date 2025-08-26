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
            # FIXED: Handle initial flow properly
            if not request.reflection_id:
                self.logger.info(f"Entering initial flow for user {user_id}")
                return await initial.handle_initial_flow(self.db, request, user_id, chat_id)

            self.logger.info(f"Entering core flow for reflection {request.reflection_id}")
            
            # FIXED: Add validation for reflection_id before processing
            try:
                uuid.UUID(request.reflection_id)  # Validate it's a proper UUID
            except (ValueError, TypeError):
                self.logger.error(f"Invalid reflection_id format: {request.reflection_id}")
                return MessageResponse(success=False, sarthi_message="Invalid reflection ID format.")
            
            if (distress_response := await distress.handle_distress_check(self.db, request)): return distress_response
            if (intent_response := await global_intent.handle_global_intent_check(self.db, request, chat_id)): return intent_response
            
            # Triage for Venting Flow
            reflection = db_handler.get_reflection_by_id(self.db, uuid.UUID(request.reflection_id))
            if reflection and reflection.flow_type == 'venting':
                return await global_intent.handle_venting_sanctuary(self.db, request, chat_id)
            
            return await normal_flow.handle_normal_flow(self.db, request, chat_id)

        except Exception as e:
            self.logger.error(f"Orchestration error for user {user_id}: {str(e)}", exc_info=True)
            return MessageResponse(success=False, sarthi_message="An unexpected error occurred.", data=[{"error": str(e)}])