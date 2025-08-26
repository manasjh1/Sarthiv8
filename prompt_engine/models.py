from typing import Dict, Any, Optional
from pydantic import BaseModel, Field
from dataclasses import dataclass


class PromptRequest(BaseModel):
    """Request model for prompt engine input"""
    stage_id: int = Field(..., description="Stage ID to fetch prompt for")
    data: Dict[str, Any] = Field(..., description="Data for variable substitution (required, can be empty)")


class PromptResponse(BaseModel):
    """Response model for prompt engine output"""
    prompt: str = Field(..., description="Generated prompt text")
    is_static: bool = Field(..., description="Whether prompt is static or dynamic")
    prompt_type: int = Field(..., description="0 for user prompt, 1 for system prompt")
    next_stage: Optional[int] = Field(None, description="Next stage ID if applicable")


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