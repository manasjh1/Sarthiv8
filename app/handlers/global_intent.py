# COMPLETE UPDATED global_intent.py - Replace entire file

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

async def _handle_stage_25(db: Session, request: MessageRequest, chat_id: uuid.UUID) -> MessageResponse:
    """Helper function to handle all logic for Stage 25 (Venting Stop/Continue)."""
    reflection_id = uuid.UUID(request.reflection_id)
    user_choice = request.data[0].get("choice") if request.data else None
    logger.info(f"Handling Stage 25 logic with user_choice: {user_choice}")

    # Store user choice with appropriate labels
    if request.data and len(request.data) > 0:
        choice_data = request.data[0].copy()
        if choice_data.get("choice") == "0":
            choice_data["label"] = "I want to quit for now"
        elif choice_data.get("choice") == "1":
            choice_data["label"] = "I want to continue"
        db_handler.save_user_choice_message(db, reflection_id, choice_data, 25)

    # Process the user's choice
    if user_choice == "0":  # "I want to quit for now"
        logger.info("User chose to quit - closing venting session")
        db_handler.update_reflection_status(db, reflection_id, 3)
        final_message = "Thank you for sharing with me today. Take care, and feel free to start a new conversation whenever you're ready."
        db_handler.save_message(db, reflection_id, final_message, sender=1, stage_no=25)
        return MessageResponse(
            success=True,
            reflection_id=str(reflection_id),
            sarthi_message=final_message,
            current_stage=None, next_stage=None, data=[{"session_closed": True}]
        )

    elif user_choice == "1":  # "I want to continue"
        logger.info("User chose to continue - moving to stage 26")
        db_handler.update_reflection_stage(db, reflection_id, 26)
        return await _handle_stage_26(db, request, chat_id)

    else:
        # If no choice is made, present the options for stage 25
        logger.info("No choice provided for Stage 25. Presenting options.")
        try:
            prompt_response = await prompt_engine_service.process_dict_request({"stage_id": 25, "data": {}})
            prompt_text = prompt_response.get("prompt", "Would you like to continue or take a break?")
        except Exception as e:
            logger.error(f"Failed to get prompt for stage 25: {e}")
            prompt_text = "I hear you'd like to pause. Would you like to continue exploring or take a break for now?"
        db_handler.save_message(db, reflection_id, prompt_text, sender=1, stage_no=25)
        return MessageResponse(
            success=True,
            reflection_id=str(reflection_id),
            sarthi_message=prompt_text,
            current_stage=25, next_stage=25,
            data=[
                {"choice": "1", "label": "I want to continue"},
                {"choice": "0", "label": "I want to quit for now"}
            ]
        )


async def _handle_stage_26(db: Session, request: MessageRequest, chat_id: uuid.UUID) -> MessageResponse:
    """Helper function to handle all logic for Stage 26 (Global Intent Choices)."""
    reflection_id = uuid.UUID(request.reflection_id)
    user_choice = request.data[0].get("choice") if request.data else None
    logger.info(f"Handling Stage 26 logic with user_choice: {user_choice}")

    # Store user choice with appropriate labels
    if request.data and len(request.data) > 0:
        choice_data = request.data[0].copy()
        if choice_data.get("choice") == "1":
            choice_data["label"] = "Let's talk about this new feeling"
        elif choice_data.get("choice") == "2":
            choice_data["label"] = "Let's try a different approach"
        elif choice_data.get("choice") == "3":
            choice_data["label"] = "Can we go back?"
        db_handler.save_user_choice_message(db, reflection_id, choice_data, 26)

    # Process the user's choice
    if user_choice == "1":
        logger.info("Choice 1: New feeling - transitioning to venting sanctuary")
        db_handler.update_reflection_flow_type(db, reflection_id, "venting")
        db_handler.update_reflection_stage(db, reflection_id, 24)
        return await handle_venting_sanctuary(db, request, chat_id)
    elif user_choice == "2":
        logger.info("Choice 2: Different approach - restarting flow at stage 1")
        db_handler.update_reflection_stage(db, reflection_id, 1)
        return None
    elif user_choice == "3":
        logger.info("Choice 3: Go back to the previous stage")
        previous_stage = db_handler.get_previous_stage(db, reflection_id, steps=2)
        db_handler.update_reflection_stage(db, reflection_id, previous_stage)
        return None
    else:
        # If no choice is made, present the options
        logger.info("No choice provided for Stage 26. Presenting options.")
        try:
            prompt_response = await prompt_engine_service.process_dict_request({"stage_id": 26, "data": {}})
            prompt_text = prompt_response.get("prompt", "How would you like to proceed?")
        except Exception as e:
            logger.error(f"Failed to get prompt for stage 26: {e}")
            prompt_text = "It seems like you want to change direction. How would you like to proceed?"
        db_handler.save_message(db, reflection_id, prompt_text, sender=1, stage_no=26)
        return MessageResponse(
            success=True, reflection_id=str(reflection_id), sarthi_message=prompt_text,
            current_stage=26, next_stage=26,
            data=[
                {"choice": "1", "label": "Let's talk about this new feeling"},
                {"choice": "2", "label": "Let's try a different approach"},
                {"choice": "3", "label": "Can we go back?"}
            ]
        )

async def handle_venting_sanctuary(db: Session, request: MessageRequest, chat_id: uuid.UUID) -> MessageResponse:
    """
    Handle venting sanctuary (stage 24) with system_response processing
    Now checks for intent transitions and automatically moves to normal flow
    """
    reflection_id = uuid.UUID(request.reflection_id)
    current_stage = 24
    
    logger.info(f"🏛️ Entering venting sanctuary for reflection {reflection_id}")
    
     # Store user text message first (if any)
    if request.message and request.message.strip():
        db_handler.save_message(db, reflection_id, request.message, sender=0, stage_no=current_stage)
        logger.info(f"✅ Stored venting message: {request.message}")
    
    # Store choice data (if any) - though venting usually doesn't have structured choices
    if request.data and len(request.data) > 0:
        choice_data = request.data[0]
        # Only store if it's a meaningful choice (not delivery-related)
        if not any(key in choice_data for key in ["delivery_mode", "reveal_name", "recipient_email", "recipient_phone"]):
            db_handler.save_user_choice_message(db, reflection_id, choice_data, current_stage)
            logger.info(f"✅ Stored venting choice: {choice_data}")
    
    
    # Get venting prompt from prompt engine
    try:
        prompt_response = await prompt_engine_service.process_dict_request({"stage_id": current_stage, "data": {}})
        prompt_text = prompt_response.get("prompt", "I'm listening.")
        logger.info(f"📝 Retrieved venting prompt for stage {current_stage}")
    except Exception as e:
        logger.error(f"Failed to get venting prompt: {e}")
        prompt_text = "I'm here to listen. Please share what's on your mind."
    
    # Call LLM service to get both user_response and system_response
    try:
        llm_request = {
            "prompt": prompt_text,
            "user_message": request.message,
            "reflection_id": str(reflection_id)
        }
        
        logger.info(f"🤖 Calling LLM service for venting analysis")
        llm_response_str = await llm_service.process_json_request(json.dumps(llm_request))
        llm_response = json.loads(llm_response_str)
        
        user_response = llm_response.get("user_response", {})
        system_response = llm_response.get("system_response", {})
        
        sarthi_response_msg = user_response.get("message", "I'm listening.")
        
        logger.info(f"💭 LLM Response received - User: '{sarthi_response_msg[:50]}...', System: {system_response}")
        
    except Exception as e:
        logger.error(f"Venting LLM error: {e}")
        sarthi_response_msg = "I'm listening. Please continue."
        system_response = {}

    # 🔄 NEW LOGIC: Process system_response and check for intent transition
    if system_response:
        logger.info(f"🔍 Processing system_response: {system_response}")
        
        # Update database with system_response data
        await update_database_with_system_message(db, system_response, reflection_id)
        logger.info(f"✅ Database updated with system_response")
        
        # Check if intent is not 'venting' and not null/empty
        intent = system_response.get("intent")
        logger.info(f"🎯 Detected intent: {intent}")
        
        if (intent is not None and 
            isinstance(intent, str) and 
            intent.strip() and 
            intent.strip().lower() != "venting"):
            logger.info(f"🚀 Intent transition detected! Moving from venting to normal flow")
            logger.info(f"   - Intent: {intent}")
            logger.info(f"   - Will redirect to stage 2 (AWAITING_EMOTION)")
            
            # Update reflection stage to 2 (AWAITING_EMOTION)
            db_handler.update_reflection_stage(db, reflection_id, 2)
            logger.info(f"✅ Updated reflection stage from {current_stage} to 2")

            # OPTIMIZED: Directly call normal flow instead of manual prompt handling
            from app.handlers import normal_flow
            return await normal_flow.handle_normal_flow(db, request, chat_id)
            
        else:
            logger.info(f"🏛️ Staying in venting sanctuary - intent is '{intent}' (continuing venting)")
    else:
        logger.info(f"📭 No system_response received - continuing normal venting flow")

    # 🏛️ NORMAL VENTING FLOW: Continue if no intent transition
    # Save normal Sarthi response for continued venting
    db_handler.save_message(db, reflection_id, sarthi_response_msg, sender=1, stage_no=current_stage)
    
    logger.info(f"🏛️ Continuing venting sanctuary - user actively sharing")
    return MessageResponse(
        success=True, 
        reflection_id=str(reflection_id), 
        sarthi_message=sarthi_response_msg, 
        current_stage=current_stage, 
        next_stage=current_stage,
        data=[{"venting_continues": True}]
    )


async def handle_global_intent_check(db: Session, request: MessageRequest, chat_id: uuid.UUID) -> MessageResponse | None:
    """
    Handle global intent classification and choices - UPDATED with INTENT_STOP_001
    """
    # Get current reflection to check stage
    reflection_id = uuid.UUID(request.reflection_id)
    reflection = db_handler.get_reflection_by_id(db, reflection_id)
    current_stage = reflection.current_stage if reflection else 0
    flow_type = reflection.flow_type if reflection else None
    
    logger.info(f"Global intent check - current_stage: {current_stage}")
    
    # ===== HANDLE VENTING STOP CHOICES (Stage 25) =====
    #    if current_stage == 25 and flow_type == "venting":

    if current_stage == 25:
        return await _handle_stage_25(db, request, chat_id)
    
    # ===== HANDLE GLOBAL INTENT CHOICES (Stage 26) =====
    if current_stage == 26:
        return await _handle_stage_26(db, request, chat_id)
    # If not in stages 25 or 26, proceed to classify global intent
    
    # ===== RUN GLOBAL INTENT CLASSIFICATION =====
    try:
        intent_result = await global_intent_classifier.classify_intent(
            reflection_id=request.reflection_id,
            user_message=request.message
        )
        
        global_intent = intent_result.system_response.get("intent")
        logger.info(f"Global intent detected: {global_intent}")
        
    except Exception as e:
        logger.error(f"Global intent classification failed: {e}")
        return None  # Let normal flow handle it
    
    # ===== HANDLE VENTING STOP INTENT (INTENT_STOP_001) =====
    if global_intent == "INTENT_STOP_001" and flow_type == "venting":
        logger.info("Detected INTENT_STOP_001 (venting stop) - moving to stage 25")
        
        # Update to stage 25 (venting stop stage)
        db_handler.update_reflection_stage(db, reflection_id, 25)
        
        return await _handle_stage_25(db, request, chat_id)

    
    # ===== HANDLE RESTART/CONFUSED INTENTS =====
    if global_intent in ["INTENT_RESTART", "INTENT_CONFUSED"]:
        logger.info(f"Detected {global_intent} - moving to stage 26")
        
        # Update to stage 26 (global intent choice stage)
        db_handler.update_reflection_stage(db, reflection_id, 26)
        
        return await _handle_stage_26(db, request, chat_id)
    
    # ===== HANDLE SKIP TO DRAFT =====
    if global_intent == "INTENT_SKIP_TO_DRAFT":
        logger.info("Skip to draft intent - going to stage 16")
        db_handler.update_reflection_stage(db, reflection_id, 16)
        return None  # Let normal flow handle stage 16
        
    # No global intent detected - let normal flow continue
    return None