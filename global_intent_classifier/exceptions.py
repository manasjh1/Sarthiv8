"""Custom exceptions for the global intent classifier"""

class IntentClassifierError(Exception):
    """Base exception for intent classifier errors"""
    pass


class MessageNotFoundError(IntentClassifierError):
    """Raised when a message is not found by reflection_id"""
    pass


class PromptEngineError(IntentClassifierError):
    """Raised when prompt engine operations fail"""
    pass


class LLMServiceError(IntentClassifierError):
    """Raised when LLM service operations fail"""
    pass
