from fastapi import APIRouter, Depends, Request, HTTPException, status
from slowapi import Limiter
from slowapi.util import get_remote_address
from sqlalchemy.orm import Session
from sqlalchemy import func  
from app.database import get_db
from app.schemas import SendOTPRequest, SendOTPResponse, VerifyOTPRequest, VerifyOTPResponse, InviteValidateRequest, InviteValidateResponse
from app.auth.manager import AuthManager
from app.auth.utils import create_access_token, verify_invite_token, create_invite_token
from app.models import User, InviteCode, Chat
import logging

# The router now includes the /api prefix, which simplifies main.py
router = APIRouter(prefix="/api/auth", tags=["auth"])
auth_manager = AuthManager()
limiter = Limiter(key_func=get_remote_address)

@router.post("/send-otp", response_model=SendOTPResponse)
@limiter.limit("3/minute")
async def send_otp(request: Request, otp_request: SendOTPRequest, db: Session = Depends(get_db)):
    contact = otp_request.contact.strip()
    if not contact:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Contact is required")
    result = await auth_manager.send_otp(contact=contact, invite_token=otp_request.invite_token, db=db)
    return SendOTPResponse(success=result.success, message=result.message, contact_type=result.contact_type)

@router.post("/verify-otp", response_model=VerifyOTPResponse)
@limiter.limit("5/minute")
async def verify_otp_and_authenticate(request: Request, verify_request: VerifyOTPRequest, db: Session = Depends(get_db)):
    contact = verify_request.contact.strip()
    otp = verify_request.otp.strip()

    if not contact or not otp or len(otp) != 6 or not otp.isdigit():
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Valid contact and 6-digit OTP are required")

    user = auth_manager.utils.find_user_by_contact(contact, db)
    if user:
        result = auth_manager.verify_otp(contact, otp, db=db)
        if not result.success:
            return VerifyOTPResponse(success=False, message=result.message)
        
        if not user.chat:
            user.chat = Chat(user_id=user.user_id)
            db.commit(); db.refresh(user)

        access_token = create_access_token(str(user.user_id), str(user.chat.chat_id))
        return VerifyOTPResponse(success=True, access_token=access_token, user_id=str(user.user_id), is_new_user=False, is_anonymous=user.is_anonymous, onboarding_required=user.is_anonymous is None, message="Welcome back!")
    else:
        if not verify_request.invite_token:
            return VerifyOTPResponse(success=False, message="Invite token required for new user registration.")

        result = auth_manager.verify_otp(contact, otp, invite_token=verify_request.invite_token, db=db)
        if not result.success:
            return VerifyOTPResponse(success=False, message=result.message)

        invite_data = verify_invite_token(verify_request.invite_token)
        invite = db.query(InviteCode).filter(InviteCode.invite_id == invite_data["invite_id"], InviteCode.is_used == False).first()
        if not invite:
            return VerifyOTPResponse(success=False, message="Invite is invalid or already used.")

        normalized_contact = auth_manager.utils.normalize_contact_auto(contact)
        new_user = User(email=normalized_contact if "@" in normalized_contact else None, phone_number=int(normalized_contact) if "@" not in normalized_contact else None)
        db.add(new_user); db.flush()
        
        new_chat = Chat(user_id=new_user.user_id)
        db.add(new_chat); db.flush()

        invite.is_used = True
        invite.user_id = new_user.user_id
        invite.used_at = func.now()
        db.commit()

        access_token = create_access_token(str(new_user.user_id), str(new_chat.chat_id), str(invite.invite_id))
        return VerifyOTPResponse(success=True, access_token=access_token, user_id=str(new_user.user_id), is_new_user=True, onboarding_required=True, message="Account created successfully!")

@router.post("/invite/validate", response_model=InviteValidateResponse)
def validate_invite_code(request: InviteValidateRequest, db: Session = Depends(get_db)):
    """Validates an invite code. This is part of the auth flow."""
    invite_code = request.invite_code.strip().upper()
    existing_invite = db.query(InviteCode).filter(InviteCode.invite_code == invite_code, InviteCode.is_used == False).first()
    
    if not existing_invite:
        return InviteValidateResponse(valid=False, message="Invite code is invalid or has been used.")

    invite_jwt = create_invite_token(str(existing_invite.invite_id), invite_code)
    return InviteValidateResponse(valid=True, message="Invite code is valid!", invite_id=str(existing_invite.invite_id), invite_token=invite_jwt)