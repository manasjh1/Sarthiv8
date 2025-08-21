import re
from typing import Dict, Any, List
from .exceptions import InvalidDataError


class TemplateProcessor:
    """Async template processor for variable substitution"""
    
    @staticmethod
    async def substitute_variables(template: str, data: Dict[str, Any]) -> str:
        """
        Substitute variables in template with provided data
        """
        if not template:
            return ""
        
        single_brace_vars = re.findall(r'\{([\w-]+)\}', template)
        double_brace_vars = re.findall(r'\{\{([\w-]+)\}\}', template)
        
        all_variables = list(set(single_brace_vars + double_brace_vars))
        
        if not all_variables:
            return template
        
        missing_vars = [var for var in all_variables if var not in data]
        if missing_vars:
            raise InvalidDataError(f"Missing required variables: {missing_vars}")
        
        result = template
        
        for var in double_brace_vars:
            if var in data:
                value = str(data[var]) if data[var] is not None else ""
                result = result.replace(f"{{{{{var}}}}}", value)
        
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
