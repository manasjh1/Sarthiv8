from app.schemas import MessageRequest, MessageResponse
from app.handlers import database as db_handler
from app.handlers.initial import process_and_respond, _base_process_and_respond
from app.services import prompt_engine_service, delivery_service
import uuid
from sqlalchemy.orm import Session
import logging

logger = logging.getLogger(__name__)

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
    logger.info(f"Processing normal flow for reflection {reflection_id}, current_stage: {current_stage}")

    # --- STAGE 1 COMPLETION CHECK (OUTSIDE MAIN LOOP) ---
    # Check if we just completed Stage 1 and need to route based on flow_type
    if current_stage == 1:
        updated_reflection = db_handler.get_reflection_by_id(db, reflection_id)
        if updated_reflection and updated_reflection.flow_type:
            flow_type = updated_reflection.flow_type
            logger.info(f"✅ Stage 1 completed - flow_type detected: {flow_type}")
            
            # Route based on flow_type without updating next_stage yet
            if flow_type == 'venting':
                logger.info("Flow type is venting - should be handled by venting sanctuary")
                return MessageResponse(success=False, sarthi_message="Venting flow should be handled separately.")
            else:
                logger.info(f"Flow type is {flow_type} - proceeding to Stage 2")
                # Now update to Stage 2 and process it
                db_handler.update_reflection_stage(db, reflection_id, 2)
                return await process_and_respond(db, 2, reflection_id, chat_id, request)
        else:
            logger.info(f"Processing Stage 1 (INTELLIGENT_CONTEXT_EXTRACTION) for reflection {reflection_id}")
            # Process Stage 1 to extract context information and set flow_type
            response = await process_and_respond(db, 1, reflection_id, chat_id, request)
            return response

    # --- Universal Pre-Playbook Flow ---
    if current_stage == 2: # AWAITING_EMOTION
        logger.info(f"Processing Stage 2 (AWAITING_EMOTION) for reflection {reflection_id}")
        return await process_and_respond(db, 2, reflection_id, chat_id, request)

    if current_stage == 3: # EMOTION_VALIDATION (Two-Part, Part 1)
        logger.info(f"Processing Stage 3 (EMOTION_VALIDATION) for reflection {reflection_id}")
        llm_validation_message, _ = await _base_process_and_respond(db, 3, reflection_id, chat_id, request)
        db_handler.update_reflection_stage(db, reflection_id, 4)
        prompt_for_stage_4 = await prompt_engine_service.get_prompt_by_stage(stage_id=4)
        final_user_message = f"{llm_validation_message}\n\n{prompt_for_stage_4.prompt}"
        db_handler.save_message(db, reflection_id, final_user_message, sender=1, stage_no=4)
         # **Crucially, update the reflection's stage to what comes AFTER stage 4**
        next_stage_from_prompt_engine = prompt_for_stage_4.next_stage
        db_handler.update_reflection_stage(db, reflection_id, next_stage_from_prompt_engine)
        
        return MessageResponse(
            success=True, 
            reflection_id=str(reflection_id), 
            sarthi_message=final_user_message, 
            current_stage=4,  # We are showing the result of stage 4
            next_stage=next_stage_from_prompt_engine # And telling the frontend to move to stage 5
        )

    # if current_stage == 4: # INTENTION_INQUIRY (Two-Part, Part 2)  
    #     logger.info(f"Processing Stage 4 (INTENTION_INQUIRY) for reflection {reflection_id}")
    #     return await process_and_respond(db, 4, reflection_id, chat_id, request)

    if current_stage == 5: # NAME_VALIDATION
        logger.info(f"Processing Stage 5 (NAME_VALIDATION) for reflection {reflection_id}")
        sarthi_message, system_msg = await _base_process_and_respond(db, 5, reflection_id, chat_id, request)
        if system_msg.get("is_valid_name") == "yes":
            db_handler.update_reflection_recipient(db, reflection_id, request.message)
            # Get the flow_type to determine which playbook to use
            current_reflection = db_handler.get_reflection_by_id(db, reflection_id)
            next_playbook_stage = _get_first_playbook_stage(current_reflection.flow_type)
            logger.info(f"Valid name confirmed. Moving to playbook stage {next_playbook_stage} for flow_type: {current_reflection.flow_type}")
            db_handler.update_reflection_stage(db, reflection_id, next_playbook_stage)
        return MessageResponse(success=True, reflection_id=str(reflection_id), sarthi_message=sarthi_message, current_stage=5, next_stage=reflection.current_stage)

    # --- Synthesis & Delivery Flow ---
    if current_stage == 16: # SYNTHESIZING (Two-Part, Part 1)
        logger.info(f"Processing Stage 16 (SYNTHESIZING) for reflection {reflection_id}")
        synthesized_msg, _ = await _base_process_and_respond(db, 16, reflection_id, chat_id, request)
        db_handler.update_reflection_stage(db, reflection_id, 17)
        prompt_for_stage_17 = await prompt_engine_service.get_prompt_by_stage(stage_id=17)
        final_user_message = f"{synthesized_msg}\n\n{prompt_for_stage_17.prompt}"
        db_handler.save_message(db, reflection_id, final_user_message, sender=1, stage_no=17)
        next_stage_from_prompt_engine = prompt_for_stage_17.next_stage
        db_handler.update_reflection_stage(db, reflection_id, next_stage_from_prompt_engine)
        
        return MessageResponse(
            success=True, 
            reflection_id=str(reflection_id), 
            sarthi_message=final_user_message, 
            current_stage=16,  # We are showing the result of stage 16
            next_stage=next_stage_from_prompt_engine # And telling the frontend to move to stage 18
        )
    
    if current_stage == 18: # AWAITING_DELIVERY_TONE
        logger.info(f"Processing Stage 18 (AWAITING_DELIVERY_TONE) for reflection {reflection_id}")
        return await process_and_respond(db, 18, reflection_id, chat_id, request)

    if current_stage == 19: # AWAITING_PREAMBLE_DECISION
        logger.info(f"Processing Stage 19 (AWAITING_PREAMBLE_DECISION) for reflection {reflection_id}")
        response = await process_and_respond(db, 19, reflection_id, chat_id, request)
        await delivery_service.send_reflection(reflection_id)
        return response

    # --- Standard Playbook & Other Synthesis Steps ---
    if (6 <= current_stage <= 15) or (current_stage in [17, 18, 20]):
        logger.info(f"Processing playbook/synthesis stage {current_stage} for reflection {reflection_id}")
        return await process_and_respond(db, current_stage, reflection_id, chat_id, request)

    # Fallback for any unhandled state
    logger.error(f"Unhandled stage {current_stage} for reflection {reflection_id}")
    return MessageResponse(success=False, sarthi_message="I'm not sure what the next step is.")