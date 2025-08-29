# COMPLETE FIXED VERSION - Replace your entire global_intent.py functions

import json
import logging
from datetime import datetime, timedelta, timezone
from sqlalchemy.orm import Session
from app.schemas import MessageRequest, MessageResponse
from app.services import global_intent_classifier, prompt_engine_service, llm_service
from app.handlers import database as db_handler
from app.handlers.initial import update_database_with_system_message
from llm_system.persona import GOLDEN_PERSONA_PROMPT
import uuid

logger = logging.getLogger(__name__)

async def handle_venting_sanctuary(db: Session, request: MessageRequest, chat_id: uuid.UUID) -> MessageResponse:
    """
    Handle venting sanctuary (stage 24) and venting off-ramp (stage 25)
    """
    reflection_id = uuid.UUID(request.reflection_id)
    
    # Get current reflection to check what stage we're actually in
    reflection = db_handler.get_reflection_by_id(db, reflection_id)
    actual_stage = reflection.current_stage if reflection else 24
    
    logger.info(f"🔍 Venting sanctuary - actual_stage: {actual_stage}")
    
    # ===== HANDLE VENTING OFF-RAMP (Stage 25) CHOICES =====
    if actual_stage == 25:
        user_choice = request.data[0].get("choice") if request.data else None
        logger.info(f"🔍 Venting off-ramp choice: {user_choice}")
        
        if user_choice == "1":  # YES - Continue (go back to context extraction)
            logger.info("🔍 Venting off-ramp: YES - going to stage 1 for new intent")
            db_handler.update_reflection_stage(db, reflection_id, 1)
            db_handler.save_message(db, reflection_id, request.message, sender=0, stage_no=1)
            
            # Return None to let normal flow handle stage 1
            return None
            
        elif user_choice == "0":  # NO - Exit to stage 20 (closing)
            logger.info("🔍 Venting off-ramp: NO - going to stage 20 (closing)")
            db_handler.update_reflection_stage(db, reflection_id, 20)
            db_handler.save_message(db, reflection_id, request.message, sender=0, stage_no=20)
            
            # Return None to let normal flow handle stage 20
            return None
        
        else:
            # No choice provided - show the venting off-ramp options
            try:
                off_ramp_response = await prompt_engine_service.process_dict_request({"stage_id": 25, "data": {}})
                off_ramp_prompt = off_ramp_response.get("prompt", "Would you like to continue or wrap up?")
            except Exception as e:
                logger.error(f"Failed to get stage 25 prompt: {e}")
                off_ramp_prompt = "Would you like to continue exploring your feelings or wrap up our session?"
            
            return MessageResponse(
                success=True, 
                reflection_id=str(reflection_id), 
                sarthi_message=off_ramp_prompt, 
                current_stage=25, 
                next_stage=25,
                data=[{"choice": "1", "label": "Yes, continue"}, {"choice": "0", "label": "No, wrap up"}]
            )
    
    # ===== HANDLE NORMAL VENTING (Stage 24) =====
    current_stage = 24
    
    # Save user message
    db_handler.save_message(db, reflection_id, request.message, sender=0, stage_no=current_stage)
    
    # Check for inactivity
    last_message = db_handler.get_last_user_message(db, reflection_id)
    is_inactive = False
    if last_message and last_message.created_at:
        last_message_time = last_message.created_at
        if not last_message_time.tzinfo:
            last_message_time = last_message_time.replace(tzinfo=timezone.utc)
        elif last_message_time.tzinfo != timezone.utc:
            last_message_time = last_message_time.astimezone(timezone.utc)
        
        time_diff = datetime.now(timezone.utc) - last_message_time
        is_inactive = time_diff > timedelta(minutes=3)

    # Get venting prompt from prompt engine
    try:
        prompt_response = await prompt_engine_service.process_dict_request({"stage_id": current_stage, "data": {}})
        prompt_text = prompt_response.get("prompt", "I'm listening.")
    except Exception as e:
        logger.error(f"Failed to get venting prompt: {e}")
        prompt_text = "I'm here to listen. Please share what's on your mind."
    
    # Call LLM service
    try:
        llm_request = {
            "prompt": prompt_text,
            "user_message": request.message,
            "reflection_id": str(reflection_id)
        }
        
        llm_response_str = await llm_service.process_json_request(json.dumps(llm_request))
        llm_response = json.loads(llm_response_str)
        
        user_response = llm_response.get("user_response", {})
        system_response = llm_response.get("system_response", {})
        
        sarthi_response_msg = user_response.get("message", "I'm listening.")
        is_done = system_response.get("done", 0) == 1
        
    except Exception as e:
        logger.error(f"Venting LLM error: {e}")
        sarthi_response_msg = "I'm listening. Please continue."
        is_done = False

    # Save Sarthi response
    db_handler.save_message(db, reflection_id, sarthi_response_msg, sender=1, stage_no=current_stage)

    # Check if we should move to venting off-ramp (stage 25)
    if is_done or is_inactive:
        off_ramp_stage = 25
        db_handler.update_reflection_stage(db, reflection_id, off_ramp_stage)
        
        logger.info(f"🔍 Moving to venting off-ramp (stage {off_ramp_stage})")
        
        try:
            off_ramp_response = await prompt_engine_service.process_dict_request({"stage_id": off_ramp_stage, "data": {}})
            off_ramp_prompt = off_ramp_response.get("prompt", "Would you like to continue or wrap up?")
        except Exception as e:
            logger.error(f"Failed to get off-ramp prompt: {e}")
            off_ramp_prompt = "Would you like to continue exploring your feelings or wrap up our session?"
        
        return MessageResponse(
            success=True, 
            reflection_id=str(reflection_id), 
            sarthi_message=off_ramp_prompt, 
            current_stage=off_ramp_stage, 
            next_stage=off_ramp_stage,
            data=[{"choice": "1", "label": "Yes, continue"}, {"choice": "0", "label": "No, wrap up"}]
        )
    else:
        # Continue venting
        return MessageResponse(
            success=True, 
            reflection_id=str(reflection_id), 
            sarthi_message=sarthi_response_msg, 
            current_stage=current_stage, 
            next_stage=current_stage
        )


async def handle_global_intent_check(db: Session, request: MessageRequest, chat_id: uuid.UUID) -> MessageResponse | None:
    """
    Handle global intent classification and choices
    """
    # Get current reflection to check stage
    reflection_id = uuid.UUID(request.reflection_id)
    reflection = db_handler.get_reflection_by_id(db, reflection_id)
    current_stage = reflection.current_stage if reflection else 0
    
    logger.info(f"🔍 Global intent check - current_stage: {current_stage}")
    
    # ===== HANDLE VENTING OFF-RAMP CHOICES (Stage 25) =====
    # If we're in stage 25 (venting off-ramp), let venting handler deal with it
    if current_stage == 25:
        logger.info("🔍 Stage 25 detected - routing to venting sanctuary")
        return await handle_venting_sanctuary(db, request, chat_id)
    
    # ===== HANDLE GLOBAL INTENT CHOICES (Stage 26) =====
    if current_stage == 26:
        user_choice = request.data[0].get("choice") if request.data else None
        logger.info(f"🔍 Global intent choice (stage 26): {user_choice}")
        
        if user_choice == "1":  # "Let's talk about this new feeling"
            logger.info("🔍 Choice 1: New feeling - going to venting")
            db_handler.update_reflection_flow_type(db, reflection_id, "venting")
            db_handler.update_reflection_stage(db, reflection_id, 24)
            return await handle_venting_sanctuary(db, request, chat_id)
            
        elif user_choice == "2":  # "Let's try a different approach"  
            logger.info("🔍 Choice 2: Different approach - going to stage 1")
            db_handler.update_reflection_stage(db, reflection_id, 1)
            # Return None to let normal flow handle stage 1 context extraction
            return None
            
        elif user_choice == "3":  # "Can we go back?"
            logger.info("🔍 Choice 3: Go back to previous stage")
            previous_stage = db_handler.get_previous_stage(db, reflection_id, steps=2)
            db_handler.update_reflection_stage(db, reflection_id, previous_stage)
            # Return None to let normal flow handle the previous stage
            return None
        
        else:
            # No choice provided - show stage 26 options
            try:
                prompt_response = await prompt_engine_service.process_dict_request({"stage_id": 26, "data": {}})
                prompt_text = prompt_response.get("prompt", "How would you like to proceed?")
            except Exception as e:
                logger.error(f"Failed to get stage 26 prompt: {e}")
                prompt_text = "How would you like to proceed?"
            
            return MessageResponse(
                success=True, 
                reflection_id=request.reflection_id, 
                sarthi_message=prompt_text, 
                current_stage=26, 
                next_stage=26, 
                data=[
                    {"choice": "1", "label": "Let's talk about this new feeling"}, 
                    {"choice": "2", "label": "Let's try a different approach"}, 
                    {"choice": "3", "label": "Can we go back?"}
                ]
            )
    
    # ===== RUN GLOBAL INTENT CLASSIFICATION =====
    try:
        intent_result = await global_intent_classifier.classify_intent(
            reflection_id=request.reflection_id,
            user_message=request.message
        )
        
        global_intent = intent_result.system_response.get("intent")
        logger.info(f"🔍 Global intent detected: {global_intent}")
        
    except Exception as e:
        logger.error(f"Global intent classification failed: {e}")
        return None  # Let normal flow handle it
    
    # ===== HANDLE STOP/RESTART/CONFUSED INTENTS =====
    if global_intent in ["INTENT_STOP", "INTENT_RESTART", "INTENT_CONFUSED"]:
        logger.info(f"🔍 Detected {global_intent} - moving to stage 26")
        
        # Update to stage 26 (global intent choice stage)
        db_handler.update_reflection_stage(db, reflection_id, 26)
        
        # Check if user already made a choice (this handles the choice)
        user_choice = request.data[0].get("choice") if request.data else None
        
        if user_choice == "1":  # "Let's talk about this new feeling"
            logger.info("🔍 Intent choice 1: New feeling - going to venting")
            db_handler.update_reflection_flow_type(db, reflection_id, "venting")
            db_handler.update_reflection_stage(db, reflection_id, 24)
            return await handle_venting_sanctuary(db, request, chat_id)
            
        elif user_choice == "2":  # "Let's try a different approach"
            logger.info("🔍 Intent choice 2: Different approach - going to stage 1") 
            db_handler.update_reflection_stage(db, reflection_id, 1)
            return None
            
        elif user_choice == "3":  # "Can we go back?"
            logger.info("🔍 Intent choice 3: Go back")
            previous_stage = db_handler.get_previous_stage(db, reflection_id, steps=2)
            db_handler.update_reflection_stage(db, reflection_id, previous_stage)
            return None
        
        else:
            # No choice provided - show the global intent options
            try:
                prompt_response = await prompt_engine_service.process_dict_request({"stage_id": 26, "data": {}})
                prompt_text = prompt_response.get("prompt", "How would you like to proceed?")
            except Exception as e:
                logger.error(f"Failed to get stage 26 prompt: {e}")
                prompt_text = "It seems like you want to change direction. How would you like to proceed?"
            
            return MessageResponse(
                success=True, 
                reflection_id=request.reflection_id, 
                sarthi_message=prompt_text, 
                current_stage=26, 
                next_stage=26, 
                data=[
                    {"choice": "1", "label": "Let's talk about this new feeling"}, 
                    {"choice": "2", "label": "Let's try a different approach"}, 
                    {"choice": "3", "label": "Can we go back?"}
                ]
            )
    
    # ===== HANDLE SKIP TO DRAFT =====
    if global_intent == "INTENT_SKIP_TO_DRAFT":
        logger.info("🔍 Skip to draft intent - going to stage 16")
        db_handler.update_reflection_stage(db, reflection_id, 16)
        return None  # Let normal flow handle stage 16
        
    # No global intent detected - let normal flow continue
    return None