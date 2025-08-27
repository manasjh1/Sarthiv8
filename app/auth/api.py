# app/auth/api.py - COMPLETE FIXED VERSION
from fastapi import APIRouter, Depends, Request, HTTPException, status
from slowapi import Limiter
from slowapi.util import get_remote_address
from sqlalchemy.orm import Session
from app.database import get_db
from app.schemas import SendOTPRequest, SendOTPResponse, VerifyOTPRequest, VerifyOTPResponse, InviteValidateRequest, InviteValidateResponse
from app.auth.manager import AuthManager
from app.auth.utils import create_access_token, verify_invite_token, create_invite_token
from app.models import User, InviteCode, Chat
from sqlalchemy import func 
import logging

router = APIRouter(prefix="/api/auth", tags=["auth"])
auth_manager = AuthManager()

# Rate limiter
limiter = Limiter(key_func=get_remote_address)

@router.post("/send-otp", response_model=SendOTPResponse)
@limiter.limit("3/minute")
async def send_otp(
    request: Request,
    otp_request: SendOTPRequest,
    db: Session = Depends(get_db)
):
    try:
        contact = otp_request.contact.strip()
        
        if not contact:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Contact information is required"
            )
        
        logging.info(f"🔍 OTP Request - Contact: {contact}, Has invite token: {bool(otp_request.invite_token)}")
        
        result = await auth_manager.send_otp(
            contact=contact,
            invite_token=otp_request.invite_token,
            db=db
        )
        
        return SendOTPResponse(
            success=result.success,
            message=result.message,
            contact_type=result.contact_type
        )
    
    except HTTPException:
        raise
    except Exception as e:
        logging.error(f"Unexpected error in send_otp: {str(e)}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to send OTP. Please try again later."
        )

@router.post("/verify-otp", response_model=VerifyOTPResponse)
@limiter.limit("5/minute")
async def verify_otp_and_authenticate(
    request: Request,
    verify_request: VerifyOTPRequest,
    db: Session = Depends(get_db)
):
    try:
        contact = verify_request.contact.strip()
        otp = verify_request.otp.strip()
        
        # Input validation
        if not contact or not otp:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Contact and OTP are required"
            )
        
        if len(otp) != 6 or not otp.isdigit():
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="OTP must be a 6-digit number"
            )
        
        logging.info(f"🔍 Verifying OTP for contact: {contact}")
        
        # Find user by contact
        user = auth_manager.utils.find_user_by_contact(contact, db)
        is_existing_user = user is not None
        
        logging.info(f"🔍 User found: {is_existing_user}")

        if is_existing_user:
            # ===== EXISTING USER VERIFICATION =====
            logging.info(f"🔍 Processing existing user: {user.user_id}")
            
            # Verify OTP first
            result = auth_manager.verify_otp(contact, otp, db=db)
            if not result.success:
                logging.warning(f"🔍 OTP verification failed for existing user: {result.message}")
                return VerifyOTPResponse(success=False, message=result.message)
            
            logging.info(f"🔍 OTP verified successfully for existing user: {user.user_id}")
            
            user_id_str = str(user.user_id)
            
            # Handle missing chat session
            if not user.chat:
                logging.warning(f"🔍 User {user.user_id} has no chat session. Creating one.")
                try:
                    new_chat = Chat(user_id=user.user_id)
                    db.add(new_chat)
                    db.flush()  # Get the ID without committing
                    chat_id_str = str(new_chat.chat_id)
                    db.commit()
                    logging.info(f"✅ Created missing chat session {chat_id_str} for existing user {user.user_id}")
                except Exception as chat_error:
                    db.rollback()
                    logging.error(f"Failed to create chat session for user {user.user_id}: {chat_error}", exc_info=True)
                    raise HTTPException(status_code=500, detail="Unable to create user session.")
            else:
                chat_id_str = str(user.chat.chat_id)
                logging.info(f"🔍 Using existing chat session: {chat_id_str}")

            # Create access token
            try:
                logging.info(f"🔍 Creating access token for user: {user_id_str}, chat: {chat_id_str}")
                access_token = create_access_token(user_id=user_id_str, chat_id=chat_id_str)
                logging.info(f"✅ Access token created successfully")
            except Exception as token_error:
                logging.error(f"Failed to create access token: {token_error}", exc_info=True)
                raise HTTPException(status_code=500, detail="Failed to create authentication token.")
            
            # Handle nullable is_anonymous field
            is_anonymous_value = user.is_anonymous if user.is_anonymous is not None else None
            onboarding_required = user.is_anonymous is None
            
            logging.info(f"✅ Existing user authentication successful - User: {user_id_str}")
            
            return VerifyOTPResponse(
                success=True, 
                access_token=access_token, 
                user_id=user_id_str, 
                is_new_user=False,
                is_anonymous=is_anonymous_value, 
                onboarding_required=onboarding_required, 
                message="Welcome back!"
            )
        else:
            # ===== NEW USER REGISTRATION =====
            logging.info(f"🔍 Processing new user registration for contact: {contact}")
            
            if not verify_request.invite_token:
                logging.warning(f"🔍 New user registration attempted without invite token")
                return VerifyOTPResponse(success=False, message="Invite token required for new user registration.")

            # Verify OTP first
            result = auth_manager.verify_otp(contact, otp, invite_token=verify_request.invite_token, db=db)
            if not result.success:
                logging.warning(f"🔍 OTP verification failed for new user: {result.message}")
                return VerifyOTPResponse(success=False, message=result.message)
            
            logging.info(f"🔍 OTP verified successfully for new user")

            try:
                # Verify invite token
                try:
                    logging.info(f"🔍 Verifying invite token")
                    invite_data = verify_invite_token(verify_request.invite_token)
                    logging.info(f"🔍 Invite token verified: {invite_data['invite_id']}")
                except Exception as invite_error:
                    logging.error(f"Invalid invite token: {invite_error}", exc_info=True)
                    return VerifyOTPResponse(success=False, message="Invalid or expired invite token.")
                
                # Check if invite code exists and is unused
                invite = db.query(InviteCode).filter(InviteCode.invite_id == invite_data["invite_id"]).first()
                if not invite:
                    logging.warning(f"🔍 Invite code not found: {invite_data['invite_id']}")
                    return VerifyOTPResponse(success=False, message="Invite code does not exist.")
                
                if invite.is_used:
                    logging.warning(f"🔍 Invite code already used: {invite_data['invite_id']}")
                    return VerifyOTPResponse(success=False, message="Invite code has already been used.")

                # Create new user
                normalized_contact = auth_manager.utils.normalize_contact_auto(contact)
                logging.info(f"🔍 Creating new user with contact: {normalized_contact}")
                
                try:
                    if "@" in normalized_contact:
                        user = User(email=normalized_contact)
                        logging.info(f"🔍 Creating user with email: {normalized_contact}")
                    else:
                        phone_number = int(normalized_contact)
                        user = User(phone_number=phone_number)
                        logging.info(f"🔍 Creating user with phone: {phone_number}")
                    
                    db.add(user)
                    db.flush()  # Get the user_id without committing
                    user_id_str = str(user.user_id)
                    logging.info(f"🔍 New user created with ID: {user_id_str}")
                    
                except ValueError as ve:
                    db.rollback()
                    logging.error(f"Invalid contact format: {ve}", exc_info=True)
                    raise HTTPException(status_code=400, detail="Invalid contact format.")
                except Exception as user_creation_error:
                    db.rollback()
                    logging.error(f"Failed to create user: {user_creation_error}", exc_info=True)
                    raise HTTPException(status_code=500, detail="Error creating user account.")

                # Create chat session for new user
                try:
                    logging.info(f"🔍 Creating chat session for new user: {user_id_str}")
                    new_chat = Chat(user_id=user.user_id)
                    db.add(new_chat)
                    db.flush()  # Get the chat_id without committing
                    chat_id_str = str(new_chat.chat_id)
                    logging.info(f"🔍 Chat session created with ID: {chat_id_str}")
                    
                except Exception as chat_creation_error:
                    db.rollback()
                    logging.error(f"Failed to create chat for new user {user_id_str}: {chat_creation_error}", exc_info=True)
                    raise HTTPException(status_code=500, detail="Error creating user session.")

                # Mark invite as used and transfer OTP data
                try:
                    logging.info(f"🔍 Marking invite as used and transferring OTP data")
                    invite.is_used = True
                    invite.user_id = user.user_id
                    invite.used_at = db.query(func.now()).scalar()
                    
                    # Transfer OTP data (this might clean up temporary storage)
                    auth_manager.storage.transfer_to_database(contact, user.user_id, str(invite.invite_id), db)
                    
                    # Commit all changes
                    db.commit()
                    logging.info(f"✅ Database transaction committed successfully")
                    
                except Exception as transfer_error:
                    db.rollback()
                    logging.error(f"Failed to finalize registration: {transfer_error}", exc_info=True)
                    raise HTTPException(status_code=500, detail="Error finalizing registration.")
                
                # Create access token
                try:
                    logging.info(f"🔍 Creating access token for new user: {user_id_str}, chat: {chat_id_str}")
                    access_token = create_access_token(
                        user_id=user_id_str, 
                        chat_id=chat_id_str, 
                        invite_id=str(invite.invite_id)
                    )
                    logging.info(f"✅ Access token created successfully for new user")
                except Exception as token_error:
                    logging.error(f"Failed to create access token for new user: {token_error}", exc_info=True)
                    raise HTTPException(status_code=500, detail="Failed to create authentication token.")
                
                logging.info(f"✅ New user registration successful - User: {user_id_str}")
                
                return VerifyOTPResponse(
                    success=True, 
                    access_token=access_token, 
                    user_id=user_id_str, 
                    is_new_user=True,
                    is_anonymous=user.is_anonymous,  # Will be None for new users
                    onboarding_required=True,  # New users always need onboarding
                    message="Account created successfully!"
                )
                
            except HTTPException:
                # Re-raise HTTP exceptions (these have proper error messages)
                raise
            except Exception as e:
                db.rollback()
                logging.error(f"New user registration failed: {e}", exc_info=True)
                raise HTTPException(status_code=500, detail="Error creating account.")
                
    except HTTPException:
        # Re-raise HTTP exceptions
        raise
    except Exception as e:
        # Log with full stack trace for debugging
        logging.error(f"Unexpected error in verify_otp: {str(e)}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Verification failed. Please try again."
        )

@router.post("/invite/validate", response_model=InviteValidateResponse)
def validate_invite_code(request: InviteValidateRequest, db: Session = Depends(get_db)):
    try:
        invite_code = request.invite_code.strip().upper()
        logging.info(f"🔍 Validating invite code: {invite_code}")
        
        existing_invite = db.query(InviteCode).filter(InviteCode.invite_code == invite_code).first()
        
        if not existing_invite:
            logging.warning(f"🔍 Invite code not found: {invite_code}")
            return InviteValidateResponse(valid=False, message="Invite code does not exist.")
        
        if existing_invite.is_used:
            logging.warning(f"🔍 Invite code already used: {invite_code}")
            return InviteValidateResponse(valid=False, message="Invite code has been used.")
        
        # Create invite JWT token
        try:
            invite_jwt = create_invite_token(str(existing_invite.invite_id), invite_code)
            logging.info(f"✅ Invite code validated successfully: {invite_code}")
            
            return InviteValidateResponse(
                valid=True, 
                message="Invite code is valid!", 
                invite_id=str(existing_invite.invite_id), 
                invite_token=invite_jwt
            )
        except Exception as token_error:
            logging.error(f"Failed to create invite token: {token_error}", exc_info=True)
            return InviteValidateResponse(valid=False, message="Error processing invite code.")
            
    except Exception as e:
        logging.error(f"Error validating invite code: {str(e)}", exc_info=True)
        return InviteValidateResponse(valid=False, message="Error validating invite code.")