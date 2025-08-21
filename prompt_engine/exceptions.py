"""Custom exceptions for the prompt engine"""

class PromptEngineError(Exception):
    """Base exception for prompt engine errors"""
    pass


class StageNotFoundError(PromptEngineError):
    """Raised when a stage ID is not found"""
    pass


class InvalidDataError(PromptEngineError):
    """Raised when provided data is invalid for prompt substitution"""
    pass


class DatabaseError(PromptEngineError):
    """Raised when database operations fail"""
    pass