# =======================================================================
# app/handlers/initial.py (Complete Proper Logic Implementation)
# =======================================================================
from sqlalchemy.orm import Session
from app.schemas import MessageRequest, MessageResponse
from app.handlers import database as db_handler
from app.services import prompt_engine_service, llm_service
from llm_system.persona import GOLDEN_PERSONA_PROMPT
from typing import Union, Tuple, Dict
import uuid
import json
import logging

logger = logging.getLogger(__name__)

async def find_data(stage_no: int, db: Session, reflection_id: uuid.UUID, chat_id: uuid.UUID) -> dict:
    reflection = db_handler.get_reflection_by_id(db, reflection_id)
    if not reflection: return {}

    if stage_no == 0:
        user = db_handler.get_user_by_chat_id(db, chat_id)
        return {"user_name": user.name if user else "there"}
    elif stage_no == 3:
        return {"user_emotions": reflection.emotion or "the way you're feeling"}
    elif stage_no == 16:
        messages = db_handler.get_all_messages(db, reflection_id)
        context = "\n".join([f"{'User' if msg.sender == 0 else 'Sarthi'}: {msg.message}" for msg in messages])
        return {"full_conversation_context": context}
    elif stage_no in [18, 19]:
        return {"recipient_name": reflection.receiver_name or "them"}
    elif stage_no == 24:
        return {"emotions": reflection.emotion or "this feeling"}
    return {}

async def update_database_with_system_message(db: Session, system_response: dict, reflection_id: uuid.UUID):
    """Updated to use system_response instead of system_message for consistency"""
    reflection = db_handler.get_reflection_by_id(db, reflection_id)
    if not reflection: return

    logger.info(f"Updating database with system_response: {system_response}")

    if recipient_name := system_response.get("recipient_name"):
        reflection.receiver_name = recipient_name
        logger.info(f"Set recipient_name to: {recipient_name}")
    
    if relationship := system_response.get("relationship"):
        reflection.receiver_relationship = relationship
        logger.info(f"Set relationship to: {relationship}")
    
    if emotions := system_response.get("emotions"):
        reflection.emotion = emotions
        logger.info(f"Set emotions to: {emotions}")
    
    if intent := system_response.get("intent"):
        reflection.flow_type = intent
        logger.info(f"Set flow_type to: {intent} (from stage {reflection.current_stage})")
    
    db.commit()

class LLMProcessingError(Exception):
    """Custom exception for LLM processing failures"""
    pass

async def _base_process_and_respond(db: Session, current_stage: int, reflection_id: uuid.UUID, chat_id: uuid.UUID, request: MessageRequest = None) -> Tuple[str, dict]:
    logger.info(f"Processing stage {current_stage} for reflection {reflection_id}")
    
    # Step 1: Get prompt configuration from prompt engine
    prompt_request_data = {"stage_id": current_stage, "data": {}}
    prompt_result = await prompt_engine_service.process_dict_request(prompt_request_data)
    
    # Extract configuration
    prompt_template = prompt_result['prompt']
    next_stage = prompt_result['next_stage']
    is_static = prompt_result['is_static']
    prompt_type = prompt_result['prompt_type']
    
    logger.info(f"Prompt config - type: {prompt_type}, static: {is_static}, next_stage: {next_stage}")
    
    final_sarthi_message = ""
    system_response = {}
    
    # Step 2: Process based on prompt_type and is_static conditions
    if prompt_type == 0:  # USER PROMPT
        logger.info("Processing USER PROMPT (prompt_type=0)")
        
        if is_static == 0:  # DYNAMIC USER PROMPT
            logger.info("Dynamic user prompt - calling find_data() and template processing")
            
            # Get dynamic data for this stage
            data_dict = await find_data(current_stage, db, reflection_id, chat_id)
            logger.info(f"Data for stage {current_stage}: {data_dict}")
            
            # Process template with dynamic data using prompt engine
            template_request_data = {"stage_id": current_stage, "data": data_dict}
            final_prompt_result = await prompt_engine_service.process_dict_request(template_request_data)
            final_sarthi_message = final_prompt_result['prompt']
            
            logger.info(f"Final dynamic user prompt: {final_sarthi_message}")
            
        else:  # STATIC USER PROMPT (is_static == 1)
            logger.info("Static user prompt - using prompt as-is")
            final_sarthi_message = prompt_template
            
    else:  # SYSTEM PROMPT (prompt_type == 1)
        logger.info("Processing SYSTEM PROMPT (prompt_type=1)")
        
        # Get current user message from request for LLM processing
        user_message = request.message if request and request.message else ""
        logger.info(f"Current user message for LLM: '{user_message}'")
        
        if is_static == 0:  # DYNAMIC SYSTEM PROMPT
            logger.info("Dynamic system prompt - calling find_data() and template processing")
            
            # Get dynamic data for this stage
            data_dict = await find_data(current_stage, db, reflection_id, chat_id)
            logger.info(f"Data for stage {current_stage}: {data_dict}")
            
            # Process template with dynamic data using prompt engine
            template_request_data = {"stage_id": current_stage, "data": data_dict}
            final_prompt_result = await prompt_engine_service.process_dict_request(template_request_data)
            final_system_prompt = final_prompt_result['prompt']
            
            logger.info(f"Final dynamic system prompt length: {len(final_system_prompt)}")
            
        else:  # STATIC SYSTEM PROMPT (is_static == 1)
            logger.info("Static system prompt - using prompt as-is")
            final_system_prompt = prompt_template
        
        # Call LLM service with system prompt and user message
        try:
            logger.info(f"Calling LLM service with system prompt and user message")
            
            llm_response_str = await llm_service.process_json_request(json.dumps({
                "prompt": final_system_prompt,
                "user_message": user_message,
                "reflection_id": str(reflection_id)
            }))
            
            llm_response = json.loads(llm_response_str)
            logger.info(f"LLM response received: {llm_response_str}")
            
            # Extract user_response and system_response
            user_response = llm_response.get("user_response", {})
            system_response = llm_response.get("system_response", {})
            
            # Handle user_response (may not always be present)
            if user_response and user_response.get("message"):
                user_message_text = user_response.get("message", "").strip()
                if user_message_text:
                    final_sarthi_message = user_message_text
                    logger.info(f"Extracted user message: '{final_sarthi_message}'")
                else:
                    logger.warning("User response message is empty")
                    final_sarthi_message = "I'm processing your message."
            else:
                logger.info("No user_response in LLM response - this is okay for some system prompts")
                final_sarthi_message = "Thank you for sharing that with me."
            
            # Process system_response if present (this is often the main purpose)
            if system_response:
                logger.info(f"Processing system_response: {system_response}")
                await update_database_with_system_message(db, system_response, reflection_id)
            else:
                logger.info("No system_response to process")
                
        except (json.JSONDecodeError, KeyError, ValueError, TypeError, LLMProcessingError) as e:
            logger.error(f"LLM processing failed for stage {current_stage}: {e}")
            raise LLMProcessingError(f"LLM processing failed: {str(e)}")
    
    # Step 3: Save user message to chat history if present
    if request and request.message:
        logger.info(f"Saving user message to chat history: '{request.message}'")
        db_handler.save_message(db, reflection_id, request.message, sender=0, stage_no=current_stage)

    # Step 4: Update current_stage ONLY if next_stage is not null
    if next_stage is not None:
        logger.info(f"Updating reflection current_stage from {current_stage} to {next_stage}")
        db_handler.update_reflection_stage(db, reflection_id, next_stage)
        
        # Save Sarthi response with new stage
        db_handler.save_message(db, reflection_id, final_sarthi_message, sender=1, stage_no=next_stage)
        logger.info(f"Saved Sarthi message: '{final_sarthi_message}' at stage {next_stage}")
    else:
        logger.warning(f"next_stage is null for stage {current_stage} - NOT updating reflection.current_stage")
        
        # Save Sarthi response at current stage (don't advance)
        db_handler.save_message(db, reflection_id, final_sarthi_message, sender=1, stage_no=current_stage)
        logger.info(f"Saved Sarthi message: '{final_sarthi_message}' at current stage {current_stage}")
    
    return final_sarthi_message, system_response

async def process_and_respond(db: Session, current_stage: int, reflection_id: uuid.UUID, chat_id: uuid.UUID, request: MessageRequest = None) -> MessageResponse:
    """Process stage with proper error handling"""
    try:
        sarthi_message, _ = await _base_process_and_respond(db, current_stage, reflection_id, chat_id, request)
        reflection = db_handler.get_reflection_by_id(db, reflection_id)
        
        return MessageResponse(
            success=True, 
            reflection_id=str(reflection_id), 
            sarthi_message=sarthi_message, 
            current_stage=current_stage, 
            next_stage=reflection.current_stage
        )
        
    except LLMProcessingError as e:
        logger.error(f"Stage {current_stage} processing failed: {e}")
        
        # Return error message but DON'T advance stage
        error_message = "I'm having some technical difficulties processing your message. Could you please try again?"
        
        # Save error message at current stage (don't advance)
        db_handler.save_message(db, reflection_id, error_message, sender=1, stage_no=current_stage)
        
        return MessageResponse(
            success=False, 
            reflection_id=str(reflection_id), 
            sarthi_message=error_message,
            current_stage=current_stage,
            next_stage=current_stage  # Stay at same stage for retry
        )

# Rest of the functions remain the same...
async def handle_initial_flow(db: Session, request: MessageRequest, user_id: uuid.UUID, chat_id: uuid.UUID) -> Union[MessageResponse, uuid.UUID]:
    latest_reflection = db_handler.get_latest_reflection_by_chat_id(db, chat_id)
    
    # Allow new reflection creation for completed (1) OR locked (2) reflections
    if not latest_reflection or latest_reflection.is_delivered in [1, 2]:
        return await handle_create_new_reflection(db, chat_id)
    
    # Only ask to continue for active/incomplete reflections (is_delivered = 0)
    return await handle_incomplete_reflection(db, request, latest_reflection, chat_id)

async def handle_incomplete_reflection(db: Session, request: MessageRequest, reflection, chat_id: uuid.UUID) -> MessageResponse:
    user_choice = request.data[0].get("choice") if request.data else None
    if user_choice == "1":
        return await process_and_respond(db, reflection.current_stage, reflection.reflection_id, chat_id, request)
    if user_choice == "0":
        return await handle_create_new_reflection(db, chat_id)
    return MessageResponse(success=True, reflection_id=str(reflection.reflection_id), sarthi_message="Welcome back! Continue?", data=[{"choice": "1", "label": "Yes"}, {"choice": "0", "label": "No"}])

async def handle_create_new_reflection(db: Session, chat_id: uuid.UUID) -> MessageResponse:
    reflection_id = db_handler.create_new_reflection(db, chat_id)
    return await process_and_respond(db, 0, reflection_id, chat_id)