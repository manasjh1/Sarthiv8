from app.schemas import MessageRequest, MessageResponse
from app.handlers import database as db_handler
from app.handlers.initial import process_and_respond, _base_process_and_respond
from app.services import prompt_engine_service, delivery_service
import uuid
from sqlalchemy.orm import Session

def _get_first_playbook_stage(flow_type: str) -> int:
    """Helper function to determine the starting stage of a playbook."""
    if flow_type == 'feedback_sbi': return 6
    if flow_type == 'apology_4a': return 9
    if flow_type == 'gratitude_aif': return 13
    return 2 # Default to AWAITING_EMOTION

async def handle_normal_flow(db: Session, request: MessageRequest, chat_id: uuid.UUID) -> MessageResponse:
    reflection_id = uuid.UUID(request.reflection_id)
    reflection = db_handler.get_reflection_by_id(db, reflection_id)
    if not reflection:
        return MessageResponse(success=False, sarthi_message="Reflection not found.")
    
    current_stage = reflection.current_stage

    # --- Universal Pre-Playbook Flow ---
    if current_stage == 2: # AWAITING_EMOTION
        return await process_and_respond(db, 2, reflection_id, chat_id, request)

    if current_stage == 3: # EMOTION_VALIDATION (Two-Part, Part 1)
        llm_validation_message, _ = await _base_process_and_respond(db, 3, reflection_id, chat_id, request)
        db_handler.update_reflection_stage(db, reflection_id, 4)
        prompt_for_stage_4 = await prompt_engine_service.get_prompt_by_stage(stage_id=4)
        final_user_message = f"{llm_validation_message}\n\n{prompt_for_stage_4.prompt}"
        db_handler.save_message(db, reflection_id, final_user_message, sender=1, stage_no=4)
        return MessageResponse(success=True, reflection_id=str(reflection_id), sarthi_message=final_user_message, current_stage=3, next_stage=4)

    if current_stage == 5: # NAME_VALIDATION
        sarthi_message, system_msg = await _base_process_and_respond(db, 5, reflection_id, chat_id, request)
        if system_msg.get("is_valid_name") == "yes":
            db_handler.update_reflection_recipient(db, reflection_id, request.message)
            next_playbook_stage = _get_first_playbook_stage(reflection.flow_type)
            db_handler.update_reflection_stage(db, reflection_id, next_playbook_stage)
        return MessageResponse(success=True, reflection_id=str(reflection_id), sarthi_message=sarthi_message, current_stage=5, next_stage=reflection.current_stage)

    # --- Synthesis & Delivery Flow ---
    if current_stage == 16: # SYNTHESIZING (Two-Part, Part 1)
        synthesized_msg, _ = await _base_process_and_respond(db, 16, reflection_id, chat_id, request)
        db_handler.update_reflection_stage(db, reflection_id, 17)
        prompt_for_stage_17 = await prompt_engine_service.get_prompt_by_stage(stage_id=17)
        final_user_message = f"{synthesized_msg}\n\n{prompt_for_stage_17.prompt}"
        db_handler.save_message(db, reflection_id, final_user_message, sender=1, stage_no=17)
        return MessageResponse(success=True, reflection_id=str(reflection_id), sarthi_message=final_user_message, current_stage=16, next_stage=17)

    if current_stage == 19: # AWAITING_PREAMBLE_DECISION
        response = await process_and_respond(db, 19, reflection_id, chat_id, request)
        await delivery_service.send_reflection(reflection_id)
        return response

    # --- Standard Playbook & Other Synthesis Steps ---
    if (6 <= current_stage <= 15) or (current_stage in [17, 18, 20]):
        return await process_and_respond(db, current_stage, reflection_id, chat_id, request)

    # Fallback for any unhandled state
    return MessageResponse(success=False, sarthi_message="I'm not sure what the next step is.")