"""Email utilities for variable replacement."""

import re
from typing import Dict, Optional


def replace_variables(content: str, data: Optional[Dict[str, str]]) -> str:
    """Replace {{variable}} placeholders with data values.
    
    Args:
        content: The text content containing placeholders
        data: Dictionary of values to replace
        
    Returns:
        String with replaced variables
    """
    if not data:
        return content
        
    def replacer(match):
        variable = match.group(1)
        # Check exact, lower, upper
        val = (
            data.get(variable) or 
            data.get(variable.lower()) or 
            data.get(variable.upper())
        )
        return str(val) if val is not None else match.group(0)
        
    return re.sub(r'\{\{(\w+)\}\}', replacer, content)

