# =======================================================================
# app/handlers/distress.py (FIXED - Use Correct Method)
# =======================================================================
from sqlalchemy.orm import Session
from app.schemas import MessageRequest, MessageResponse
from app.services import distress_service, llm_service, prompt_engine_service
from app.handlers import database as db_handler
from llm_system.persona import GOLDEN_PERSONA_PROMPT
import uuid
import json

async def handle_distress_check(db: Session, request: MessageRequest) -> MessageResponse | None:
    level = await distress_service.check(message=request.message)

    reflection_id = uuid.UUID(request.reflection_id)
    if level == 1:
        db_handler.update_reflection_status(db, reflection_id, 2)
        db_handler.save_message(db, reflection_id, request.message, sender=0, stage_no=-1, is_distress=True)
        return MessageResponse(success=False, reflection_id=request.reflection_id, sarthi_message="For immediate support, please reach out to a crisis hotline.", data=[{"distress_level": "critical"}])
    
    if level == 2:
        # FIXED: Use the correct method
        prompt_response = await prompt_engine_service.process_dict_request({"stage_id": 22, "data": {}})
        prompt_text = prompt_response.get("prompt", "I understand you're going through a difficult time.")
        
        llm_response_str = await llm_service.chat_completion(system_prompt=prompt_text, user_message=request.message, persona=GOLDEN_PERSONA_PROMPT)
        try:
            intensity = json.loads(llm_response_str).get("intensity", "neutral")
            if intensity in ["high", "elevated"]:
                # FIXED: Use the correct method
                safety_response = await prompt_engine_service.process_dict_request({"stage_id": 23, "data": {}})
                safety_prompt_text = safety_response.get("prompt", "Your wellbeing is important. Please consider reaching out for support.")
                
                return MessageResponse(success=True, reflection_id=request.reflection_id, sarthi_message=safety_prompt_text)
        except (json.JSONDecodeError, TypeError): 
            pass
    
    return None