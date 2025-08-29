# app/endpoints/invite.py

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from app.database import get_db
from app.schemas import InviteValidateRequest, InviteValidateResponse, InviteGenerateResponse
from app.auth.utils import create_invite_token
from app.models import InviteCode
import random
import string

router = APIRouter(prefix="/invite", tags=["invite"])

@router.post("/generate", response_model=InviteGenerateResponse)
def generate_invite(db: Session = Depends(get_db)):
    """
    Generates a new, unique invite code.
    """
    for _ in range(10): # Attempts to find a unique code
        code = ''.join(random.choices("ABCDEFGHJKMNPQRSTUVWXYZ23456789", k=8))
        if not db.query(InviteCode).filter(InviteCode.invite_code == code).first():
            new_invite = InviteCode(invite_code=code)
            db.add(new_invite)
            db.commit()
            return InviteGenerateResponse(success=True, message="Invite generated", invite_code=code, invite_id=str(new_invite.invite_id))
    raise HTTPException(status_code=500, detail="Could not generate a unique invite code.")