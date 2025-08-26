# =======================================================================
# app/handlers/global_intent.py (FIXED - Rename Intent Key)
# =======================================================================
from sqlalchemy.orm import Session
from app.schemas import MessageRequest, MessageResponse
from app.services import global_intent_classifier, prompt_engine_service, llm_service
from app.handlers import database as db_handler
from app.handlers.initial import update_database_with_system_message
from llm_system.persona import GOLDEN_PERSONA_PROMPT
import uuid
import json
from datetime import datetime, timedelta, timezone

async def handle_venting_sanctuary(db: Session, request: MessageRequest, chat_id: uuid.UUID) -> MessageResponse:
    reflection_id = uuid.UUID(request.reflection_id)
    current_stage = 24
    db_handler.save_message(db, reflection_id, request.message, sender=0, stage_no=current_stage)

    last_message = db_handler.get_last_user_message(db, reflection_id)
    is_inactive = False
    if last_message and last_message.created_at:
        last_message_time = last_message.created_at.replace(tzinfo=timezone.utc)
        if (datetime.now(timezone.utc) - last_message_time) > timedelta(minutes=3):
            is_inactive = True

    prompt_response = await prompt_engine_service.process_dict_request({"stage_id": current_stage, "data": {}})
    prompt_text = prompt_response.get("prompt", "I'm listening.")
    
    llm_response_str = await llm_service.chat_completion(system_prompt=prompt_text, user_message=request.message, persona=GOLDEN_PERSONA_PROMPT)
    
    try:
        llm_response = json.loads(llm_response_str)
        sarthi_response_msg = llm_response.get("user_msg", "I'm listening.")
        system_msg = llm_response.get("system_msg", {})
        is_done = system_msg.get("done", 0) == 1
    except (json.JSONDecodeError, TypeError):
        sarthi_response_msg = "Let's pause for a moment. I'm having a little trouble."
        is_done = False

    db_handler.save_message(db, reflection_id, sarthi_response_msg, sender=1, stage_no=current_stage)

    if is_done or is_inactive:
        off_ramp_stage = 25
        db_handler.update_reflection_stage(db, reflection_id, off_ramp_stage)
        
        off_ramp_response = await prompt_engine_service.process_dict_request({"stage_id": off_ramp_stage, "data": {}})
        off_ramp_prompt_text = off_ramp_response.get("prompt", "Would you like to continue?")
        
        return MessageResponse(success=True, reflection_id=str(reflection_id), sarthi_message=off_ramp_prompt_text, current_stage=off_ramp_stage, next_stage=off_ramp_response.get("next_stage"), data=[{"choice": "1", "label": "Yes"}, {"choice": "0", "label": "No"}])
    else:
        return MessageResponse(success=True, reflection_id=str(reflection_id), sarthi_message=sarthi_response_msg, current_stage=current_stage, next_stage=current_stage)

async def handle_global_intent_check(db: Session, request: MessageRequest, chat_id: uuid.UUID) -> MessageResponse | None:
    intent_result = await global_intent_classifier.classify_intent(
        reflection_id=request.reflection_id,
        user_message=request.message
    )
    
    # FIXED: Use a more specific key name to avoid collision with stage 4
    global_intent = intent_result.system_response.get("intent")  # This is the global intent (INTENT_STOP, etc.)
    reflection_id = uuid.UUID(request.reflection_id)

    if global_intent in ["INTENT_STOP", "INTENT_RESTART", "INTENT_CONFUSED"]:
        db_handler.update_reflection_stage(db, reflection_id, 26)
        user_choice = request.data[0].get("choice") if request.data else None
        if user_choice == "1":
            db_handler.update_reflection_flow_type(db, reflection_id, "venting")
            db_handler.update_reflection_stage(db, reflection_id, 24)
            return await handle_venting_sanctuary(db, request, chat_id)
        if user_choice == "2":
            db_handler.update_reflection_stage(db, reflection_id, 1)
            return None
        if user_choice == "3":
            db_handler.update_reflection_stage(db, reflection_id, db_handler.get_previous_stage(db, reflection_id, steps=2))
            return None
        
        prompt_response = await prompt_engine_service.process_dict_request({"stage_id": 26, "data": {}})
        prompt_text = prompt_response.get("prompt", "How would you like to proceed?")
        
        return MessageResponse(success=True, reflection_id=request.reflection_id, sarthi_message=prompt_text, current_stage=26, next_stage=26, data=[{"choice": "1", "label": "New feeling"}, {"choice": "2", "label": "Different approach"}, {"choice": "3", "label": "Go back"}])
    
    if global_intent == "INTENT_SKIP_TO_DRAFT":
        db_handler.update_reflection_stage(db, reflection_id, 16)
        return None
        
    return None