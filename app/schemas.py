# app/schemas.py - COMPLETE UPDATED VERSION
from pydantic import BaseModel, EmailStr, Field
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

class UniversalRequest(BaseModel):
    reflection_id: Optional[str] = None
    message: str
    data: List[Dict[str, Any]] = []

class ProgressInfo(BaseModel):
    current_step: int
    total_step: int
    workflow_completed: bool

class UniversalResponse(BaseModel):
    success: bool
    reflection_id: str
    sarthi_message: str
    current_stage: int
    next_stage: int
    progress: ProgressInfo
    data: List[Dict[str, Any]] = []

class InviteValidateRequest(BaseModel):
    invite_code: str

class InviteValidateResponse(BaseModel):
    valid: bool
    message: str
    invite_id: Optional[str] = None
    invite_token: Optional[str] = None 

class InviteGenerateResponse(BaseModel):
    success: bool
    message: str
    invite_code: Optional[str] = None
    invite_id: Optional[str] = None
    created_at: Optional[str] = None
    is_used: Optional[bool] = None

class SendOTPRequest(BaseModel):
    contact: str  
    invite_token: Optional[str] = None  

class SendOTPResponse(BaseModel):
    success: bool
    message: str
    contact_type: Optional[str] = None  

class VerifyOTPRequest(BaseModel):
    contact: str  
    otp: str
    invite_token: Optional[str] = None  

class VerifyOTPResponse(BaseModel):
    success: bool
    message: str
    access_token: Optional[str] = None
    user_id: Optional[str] = None
    is_new_user: Optional[bool] = None
    is_anonymous: Optional[bool] = None 
    onboarding_required: Optional[bool] = None  

class UserProfileResponse(BaseModel):
    user_id: str
    name: Optional[str] = ""
    email: Optional[str] = ""  
    phone_number: Optional[int] = None
    is_verified: Optional[bool] = True
    user_type: Optional[str] = "user"
    proficiency_score: Optional[int] = 0
    created_at: Optional[str] = None
    updated_at: Optional[str] = None

class OnboardingChoice(BaseModel):
    is_anonymous: bool
    name: Optional[str] = None

class ChatMessage(BaseModel):
    """Schema for chat messages in reflection history"""
    sender: str = Field(..., description="Message sender: user, sarthi, system, reflection")
    message: str = Field(..., description="Message content")
    stage: Optional[int] = Field(None, description="Conversation stage")
    is_distress: bool = Field(False, description="Whether message was flagged as distress")
    created_at: Optional[str] = Field(None, description="When message was created")

class InboxReflection(BaseModel):
    """Schema for inbox reflections - ONLY SUMMARY"""
    reflection_id: str
    summary: str  # ONLY summary, no full content
    from_sender: str = Field(..., alias="from")
    created_at: Optional[str] = None
    
    class Config:
        allow_population_by_field_name = True

class OutboxReflection(BaseModel):
    """Schema for outbox reflections"""
    reflection_id: str
    summary: str
    to: str
    status: str
    created_at: Optional[str] = None

class HistoryReflection(BaseModel):
    """Schema for history reflections with FULL CHAT"""
    reflection_id: str
    summary: str
    from_sender: str = Field(..., alias="from")
    to: str
    type: str  # "sent" or "received"
    status: str
    created_at: Optional[str] = None
    chat_history: List[ChatMessage]  # ALWAYS includes full chat
    
    class Config:
        allow_population_by_field_name = True

class InboxResponse(BaseModel):
    """Response for inbox endpoint"""
    success: bool
    data: List[InboxReflection]

class OutboxResponse(BaseModel):
    """Response for outbox endpoint"""
    success: bool
    data: List[OutboxReflection]

class HistoryResponse(BaseModel):
    """Response for history endpoint with pagination"""
    success: bool
    total: int
    page: int
    limit: int
    has_more: bool  # For scroll detection
    data: List[HistoryReflection]
    flow_type: Optional[str] = Field(None, description="Reflection flow type")
    updated_at: Optional[str] = Field(None, description="ISO timestamp when reflection was last updated")
    chat_history: Optional[List[ChatMessage]] = Field(None, description="Full conversation history")

class ReflectionStatsSent(BaseModel):
    """Statistics for sent reflections"""
    total: int = Field(..., description="Total sent reflections")
    delivered: int = Field(..., description="Successfully delivered reflections")
    in_progress: int = Field(..., description="Reflections still being created")
    blocked: int = Field(..., description="Blocked reflections")
    completed: int = Field(..., description="Completed but not delivered reflections")

class ReflectionStatsReceived(BaseModel):
    """Statistics for received reflections"""
    total: int = Field(..., description="Total received reflections")

class ReflectionStats(BaseModel):
    """Schema for reflection statistics"""
    sent: ReflectionStatsSent = Field(..., description="Sent reflection statistics")
    received: ReflectionStatsReceived = Field(..., description="Received reflection statistics")
    total_reflections: int = Field(..., description="Total reflections (sent + received)")

class ReflectionSummary(BaseModel):
    """Summary information for a reflection (used in inbox/outbox responses)"""
    reflection_id: str = Field(..., description="Unique reflection identifier")
    summary: str = Field(..., description="Reflection summary")
    from_sender: str = Field(..., alias="from", description="Sender of the reflection")
    to: Optional[str] = Field(None, description="Recipient of the reflection")
    status: Optional[str] = Field(None, description="Reflection status")
    created_at: Optional[str] = Field(None, description="Creation timestamp")
    updated_at: Optional[str] = Field(None, description="Last updated timestamp")

    class Config:
        allow_population_by_field_name = True

class InboxResponse(BaseModel):
    """Response schema for inbox endpoint"""
    success: bool = Field(..., description="Request success status")
    count: int = Field(..., description="Number of reflections returned")
    data: List[InboxReflection] = Field(..., description="List of received reflections")

class OutboxResponse(BaseModel):
    """Response schema for outbox endpoint"""
    success: bool = Field(..., description="Request success status")
    count: int = Field(..., description="Number of reflections returned")
    data: List[OutboxReflection] = Field(..., description="List of sent reflections")

class ReflectionDetails(BaseModel):
    """Detailed reflection information schema"""
    reflection_id: str = Field(..., description="Unique reflection identifier")
    summary: str = Field(..., description="Reflection summary")
    from_sender: str = Field(..., alias="from", description="Sender of the reflection")
    to: Optional[str] = Field(None, description="Recipient of the reflection")
    type: Optional[str] = Field(None, description="Reflection type (sent/received)")
    status: Optional[str] = Field(None, description="Reflection status")
    created_at: Optional[str] = Field(None, description="Creation timestamp")
    updated_at: Optional[str] = Field(None, description="Last updated timestamp")
    chat_history: Optional[List[ChatMessage]] = Field(None, description="Full conversation history")

    class Config:
        allow_population_by_field_name = True

class HistoryResponse(BaseModel):
    """Response schema for history endpoint with pagination"""
    success: bool = Field(..., description="Request success status")
    total: int = Field(..., description="Total number of reflections")
    page: int = Field(..., description="Current page number")
    limit: int = Field(..., description="Items per page")
    pages: int = Field(..., description="Total number of pages")
    count: int = Field(..., description="Number of reflections in current page")
    data: List[HistoryReflection] = Field(..., description="List of reflections with optional chat history")

class ReflectionDetails(BaseModel):
    """Detailed reflection information schema"""
    reflection_id: str = Field(..., description="Unique reflection identifier")
    summary: str = Field(..., description="Reflection summary")
    from_sender: str = Field(..., alias="from", description="Sender of the reflection")
    to: Optional[str] = Field(None, description="Recipient of the reflection")
    type: Optional[str] = Field(None, description="Reflection type (sent/received)")
    status: Optional[str] = Field(None, description="Reflection status")
    created_at: Optional[str] = Field(None, description="Creation timestamp")
    updated_at: Optional[str] = Field(None, description="Last updated timestamp")
    chat_history: Optional[List[ChatMessage]] = Field(None, description="Full conversation history")

    class Config:
        allow_population_by_field_name = True

class ReflectionStatsResponse(BaseModel):
    """Response schema for reflection stats endpoint"""
    success: bool = Field(..., description="Request success status")
    data: ReflectionStats = Field(..., description="Reflection statistics")

class PaginationParams(BaseModel):
    """Common pagination parameters"""
    page: int = Field(1, ge=1, description="Page number (starts from 1)")
    limit: int = Field(10, ge=1, le=100, description="Items per page (max 100)")

class ReflectionFilters(BaseModel):
    """Filters for reflection queries"""
    reflection_type: Optional[str] = Field("all", description="Filter by type: all, sent, received")
    include_chat: Optional[bool] = Field(False, description="Include full chat history")
    status: Optional[str] = Field(None, description="Filter by status: delivered, in_progress, blocked, completed")
    date_from: Optional[str] = Field(None, description="Filter reflections from this date (ISO format)")
    date_to: Optional[str] = Field(None, description="Filter reflections to this date (ISO format)")

class BaseResponse(BaseModel):
    """Base response schema"""
    success: bool = Field(..., description="Request success status")
    message: Optional[str] = Field(None, description="Optional response message")
    
class ErrorResponse(BaseModel):
    """Error response schema"""
    success: bool = Field(False, description="Request success status (always false for errors)")
    error: str = Field(..., description="Error message")
    error_code: Optional[str] = Field(None, description="Optional error code")
    details: Optional[Dict[str, Any]] = Field(None, description="Optional additional error details")