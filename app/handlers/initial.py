from sqlalchemy.orm import Session
from app.schemas import MessageRequest, MessageResponse
from app.handlers import database as db_handler
from app.services import prompt_engine_service, llm_service
from llm_system.persona import GOLDEN_PERSONA_PROMPT
from typing import Union, Tuple, Dict
import uuid
import json
import logging

from prompt_engine.models import PromptData

# Set up logger
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

async def update_database_with_system_message(db: Session, system_message: dict, reflection_id: uuid.UUID):
    reflection = db_handler.get_reflection_by_id(db, reflection_id)
    if not reflection: return

    logger.info(f"Updating database with system message: {system_message}")

    if recipient_name := system_message.get("recipient_name"):
        reflection.receiver_name = recipient_name
        logger.info(f"Set recipient_name to: {recipient_name}")
    
    if relationship := system_message.get("relationship"):
        reflection.receiver_relationship = relationship
        logger.info(f"Set relationship to: {relationship}")
    
    if emotions := system_message.get("emotions"):
        reflection.emotion = emotions
        logger.info(f"Set emotions to: {emotions}")
    
    # CORRECTED: At stage 1, the intent becomes the flow_type
    if intent := system_message.get("intent"):
        reflection.flow_type = intent
        logger.info(f"Set flow_type to: {intent} (from stage 1 INTELLIGENT_CONTEXT_EXTRACTION)")
    
    db.commit()

async def _base_process_and_respond(db: Session, current_stage: int, reflection_id: uuid.UUID, chat_id: uuid.UUID, request: MessageRequest = None) -> Tuple[str, dict]:
    logger.info(f"Processing stage {current_stage} for reflection {reflection_id}")
    
    data_for_prompt = await find_data(current_stage, db, reflection_id, chat_id)
    logger.info(f"Data for prompt: {data_for_prompt}")
    
    prompt_request_data = {"stage_id": current_stage, "data": data_for_prompt}
    prompt_result = await prompt_engine_service.process_dict_request(prompt_request_data)
    logger.info(f"Prompt result: prompt_type={prompt_result.get('prompt_type')}, has_prompt={bool(prompt_result.get('prompt'))}")

    final_sarthi_message = ""
    system_msg = {}

    if prompt_result['prompt_type'] == 0:
        # Static prompt
        final_sarthi_message = prompt_result['prompt']
        logger.info(f"Using static prompt: {final_sarthi_message[:100]}...")
    elif prompt_result['prompt_type'] == 1:
        # Dynamic prompt - needs LLM processing
        system_prompt = prompt_result['prompt']
        last_user_msg_obj = db_handler.get_last_user_message(db, reflection_id)
        last_user_msg = last_user_msg_obj.message if last_user_msg_obj else (request.message if request else "")
        
        logger.info(f"Making LLM call with system_prompt length: {len(system_prompt)}, user_message: '{last_user_msg}'")
        
        llm_request = {
            "prompt": system_prompt,
            "user_message": last_user_msg,
            "reflection_id": str(reflection_id)
        }
        
        try:
            llm_response_str = await llm_service.process_json_request(json.dumps(llm_request))
            logger.info(f"LLM response received: {llm_response_str}")
            
            llm_response = json.loads(llm_response_str)
            logger.info(f"Parsed LLM response keys: {list(llm_response.keys())}")
            
            user_response = llm_response.get("user_response", {})
            final_sarthi_message = user_response.get("message", "I'm not sure how to respond.")
            system_msg = llm_response.get("system_response", {})
            
            logger.info(f"Extracted message: '{final_sarthi_message}', system_msg keys: {list(system_msg.keys())}")
            
            if system_msg:
                await update_database_with_system_message(db, system_msg, reflection_id)
                
        except json.JSONDecodeError as e:
            logger.error(f"JSON decode error: {e}. Raw response: {llm_response_str}")
            final_sarthi_message = "There was an issue processing the response."
        except Exception as e:
            logger.error(f"LLM processing error: {e}")
            final_sarthi_message = "There was an issue processing the response."

    if request and request.message:
        db_handler.save_message(db, reflection_id, request.message, sender=0, stage_no=current_stage)

    # Handle NULL next_stage values
    next_stage = prompt_result.get('next_stage')
    if next_stage is None:
        # CORRECTED: For stage 1 (AWAITING_VENT), next stage should be 2 (AWAITING_EMOTION)
        if current_stage == 1:
            next_stage = 2  # AWAITING_EMOTION
        else:
            next_stage = current_stage + 1
        logger.warning(f"next_stage was None for stage {current_stage}, using {next_stage} as fallback")

    logger.info(f"Saving Sarthi message: '{final_sarthi_message}' with next_stage: {next_stage}")
    db_handler.save_message(db, reflection_id, final_sarthi_message, sender=1, stage_no=next_stage)
    db_handler.update_reflection_stage(db, reflection_id, next_stage)
    
    return final_sarthi_message, system_msg

async def process_and_respond(db: Session, current_stage: int, reflection_id: uuid.UUID, chat_id: uuid.UUID, request: MessageRequest = None) -> MessageResponse:
    sarthi_message, _ = await _base_process_and_respond(db, current_stage, reflection_id, chat_id, request)
    reflection = db_handler.get_reflection_by_id(db, reflection_id)
    
    # Ensure we always have valid stage values
    current_stage_safe = current_stage if current_stage is not None else 0
    next_stage_safe = reflection.current_stage if reflection and reflection.current_stage is not None else current_stage_safe + 1
    
    return MessageResponse(success=True, reflection_id=str(reflection_id), sarthi_message=sarthi_message, current_stage=current_stage_safe, next_stage=next_stage_safe)

async def handle_initial_flow(db: Session, request: MessageRequest, user_id: uuid.UUID, chat_id: uuid.UUID) -> MessageResponse:
    latest_reflection = db_handler.get_latest_reflection_by_chat_id(db, chat_id)
    if not latest_reflection or latest_reflection.is_delivered in [1, 2]:
        return await handle_create_new_reflection(db, chat_id)
    if latest_reflection.is_delivered == 2:
        return MessageResponse(success=False, reflection_id=str(latest_reflection.reflection_id), data=[{"message": "This reflection is locked."}])
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