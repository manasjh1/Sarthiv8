# app/auth/api.py
from fastapi import APIRouter, Depends, Request, HTTPException, status
from slowapi import Limiter
from slowapi.util import get_remote_address
from sqlalchemy.orm import Session
from app.database import get_db
from app.schemas import SendOTPRequest, SendOTPResponse, VerifyOTPRequest, VerifyOTPResponse, InviteValidateRequest, InviteValidateResponse
from app.auth.manager import AuthManager
from app.auth.utils import create_access_token, verify_invite_token, create_invite_token
from app.models import User, InviteCode, Chat # <-- Import Chat model
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
        logging.error(f"Unexpected error in send_otp: {str(e)}")
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
        
        user = auth_manager.utils.find_user_by_contact(contact, db)
        is_existing_user = user is not None

        if is_existing_user:
            # ===== EXISTING USER VERIFICATION =====
            result = auth_manager.verify_otp(contact, otp, db=db)
            if not result.success:
                return VerifyOTPResponse(success=False, message=result.message)
            
            user_id_str = str(user.user_id)
            if not user.chat:
                raise HTTPException(status_code=500, detail="Existing user is missing a chat session.")
            chat_id_str = str(user.chat.chat_id)

            # Create token with both user_id and chat_id
            access_token = create_access_token(user_id=user_id_str, chat_id=chat_id_str)
            return VerifyOTPResponse(
                success=True, access_token=access_token, user_id=user_id_str, is_new_user=False,
                is_anonymous=user.is_anonymous, onboarding_required=user.is_anonymous is None, message="Welcome back!"
            )
        else:
            # ===== NEW USER REGISTRATION =====
            if not verify_request.invite_token:
                return VerifyOTPResponse(success=False, message="Invite token required for new user registration.")

            result = auth_manager.verify_otp(contact, otp, db=db)
            if not result.success:
                return VerifyOTPResponse(success=False, message=result.message)

            try:
                invite_data = verify_invite_token(verify_request.invite_token)
                invite = db.query(InviteCode).filter(InviteCode.invite_id == invite_data["invite_id"]).first()
                if not invite or invite.is_used:
                    return VerifyOTPResponse(success=False, message="Invite code has already been used.")

                normalized_contact = auth_manager.utils.normalize_contact_auto(contact)
                if "@" in normalized_contact:
                    user = User(email=normalized_contact)
                else:
                    user = User(phone_number=int(normalized_contact))
                db.add(user)
                db.commit()
                db.refresh(user)

                # *** FIX: CREATE CHAT SESSION FOR NEW USER ***
                new_chat = Chat(user_id=user.user_id)
                db.add(new_chat)
                db.commit()
                db.refresh(new_chat)
                logging.info(f"✅ Created chat session for new user {user.user_id}")
                # *** END FIX ***
                
                user_id_str = str(user.user_id)
                chat_id_str = str(new_chat.chat_id)

                auth_manager.storage.transfer_to_database(contact, user.user_id, str(invite.invite_id), db)
                
                access_token = create_access_token(user_id=user_id_str, chat_id=chat_id_str, invite_id=str(invite.invite_id))
                
                return VerifyOTPResponse(
                    success=True, access_token=access_token, user_id=user_id_str, is_new_user=True,
                    is_anonymous=user.is_anonymous, onboarding_required=user.is_anonymous is None, message="Account created successfully!"
                )
            except Exception as e:
                db.rollback()
                logging.error(f"User creation failed: {e}")
                raise HTTPException(status_code=500, detail="Error creating account.")
    except Exception as e:
        logging.error(f"Unexpected error in verify_otp: {str(e)}")
        raise HTTPException(status_code=500, detail="Verification failed.")

@router.post("/invite/validate", response_model=InviteValidateResponse)
def validate_invite_code(request: InviteValidateRequest, db: Session = Depends(get_db)):
    invite_code = request.invite_code.strip().upper()
    existing_invite = db.query(InviteCode).filter(InviteCode.invite_code == invite_code).first()
    if not existing_invite:
        return InviteValidateResponse(valid=False, message="Invite code does not exist.")
    if existing_invite.is_used:
        return InviteValidateResponse(valid=False, message="Invite code has been used.")
    invite_jwt = create_invite_token(str(existing_invite.invite_id), invite_code)
    return InviteValidateResponse(valid=True, message="Invite code is valid!", invite_id=str(existing_invite.invite_id), invite_token=invite_jwt)