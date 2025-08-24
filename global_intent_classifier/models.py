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


class IntentRequestById(BaseModel):
    """Request model for intent classification - only needs reflection_id"""
    reflection_id: str = Field(..., description="Unique reflection ID to fetch message")


class MessageRequest(BaseModel):
    """
    Defines the structure for incoming chat messages from the client.
    """
    reflection_id: Optional[str] = None
    message: Optional[str] = ""
    data: List[Dict[str, Any]] = []


class IntentResult(BaseModel):
    """Final result from intent classifier"""
    reflection_id: str = Field(..., description="Reflection ID")
    intent: IntentType = Field(..., description="Classified intent")


class MessageData(BaseModel):
    """Model for fetched message data"""
    reflection_id: str = Field(..., description="Reflection ID")
    user_message: str = Field(..., description="User message content")
    timestamp: Optional[str] = Field(None, description="Message timestamp")
    metadata: Optional[Dict[str, Any]] = Field(None, description="Additional message metadata")


@dataclass
class PromptData:
    """Internal data model for prompt table records"""
    prompt_id: int
    flow_type: Optional[str]
    stage_id: int
    is_static: bool
    prompt_type: int
    prompt_name: str
    prompt: str
    next_stage: Optional[int]
    status: int