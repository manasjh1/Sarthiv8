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
    if current_stage == 1:
        print(f"NORMAL_FLOW: Entering Stage 1 for reflection {reflection_id}")
        logger.info(f"Processing Stage 1 completion check for reflection {reflection_id}")
        
        if request.message and request.message.strip():
            print(f"NORMAL_FLOW: Storing user message: {request.message}")
            db_handler.save_message(db, reflection_id, request.message, sender=0, stage_no=current_stage)
            logger.info(f"Stored user message for Stage 1: {request.message}")
        
        try:
            print(f"NORMAL_FLOW: Getting prompt from prompt engine...")
            prompt_request_data = {"stage_id": current_stage, "data": {}}
            prompt_result = await prompt_engine_service.process_dict_request(prompt_request_data)
            
            prompt_template = prompt_result['prompt']
            print(f"NORMAL_FLOW: Got prompt (length: {len(prompt_template)})")
            logger.info(f"Retrieved Stage 1 prompt (length: {len(prompt_template)})")
            logger.info(f"Prompt preview: {prompt_template[:200]}...")
            
            print(f"NORMAL_FLOW: Calling LLM service...")
            llm_request = {
                "prompt": prompt_template,
                "user_message": request.message,
                "reflection_id": str(reflection_id)
            }
            
            logger.info(f"Calling LLM with request: {llm_request}")
            
            llm_response_str = await llm_service.process_json_request(json.dumps(llm_request))
            print(f"NORMAL_FLOW: Got LLM response (length: {len(llm_response_str)})")
            print(f"NORMAL_FLOW: LLM response: {llm_response_str}")
            logger.info(f"Raw LLM response: {llm_response_str}")
            
            try:
                llm_response = json.loads(llm_response_str)
                print(f"NORMAL_FLOW: Successfully parsed JSON")
                print(f"NORMAL_FLOW: Parsed response: {llm_response}")
            except json.JSONDecodeError as e:
                print(f"NORMAL_FLOW: JSON parsing failed: {e}")
                print(f"NORMAL_FLOW: Raw response: {llm_response_str}")
                logger.error(f"Failed to parse LLM response: {e}", exc_info=True)
                return MessageResponse(success=False, sarthi_message="Failed to process LLM response.")

            logger.info(f"Parsed LLM response: {llm_response}")
            
            system_response = llm_response.get("system_response", {})
            user_response = llm_response.get("user_response", {})
            
            logger.info(f"System response: {system_response}")
            logger.info(f"User response: {user_response}")
            
            if system_response:
                await update_database_with_system_message(db, system_response, reflection_id)
                logger.info(f"Updated database with system_response: {system_response}")
            
            intent = system_response.get("intent")
            logger.info(f"Extracted intent: '{intent}' (type: {type(intent)})")
            
            if intent is None or intent == "null":
                logger.info("Intent is NULL - staying at Stage 1, showing guidance message")
                
                guidance_message = user_response.get("message", "I'm listening. Could you share a bit more about what you'd like to express?")
                db_handler.save_message(db, reflection_id, guidance_message, sender=1, stage_no=current_stage)
                
                return MessageResponse(
                    success=True,
                    reflection_id=str(reflection_id),
                    sarthi_message=guidance_message,
                    current_stage=current_stage,
                    next_stage=current_stage
                )
            
            elif intent == "venting":
                logger.info("Intent is VENTING - going to venting sanctuary (Stage 24)")
                
                db_handler.update_reflection_flow_type(db, reflection_id, "venting")
                db_handler.update_reflection_stage(db, reflection_id, 24)
                
                empathetic_message = user_response.get("message", "I hear you. This is a safe space to share what's on your mind.")
                db_handler.save_message(db, reflection_id, empathetic_message, sender=1, stage_no=24)
                
                return MessageResponse(
                    success=True,
                    reflection_id=str(reflection_id),
                    sarthi_message=empathetic_message,
                    current_stage=24,
                    next_stage=24
                )
            
            else:
                logger.info(f"Valid intent detected: {intent} - proceeding to Stage 2")
                
                db_handler.update_reflection_stage(db, reflection_id, 2)
                return await process_and_respond(db, 2, reflection_id, chat_id, request)
            
        except Exception as e:
            logger.error(f"Error in Stage 1 processing: {str(e)}", exc_info=True)
            
            error_message = "I'm having some difficulty processing that. Could you tell me a bit more about what you'd like to share?"
            db_handler.save_message(db, reflection_id, error_message, sender=1, stage_no=current_stage)
            
            return MessageResponse(
                success=True,
                reflection_id=str(reflection_id),
                sarthi_message=error_message,
                current_stage=current_stage,
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
        
        next_stage_from_prompt_engine = prompt_for_stage_4.next_stage
        db_handler.update_reflection_stage(db, reflection_id, next_stage_from_prompt_engine)
        
        return MessageResponse(
            success=True, 
            reflection_id=str(reflection_id), 
            sarthi_message=final_user_message, 
            current_stage=4,
            next_stage=next_stage_from_prompt_engine
        )

    if current_stage == 4: # INTENTION_INQUIRY (Two-Part, Part 2)  
        logger.info(f"Processing Stage 4 (INTENTION_INQUIRY) for reflection {reflection_id}")
        return await process_and_respond(db, 4, reflection_id, chat_id, request)

    if current_stage == 5:  # NAME_VALIDATION
        print(f"STAGE5: Entering Stage 5 for reflection {reflection_id}")
        logger.info(f"Processing Stage 5 (NAME_VALIDATION) for reflection {reflection_id}")
        
        db_handler.save_message(db, reflection_id, request.message, sender=0, stage_no=current_stage)
        
        try:
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
            
            print(f"STAGE5: Got system_msg: {system_msg}")
            print(f"STAGE5: Got sarthi_message: {sarthi_message}")
            
            print(f"STAGE5: Got system_msg: {system_msg}")
            print(f"STAGE5: Checking is_valid_name: {system_msg.get('is_valid_name')}")


            
            is_valid = system_msg.get("validNames") == "yes"
            
            if "names" in system_msg and system_msg["names"]:
                validated_name = system_msg["names"][0]
                print(f"STAGE5: Found MULTIPLE names: {system_msg['names']}, using: {validated_name}")
            elif "name" in system_msg and system_msg["name"]:
                validated_name = system_msg["name"]
                print(f"STAGE5: Found SINGLE name: {validated_name}")
            else:
                validated_name = request.message
                print(f"STAGE5: NO name found, using fallback: {validated_name}")
                
            print(f"STAGE5: Preliminary is_valid: {is_valid}, validated_name: {validated_name}")
            
            if validated_name:
                db_handler.update_reflection_recipient(db, reflection_id, validated_name)
                print(f"STAGE5: Updated recipient name in DB: {validated_name}")
                
                updated_reflection = db_handler.get_reflection_by_id(db, reflection_id)
                print(f"STAGE5: AFTER update - receiver_name: {updated_reflection.receiver_name}")
                
            current_reflection = db_handler.get_reflection_by_id(db, reflection_id)
            next_playbook_stage = _get_first_playbook_stage(current_reflection.flow_type)
            print(f"STAGE5: next_playbook_stage calculated as: {next_playbook_stage}")
            logger.info(f"Moving to playbook stage {next_playbook_stage}")
            
            db_handler.update_reflection_stage(db, reflection_id, next_playbook_stage)
            return await process_and_respond(db, next_playbook_stage, reflection_id, chat_id, request)
        
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

        db_handler.update_reflection_summary(db, reflection_id, synthesized_msg)
        
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
            current_stage=16,
            next_stage=next_stage_from_prompt_engine
        )
    
    if current_stage == 18:  # AWAITING_DELIVERY_TONE
        logger.info(f"Processing Stage 18 (AWAITING_DELIVERY_TONE) for reflection {reflection_id}")
        return await process_and_respond(db, 18, reflection_id, chat_id, request)

    if current_stage == 19:  # AWAITING_PREAMBLE_DECISION
        logger.info(f"Processing Stage 19 (AWAITING_PREAMBLE_DECISION) for reflection {reflection_id}")
        print(f"STAGE19: Entering delivery flow for reflection {reflection_id}")
        print(f"STAGE19: Request data: {request.data}")
        print(f"STAGE19: Request message: '{request.message}'")
        return await process_and_respond(db, 19, reflection_id, chat_id, request)

    if current_stage == 27:  # CONFIRMATION STAGE
        logger.info(f"Processing Stage 27 (CONFIRMATION) for reflection {reflection_id}")
        
        # FIRST: Handle user choices (when request.data exists)
        if request.data and len(request.data) > 0:
            user_choice = request.data[0]
            print(f" STAGE27: Processing user choice without LLM: {user_choice}")
            
            try:
                # Handle identity reveal choice
                if "reveal_name" in user_choice:
                    reveal_choice = user_choice.get("reveal_name")
                    provided_name = user_choice.get("name")
                    print(f" STAGE27: Identity choice - reveal: {reveal_choice}, name: {provided_name}")
                    result = await delivery_service.process_identity_choice(
                        reflection_id=reflection_id,
                        reveal_choice=reveal_choice,
                        provided_name=provided_name,
                        db=db
                    )
                
                # Handle name input (when user chose reveal but didn't provide name initially)
                elif "name" in user_choice:
                    print(f" STAGE27: Name input: {user_choice.get('name')}")
                    result = await delivery_service.process_identity_choice(
                        reflection_id=reflection_id,
                        reveal_choice=True,
                        provided_name=user_choice.get("name"),
                        db=db
                    )
                
                # Handle delivery mode choice
                elif "delivery_mode" in user_choice:
                    delivery_mode = user_choice.get("delivery_mode")
                    print(f" STAGE27: Delivery mode choice: {delivery_mode}")
                    
                    # Validate required contact info
                    if delivery_mode in [0, 2] and not user_choice.get("recipient_email"):
                        return MessageResponse(
                            success=False,
                            reflection_id=str(reflection_id),
                            sarthi_message="Email address is required for email delivery.",
                            current_stage=27,
                            next_stage=27
                        )
                    
                    if delivery_mode in [1, 2] and not user_choice.get("recipient_phone"):
                        return MessageResponse(
                            success=False,
                            reflection_id=str(reflection_id),
                            sarthi_message="Phone number is required for WhatsApp delivery.",
                            current_stage=27,
                            next_stage=27
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
                    print(f" STAGE27: Third-party email: {user_choice.get('email')}")
                    result = await delivery_service.process_third_party_email(
                        reflection_id=reflection_id,
                        third_party_email=user_choice.get("email"),
                        db=db
                    )
                
                else:
                    # Unrecognized choice format
                    print(f" STAGE27: Unrecognized choice format: {user_choice}")
                    return MessageResponse(
                        success=False,
                        reflection_id=str(reflection_id),
                        sarthi_message="Invalid choice format.",
                        current_stage=27,
                        next_stage=27
                    )
                
                print(f" STAGE27: Choice handling result: {result}")
                
                return MessageResponse(
                    success=result.get("success", True),
                    reflection_id=result["reflection_id"],
                    sarthi_message=result["sarthi_message"],
                    current_stage=result.get("current_stage", 27),
                    next_stage=result.get("next_stage", 27),
                    data=result.get("data", [])
                )
                
            except Exception as e:
                logger.error(f"Choice handling failed: {str(e)}", exc_info=True)
                print(f" STAGE27: Choice handling ERROR - {str(e)}")
                return MessageResponse(
                    success=False,
                    reflection_id=str(reflection_id),
                    sarthi_message="Failed to process your choice. Please try again.",
                    current_stage=27,
                    next_stage=27
                )
        
        # SECOND: Handle text message with LLM (when request.message exists but no data)
        elif request.message and request.message.strip():
            try:
                prompt_request_data = {"stage_id": current_stage, "data": {}}
                prompt_result = await prompt_engine_service.process_dict_request(prompt_request_data)
                
                llm_request = {
                    "prompt": prompt_result['prompt'],
                    "user_message": request.message,
                    "reflection_id": str(reflection_id)
                }
                
                llm_response_str = await llm_service.process_json_request(json.dumps(llm_request))
                llm_response = json.loads(llm_response_str)
                
                system_response = llm_response.get("system_response", {})
                user_response = llm_response.get("user_response", {})
                
                logger.info(f"Stage 27 LLM system_response: {system_response}")
                logger.info(f"Stage 27 LLM user_response: {user_response}")
                
                db_handler.save_message(db, reflection_id, request.message, sender=0, stage_no=current_stage)
                
                decision = None

                # Handle case where system_response is just a string "yes" or "no"
                if isinstance(system_response, str):
                    response_str = system_response.lower().strip()
                    if response_str in ["yes", "y", "true", "1"]:
                        decision = "yes"
                    elif response_str in ["no", "n", "false", "0"]:
                        decision = "no"

                # Handle case where system_response is a dictionary
                elif isinstance(system_response, dict):
                    # Check for specific decision fields first
                    if "decision" in system_response:
                        decision_value = str(system_response["decision"]).lower().strip()
                        if decision_value in ["yes", "y", "true", "1"]:
                            decision = "yes"
                        elif decision_value in ["no", "n", "false", "0"]:
                            decision = "no"
                    
                    elif "choice" in system_response:
                        choice_value = str(system_response["choice"]).lower().strip()
                        if choice_value in ["yes", "y", "true", "1"]:
                            decision = "yes"
                        elif choice_value in ["no", "n", "false", "0"]:
                            decision = "no"
                    
                    elif "proceed" in system_response:
                        proceed_value = system_response["proceed"]
                        if isinstance(proceed_value, bool):
                            decision = "yes" if proceed_value else "no"
                        else:
                            proceed_str = str(proceed_value).lower().strip()
                            decision = "yes" if proceed_str in ["yes", "true", "1"] else "no"

                logger.info(f"Final extracted decision: {decision}")
                
                if decision == "yes":
                    logger.info("LLM detected YES - showing identity reveal options")
                    
                    # Just show the identity reveal options - no delivery service call yet
                    result = await delivery_service.send_reflection(
                        reflection_id=reflection_id,
                        db=db
                    )
                    
                    return MessageResponse(
                        success=result.get("success", True),
                        reflection_id=result["reflection_id"],
                        sarthi_message=result["sarthi_message"],
                        current_stage=result.get("current_stage", 27),
                        next_stage=result.get("next_stage", 27),
                        data=result.get("data", [])
                    )
                
                elif decision == "no":
                    logger.info("LLM determined user wants to continue editing - going to stage 20")
                    
                    choice_data = {"choice": "0", "label": "No, continue editing", "llm_decision": decision}
                    db_handler.save_user_choice_message(db, reflection_id, choice_data, 27)
                    
                    db_handler.update_reflection_stage(db, reflection_id, 20)
                    return await process_and_respond(db, 20, reflection_id, chat_id, request)
                
                else:
                    logger.info("LLM couldn't determine clear decision - showing delivery options anyway")
                    
                    # Show delivery options when unclear
                    result = await delivery_service.send_reflection(
                        reflection_id=reflection_id,
                        db=db
                    )
                    
                    return MessageResponse(
                        success=result.get("success", True),
                        reflection_id=result["reflection_id"],
                        sarthi_message=result["sarthi_message"],
                        current_stage=result.get("current_stage", 27),
                        next_stage=result.get("next_stage", 27),
                        data=result.get("data", [])
                    )
                    
            except Exception as e:
                logger.error(f"Error in Stage 27 LLM processing: {str(e)}", exc_info=True)
                
                # Exception fallback - show delivery options
                try:
                    result = await delivery_service.send_reflection(
                        reflection_id=reflection_id,
                        db=db
                    )
                    
                    return MessageResponse(
                        success=result.get("success", True),
                        reflection_id=result["reflection_id"],
                        sarthi_message=result["sarthi_message"],
                        current_stage=result.get("current_stage", 27),
                        next_stage=result.get("next_stage", 27),
                        data=result.get("data", [])
                    )
                    
                except Exception as delivery_error:
                    logger.error(f"Delivery service also failed: {str(delivery_error)}", exc_info=True)
                    
                    fallback_message = "Let me help you with the delivery options for your reflection."
                    db_handler.save_message(db, reflection_id, fallback_message, sender=1, stage_no=27)
                    
                    return MessageResponse(
                        success=True,
                        reflection_id=str(reflection_id),
                        sarthi_message=fallback_message,
                        current_stage=27,
                        next_stage=27,
                        data=[]
                    )
        
        # THIRD: Fallback when no message and no data
        else:
            return await process_and_respond(db, 27, reflection_id, chat_id, request)
    
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