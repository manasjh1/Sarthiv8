from typing import Optional, Dict, Any, List
from pydantic import BaseModel, Field
from enum import Enum
from dataclasses import dataclass


class IntentType(str, Enum):
    """Enumeration of valid intent types"""
    INTENT_STOP = "INTENT_STOP"
    INTENT_RESTART = "INTENT_RESTART"
    INTENT_CONFUSED = "INTENT_CONFUSED"
    INTENT_SKIP_TO_DRAFT = "INTENT_SKIP_TO_DRAFT"
    NO_OVERRIDE = "NO_OVERRIDE"


class ConversationRequest(BaseModel):
    """
    Defines the structure for an incoming conversation turn from the client.
    """
    reflection_id: Optional[str] = None
    system_response: Optional[str] = ""
    user_response: Optional[str] = ""


class IntentResult(BaseModel):
    """Final result from the intent classifier"""
    reflection_id: str = Field(..., description="Reflection ID")
    system_response: Dict[str, Any] = Field(..., description="Data for the system, containing key-value pairs")
    user_response: Dict[str, Any] = Field(..., description="The response object to be shown to the user")


# --- Other models remain the same ---
class MessageData(BaseModel):
    reflection_id: str
    user_message: str
    timestamp: Optional[str] = None
    metadata: Optional[Dict[str, Any]] = None

@dataclass
class PromptData:
    prompt_id: int
    flow_type: Optional[str]
    stage_id: int
    is_static: bool
    prompt_type: int
    prompt_name: str
    prompt: str
    next_stage: Optional[int]
    status: int