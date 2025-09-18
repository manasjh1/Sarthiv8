from fastapi import APIRouter, Depends, HTTPException, status, Response
from sqlalchemy.orm import Session
from app.database import get_db
from app.auth.utils import get_current_user
from app.auth.manager import AuthManager
from app.models import User
from app.schemas import OnboardingChoice
from pydantic import BaseModel
from typing import Optional

router = APIRouter(prefix="/api/user", tags=["user"])
auth_manager = AuthManager()

# --- Pydantic models for endpoints in this file ---
class UpdateNameRequest(BaseModel):
    name: str

class RequestContactOTPRequest(BaseModel):
    contact: str

class VerifyContactOTPRequest(BaseModel):
    contact: str
    otp: str

class UpdateProfileResponse(BaseModel):
    success: bool
    message: str

# --- User Profile Endpoints ---
@router.get("/me")
async def get_me(
    response: Response,
    current_user: User = Depends(get_current_user)
):
    """Gets the profile of the currently authenticated user."""
    return {
        "user_id": str(current_user.user_id),
        "name": current_user.name,
        "email": current_user.email,
        "phone_number": current_user.phone_number,
        "is_anonymous": current_user.is_anonymous,
        "is_verified": current_user.is_verified,
    }

@router.put("/update-name")
async def update_name(
    req: UpdateNameRequest, 
    response: Response,
    current_user: User = Depends(get_current_user), 
    db: Session = Depends(get_db)
):
    """Updates the authenticated user's name with auto JWT refresh."""
    name = req.name.strip()
    if not name:
        raise HTTPException(status_code=400, detail="Name cannot be empty.")
    
    current_user.name = name
    if current_user.is_anonymous:
        current_user.is_anonymous = False
    db.commit()
    return {"success": True, "message": "Name updated successfully."}

@router.post("/onboarding")
async def onboarding(data: OnboardingChoice, current_user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    """Sets the user's anonymity choice from the onboarding flow."""
    current_user.is_anonymous = data.is_anonymous
    if not data.is_anonymous:
        if not data.name or not data.name.strip():
            raise HTTPException(status_code=400, detail="Name is required.")
        current_user.name = data.name.strip()
    else:
        current_user.name = None
    db.commit()
    return {"message": "Onboarding choice saved."}

@router.post("/request-contact-otp", response_model=UpdateProfileResponse)
async def request_contact_otp(
    request: RequestContactOTPRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    Request an OTP to add or change a contact method for the current user.
    """
    contact = request.contact.strip()
    
    # Pass the current_user to trigger profile update logic
    result = await auth_manager.send_otp(contact=contact, db=db, current_user=current_user)
    
    if not result.success:
        # Handle specific error codes with better messages
        return UpdateProfileResponse(
            success=result.success, 
            message=result.message  # ✅ Frontend gets "message"
        )
        
    return UpdateProfileResponse(success=True, message=f"OTP sent successfully to {contact}")

@router.post("/verify-contact-otp", response_model=UpdateProfileResponse)
async def verify_contact_otp(
    request: VerifyContactOTPRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    Verify the OTP to confirm and save the new contact method.
    """
    contact = request.contact.strip()
    otp = request.otp.strip()

    status, message = auth_manager.storage.verify_for_existing_user(
        user_id=current_user.user_id, otp=otp, db=db
    )
    if status != "SUCCESS":
        raise HTTPException(status_code=400, detail=message)

    # If successful, update the user's profile
    contact_type = auth_manager.utils.detect_channel(contact)
    normalized_contact = auth_manager.utils.normalize_contact(contact, contact_type)
    
    if contact_type == "email":
        current_user.email = normalized_contact
    else: # whatsapp
        current_user.phone_number = int(normalized_contact)
        
    db.commit()
    return UpdateProfileResponse(success=True, message=f"{contact_type.capitalize()} updated successfully.")