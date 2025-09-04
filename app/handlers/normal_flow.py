from app.schemas import MessageRequest, MessageResponse
from app.handlers import database as db_handler
from app.handlers.initial import process_and_respond, _base_process_and_respond
from app.services import prompt_engine_service, delivery_service, llm_service
import uuid
import json
from sqlalchemy.orm import Session
import logging
from app.handlers.initial import process_and_respond, _base_process_and_respond, update_database_with_system_message

logger = logging.getLogger(__name__)

def _get_first_playbook_stage(flow_type: str) -> int:
    """Helper function to determine the starting stage of a playbook."""
    if flow_type == 'feedback_sbi': 
        return 6
    if flow_type == 'feedback':  # Add this line
        return 6
    if flow_type == 'apology_4a': 
        return 9
    if flow_type == 'apology':   # Add this line
        return 9
    if flow_type == 'gratitude_aif': 
        return 13
    if flow_type == 'gratitude': # Add this line
        return 13
    return 6  # Default to feedback playbook starting stage (not 2)

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
        print(f" NORMAL_FLOW: Entering Stage 1 for reflection {reflection_id}")
        logger.info(f"Processing Stage 1 completion check for reflection {reflection_id}")
        
        # Store user message first
        # if request.message and request.message.strip():
        #     print(f" NORMAL_FLOW: Storing user message: {request.message}")
        #     db_handler.save_message(db, reflection_id, request.message, sender=0, stage_no=current_stage)
        #     logger.info(f"✅ Stored user message for Stage 1: {request.message}")
        
        try:
            # Get prompt from prompt engine
            print(f" NORMAL_FLOW: Getting prompt from prompt engine...")
            prompt_request_data = {"stage_id": current_stage, "data": {}}
            prompt_result = await prompt_engine_service.process_dict_request(prompt_request_data)
            
            prompt_template = prompt_result['prompt']
            print(f" NORMAL_FLOW: Got prompt (length: {len(prompt_template)})")
            logger.info(f" Retrieved Stage 1 prompt (length: {len(prompt_template)})")
            logger.info(f" Prompt preview: {prompt_template[:200]}...")
            
            # Call LLM service with the new prompt
            print(f" NORMAL_FLOW: Calling LLM service...")
            llm_request = {
                "prompt": prompt_template,
                "user_message": request.message,
                "reflection_id": str(reflection_id)
            }
            
            logger.info(f" Calling LLM with request: {llm_request}")
            
            llm_response_str = await llm_service.process_json_request(json.dumps(llm_request))
            print(f" NORMAL_FLOW: Got LLM response (length: {len(llm_response_str)})")
            print(f" NORMAL_FLOW: LLM response: {llm_response_str}")
            logger.info(f" Raw LLM response: {llm_response_str}")
            
            try:
                llm_response = json.loads(llm_response_str)
                print(f" NORMAL_FLOW: Successfully parsed JSON")
                print(f" NORMAL_FLOW: Parsed response: {llm_response}")
            except json.JSONDecodeError as e:
                print(f" NORMAL_FLOW: JSON parsing failed: {e}")
                print(f" NORMAL_FLOW: Raw response: {llm_response_str}")
                logger.error(f"Failed to parse LLM response: {e}", exc_info=True)
                return MessageResponse(success=False, sarthi_message="Failed to process LLM response.")

            logger.info(f" Parsed LLM response: {llm_response}")
            
            # Extract system_response and user_response
            system_response = llm_response.get("system_response", {})
            user_response = llm_response.get("user_response", {})
            
            logger.info(f" System response: {system_response}")
            logger.info(f" User response: {user_response}")
            
            # Update database with system_response data
            if system_response:
                await update_database_with_system_message(db, system_response, reflection_id)
                logger.info(f" Updated database with system_response: {system_response}")
            
            # Get the intent from system_response
            intent = system_response.get("intent")
            logger.info(f" Extracted intent: '{intent}' (type: {type(intent)})")
            
            # CONDITION 1: Intent is NULL - Stay at Stage 1, show user_response
            if intent is None or intent == "null":
                logger.info(" Intent is NULL - staying at Stage 1, showing guidance message")
                
                # Get user guidance message
                guidance_message = user_response.get("message", "I'm listening. Could you share a bit more about what you'd like to express?")
                
                # Save Sarthi response at Stage 1 (don't advance stage)
                db_handler.save_message(db, reflection_id, guidance_message, sender=1, stage_no=current_stage)
                
                return MessageResponse(
                    success=True,
                    reflection_id=str(reflection_id),
                    sarthi_message=guidance_message,
                    current_stage=current_stage,  # Stay at Stage 1
                    next_stage=current_stage  # Stay at Stage 1
                )
            
            # CONDITION 2: Intent is VENTING - Go to venting sanctuary (Stage 24)
            elif intent == "venting":
                logger.info(" Intent is VENTING - going to venting sanctuary (Stage 24)")
                
                # Update flow_type and stage for venting
                db_handler.update_reflection_flow_type(db, reflection_id, "venting")
                db_handler.update_reflection_stage(db, reflection_id, 24)
                
                # Get empathetic message
                empathetic_message = user_response.get("message", "I hear you. This is a safe space to share what's on your mind.")
                
                # Save Sarthi response at Stage 24
                db_handler.save_message(db, reflection_id, empathetic_message, sender=1, stage_no=24)
                
                return MessageResponse(
                    success=True,
                    reflection_id=str(reflection_id),
                    sarthi_message=empathetic_message,
                    current_stage=24,  # Move to venting sanctuary
                    next_stage=24
                )
            
            # CONDITION 3: Intent is NOT NULL and NOT VENTING (feedback, apology, gratitude)
            else:
                logger.info(f" Valid intent detected: {intent} - proceeding to Stage 2")
                
                # Update to Stage 2 and process it
                db_handler.update_reflection_stage(db, reflection_id, 2)
                
                # Process Stage 2 immediately
                return await process_and_respond(db, 2, reflection_id, chat_id, request)
            
        except Exception as e:
            logger.error(f"Error in Stage 1 processing: {str(e)}", exc_info=True)
            
            # Fallback response for errors
            error_message = "I'm having some difficulty processing that. Could you tell me a bit more about what you'd like to share?"
            db_handler.save_message(db, reflection_id, error_message, sender=1, stage_no=current_stage)
            
            return MessageResponse(
                success=True,  # Don't fail the whole flow
                reflection_id=str(reflection_id),
                sarthi_message=error_message,
                current_stage=current_stage,  # Stay at Stage 1 for retry
                next_stage=current_stage
            )

    # --- Universal Pre-Playbook Flow ---
    if current_stage == 2:  # AWAITING_EMOTION
        logger.info(f"Processing Stage 2 (AWAITING_EMOTION) for reflection {reflection_id}")
        return await process_and_respond(db, 2, reflection_id, chat_id, request)

    if current_stage == 3:  # EMOTION_VALIDATION (Two-Part, Part 1)
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
            next_stage=next_stage_from_prompt_engine  # And telling the frontend to move to stage 5
        )

    # if current_stage == 4: # INTENTION_INQUIRY (Two-Part, Part 2)  
    #     logger.info(f"Processing Stage 4 (INTENTION_INQUIRY) for reflection {reflection_id}")
    #     return await process_and_respond(db, 4, reflection_id, chat_id, request)

    # FIXED Stage 5 Handler in app/handlers/normal_flow.py

    if current_stage == 5:  # NAME_VALIDATION
        print(f" STAGE5: Entering Stage 5 for reflection {reflection_id}")
        logger.info(f"Processing Stage 5 (NAME_VALIDATION) for reflection {reflection_id}")
        
        # Store user message first
        db_handler.save_message(db, reflection_id, request.message, sender=0, stage_no=current_stage)
        
        try:
            # Get prompt and call LLM manually (don't use _base_process_and_respond)
            prompt_request_data = {"stage_id": current_stage, "data": {}}
            prompt_result = await prompt_engine_service.process_dict_request(prompt_request_data)
            
            llm_request = {
                "prompt": prompt_result['prompt'],
                "user_message": request.message,
                "reflection_id": str(reflection_id)
            }
            
            llm_response_str = await llm_service.process_json_request(json.dumps(llm_request))
            llm_response = json.loads(llm_response_str)
            
            system_msg = llm_response.get("system_response", {})
            user_response = llm_response.get("user_response", {})
            sarthi_message = user_response.get("message", "Thank you for sharing that.")

            print(f" STAGE5: Got system_msg: {system_msg}")
            print(f" STAGE5: Got sarthi_message: {sarthi_message}")

            if system_msg.get("is_valid_name") == "yes":
                print(f" STAGE5: Name is VALID - advancing to playbook")
                # Valid name - save it and advance to playbook
                db_handler.update_reflection_recipient(db, reflection_id, request.message)
                
                current_reflection = db_handler.get_reflection_by_id(db, reflection_id)
                next_playbook_stage = _get_first_playbook_stage(current_reflection.flow_type)
                print(f" STAGE5: next_playbook_stage calculated as: {next_playbook_stage}")
                logger.info(f"Valid name confirmed. Moving to playbook stage {next_playbook_stage}")
                
                # *** FIX: Update stage and let process_and_respond handle it ***
                db_handler.update_reflection_stage(db, reflection_id, next_playbook_stage)
                
                # Let process_and_respond handle the playbook stage automatically
                return await process_and_respond(db, next_playbook_stage, reflection_id, chat_id, request)
                
            else:
                print(f" STAGE5: Name is INVALID - staying at Stage 5")
                # Invalid name - stay at Stage 5
                db_handler.save_message(db, reflection_id, sarthi_message, sender=1, stage_no=current_stage)
                
                return MessageResponse(
                    success=True, 
                    reflection_id=str(reflection_id), 
                    sarthi_message=sarthi_message, 
                    current_stage=5, 
                    next_stage=5
                )
        except Exception as e:
            logger.error(f"Error in Stage 5 processing: {str(e)}", exc_info=True)
            error_message = "I'm having some difficulty processing that. Could you please tell me the name again?"
            db_handler.save_message(db, reflection_id, error_message, sender=1, stage_no=current_stage)
            
            return MessageResponse(
                success=True,
                reflection_id=str(reflection_id),
                sarthi_message=error_message,
                current_stage=5,
                next_stage=5
            )

    # --- Synthesis & Delivery Flow ---
    if current_stage == 16:  # SYNTHESIZING (Two-Part, Part 1)
        logger.info(f"Processing Stage 16 (SYNTHESIZING) for reflection {reflection_id}")
        synthesized_msg, _ = await _base_process_and_respond(db, 16, reflection_id, chat_id, request)

        # Save the summary to the reflection table
        db_handler.update_reflection_summary(db, reflection_id, synthesized_msg)
        
        # db_handler.update_reflection_stage(db, reflection_id, 17)
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
            next_stage=next_stage_from_prompt_engine  # And telling the frontend to move to stage 18
        )
    
    if current_stage == 18:  # AWAITING_DELIVERY_TONE
        logger.info(f"Processing Stage 18 (AWAITING_DELIVERY_TONE) for reflection {reflection_id}")
        return await process_and_respond(db, 18, reflection_id, chat_id, request)

    if current_stage == 19:  # AWAITING_PREAMBLE_DECISION
        logger.info(f"Processing Stage 19 (AWAITING_PREAMBLE_DECISION) for reflection {reflection_id}")
        print(f" STAGE19: Entering delivery flow for reflection {reflection_id}")
        print(f" STAGE19: Request data: {request.data}")
        print(f" STAGE19: Request message: '{request.message}'")

        try:
            # Check if user provided input
            if request.data and len(request.data) > 0:
                user_choice = request.data[0]
                print(f" STAGE19: Processing user choice: {user_choice}")
                
                # Handle identity reveal choice
                if "reveal_name" in user_choice:
                    reveal_choice = user_choice.get("reveal_name")
                    provided_name = user_choice.get("name")
                    print(f" STAGE19: Identity choice - reveal: {reveal_choice}, name: {provided_name}")
                    result = await delivery_service.process_identity_choice(
                        reflection_id=reflection_id,
                        reveal_choice=reveal_choice,
                        provided_name=provided_name,
                        db=db
                    )
                
                # Handle name input (when user chose reveal but didn't provide name initially)
                elif "name" in user_choice:
                    print(f" STAGE19: Name input: {user_choice.get('name')}")
                    result = await delivery_service.process_identity_choice(
                        reflection_id=reflection_id,
                        reveal_choice=True,
                        provided_name=user_choice.get("name"),
                        db=db
                    )
                
                # Handle delivery mode choice
                elif "delivery_mode" in user_choice:
                    delivery_mode = user_choice.get("delivery_mode")
                    print(f" STAGE19: Delivery mode choice: {delivery_mode}")
                    
                    # Validate required contact info
                    if delivery_mode in [0, 2] and not user_choice.get("recipient_email"):
                        return MessageResponse(
                            success=False,
                            reflection_id=str(reflection_id),
                            sarthi_message="Email address is required for email delivery.",
                            current_stage=19,
                            next_stage=19
                        )
                    
                    if delivery_mode in [1, 2] and not user_choice.get("recipient_phone"):
                        return MessageResponse(
                            success=False,
                            reflection_id=str(reflection_id),
                            sarthi_message="Phone number is required for WhatsApp delivery.",
                            current_stage=19,
                            next_stage=19
                        )
                    
                    recipient_contact = {
                        "recipient_email": user_choice.get("recipient_email"),
                        "recipient_phone": user_choice.get("recipient_phone")
                    }
                    result = await delivery_service.process_delivery_choice(
                        reflection_id=reflection_id,
                        delivery_mode=delivery_mode,
                        recipient_contact=recipient_contact,
                        db=db
                    )
                
                # Handle third-party email
                elif "email" in user_choice:
                    print(f" STAGE19: Third-party email: {user_choice.get('email')}")
                    result = await delivery_service.process_third_party_email(
                        reflection_id=reflection_id,
                        third_party_email=user_choice.get("email"),
                        db=db
                    )
                
                else:
                    # No recognized choice, show initial options
                    print(f" STAGE19: Unrecognized choice, showing initial options")
                    result = await delivery_service.send_reflection(
                        reflection_id=reflection_id,
                        db=db
                    )
            
            else:
                # No user input, show initial options
                print(f" STAGE19: No user input, showing initial delivery options")
                result = await delivery_service.send_reflection(
                    reflection_id=reflection_id,
                    db=db
                )
            
            print(f" STAGE19: Delivery service result: {result}")
            
            return MessageResponse(
                success=result.get("success", True),
                reflection_id=result["reflection_id"],
                sarthi_message=result["sarthi_message"],
                current_stage=result.get("current_stage", 19),
                next_stage=result.get("next_stage", 19),
                data=result.get("data", [])
            )
            
        except Exception as e:
            logger.error(f"Delivery service failed: {str(e)}", exc_info=True)
            print(f" STAGE19: ERROR - {str(e)}")
            return MessageResponse(
                success=False,
                reflection_id=str(reflection_id),
                sarthi_message="Delivery failed. Please try again.",
                current_stage=19,
                next_stage=19
            )

    # Special handling for venting sanctuary stage
    if current_stage == 24:  # VENTING_SANCTUARY
        logger.info(f"Processing Stage 24 (VENTING_SANCTUARY) for reflection {reflection_id}")
        return await process_and_respond(db, 24, reflection_id, chat_id, request)

    # --- Standard Playbook & Other Synthesis Steps ---
    if (6 <= current_stage <= 15) or (current_stage in [17, 18, 20]):
        logger.info(f"Processing playbook/synthesis stage {current_stage} for reflection {reflection_id}")
        return await process_and_respond(db, current_stage, reflection_id, chat_id, request)

    # Fallback for any unhandled state
    logger.error(f"Unhandled stage {current_stage} for reflection {reflection_id}")
    return MessageResponse(success=False, sarthi_message="I'm not sure what the next step is.")