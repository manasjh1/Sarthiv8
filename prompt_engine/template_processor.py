import re
from typing import Dict, Any, List
from .exceptions import InvalidDataError


class TemplateProcessor:
    """Async template processor for variable substitution"""
    
    @staticmethod
    async def substitute_variables(template: str, data: Dict[str, Any]) -> str:
        """
        Substitute variables in template with provided data
        Handle missing variables gracefully by leaving them as placeholders
        """
        if not template:
            return ""
        
        single_brace_vars = re.findall(r'\{([\w-]+)\}', template)
        double_brace_vars = re.findall(r'\{\{([\w-]+)\}\}', template)
        
        all_variables = list(set(single_brace_vars + double_brace_vars))
        
        if not all_variables:
            return template
        
        # Check if any required variables are missing
        missing_vars = [var for var in all_variables if var not in data]
        if missing_vars:
            # For dynamic prompts, we could either:
            # 1. Raise an error (strict mode)
            # 2. Leave placeholders (lenient mode)
            # 3. Use empty strings (replacement mode)
            
            # Option 1: Strict mode - uncomment to use
            # raise InvalidDataError(f"Missing required variables: {missing_vars}")
            
            # Option 3: Replacement mode - replace missing vars with empty strings
            for var in missing_vars:
                data[var] = ""
        
        result = template
        
        # Replace double brace variables first
        for var in double_brace_vars:
            if var in data:
                value = str(data[var]) if data[var] is not None else ""
                result = result.replace(f"{{{{{var}}}}}", value)
        
        # Replace single brace variables
        for var in single_brace_vars:
            if var in data:
                value = str(data[var]) if data[var] is not None else ""
                result = result.replace(f"{{{var}}}", value)
        
        return result
    
    @staticmethod
    def extract_variables(template: str) -> List[str]:
        """
        Extract all variables from a template
        """
        if not template:
            return []
        
        single_brace_vars = re.findall(r'\{([\w-]+)\}', template)
        double_brace_vars = re.findall(r'\{\{([\w-]+)\}\}', template)
        
        all_variables = list(set(single_brace_vars + double_brace_vars))
        return all_variables