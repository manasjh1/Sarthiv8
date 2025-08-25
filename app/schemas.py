# app/schemas.py
from pydantic import BaseModel
from typing import Optional, List, Dict, Any
import uuid

class MessageRequest(BaseModel):
    reflection_id: Optional[str] = None
    message: Optional[str] = ""
    data: List[Dict[str, Any]] = []

class MessageResponse(BaseModel):
    success: bool
    reflection_id: Optional[str] = None
    sarthi_message: Optional[str] = None
    current_stage: Optional[int] = None
    next_stage: Optional[int] = None
    data: List[Dict[str, Any]] = []

class PromptResult(BaseModel):
    prompt: str
    is_static: bool
    prompt_type: int
    next_stage: int