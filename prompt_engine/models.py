from typing import Dict, Any, Optional, List
from pydantic import BaseModel, Field
from dataclasses import dataclass


class PromptRequest(BaseModel):
    """Request model for prompt engine input"""
    stage_id: int = Field(..., description="Stage ID to fetch prompt for")
    data: Dict[str, Any] = Field(default_factory=dict, description="Data for variable substitution")


class PromptResponse(BaseModel):
    """Response model for prompt engine output"""
    prompt: str = Field(..., description="Generated prompt text")
    is_static: bool = Field(..., description="Whether prompt is static or dynamic")
    prompt_type: int = Field(..., description="0 for user prompt, 1 for system prompt")
    next_stage: Optional[int] = Field(None, description="Next stage ID")
    next_stage_variables: Optional[List[str]] = Field(None, description="Required variables for next stage")


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
