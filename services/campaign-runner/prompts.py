"""Prompt engineering and AI generation logic."""

from typing import List, Dict, Any, Optional
from pydantic import BaseModel, Field

from google import genai
from config import Config

# Initialize GenAI client
client = genai.Client(api_key=Config.GEMINI_API_KEY)


class GeneratedSection(BaseModel):
    """A single generated section content."""
    section_id: str = Field(description="The ID of the personalized section")
    content: str = Field(description="The generated text content for this section")


class GenerationResponse(BaseModel):
    """Structured response from the AI."""
    sections: List[GeneratedSection]


def build_prompt(
    all_sections: List[Dict[str, Any]],
    personalized_sections: List[Dict[str, Any]],
    recipient_data: Dict[str, Any]
) -> str:
    """Build the prompt for a single recipient.
    
    Args:
        all_sections: List of all section objects from the campaign
        personalized_sections: List of sections that need generation
        recipient_data: Dictionary of CSV fields for the recipient
        
    Returns:
        The constructed prompt string
    """
    # 1. Build Email Structure Overview
    sorted_sections = sorted(all_sections, key=lambda s: s.get('order', 0))
    
    structure_lines = []
    for i, section in enumerate(sorted_sections):
        s_type = section.get('type', 'text')
        s_mode = section.get('mode', 'static')
        s_id = section.get('id', '')
        s_name = section.get('name', 'Section')
        s_content = section.get('content', '')
        
        if s_mode == 'personalized':
            fields = section.get('selectedFields', [])
            fields_str = ', '.join(fields) if fields else 'any available'
            line = (
                f'{i + 1}. [GENERATE - ID: "{s_id}"] "{s_name}"\n'
                f'   Instructions: {s_content}\n'
                f'   Fields to use: {fields_str}'
            )
            structure_lines.append(line)
        elif s_type == 'button':
            url = section.get('buttonUrl', 'booking link')
            structure_lines.append(f'{i + 1}. [CTA BUTTON] "{s_content}" -> {url}')
        else:
            # Static Text - show preview
            # Strip simple HTML tags for context clarity
            plain = s_content.replace('<br>', '\n').replace('<p>', '').replace('</p>', '\n')
            # Rudimentary strip (we don't need perfect HTML parsing here, just context)
            if len(plain) > 150:
                plain = plain[:150] + '...'
            structure_lines.append(f'{i + 1}. [STATIC] "{s_name}": "{plain}"')
            
    email_structure = '\n\n'.join(structure_lines)
    
    # 2. Build Recipient Fields
    # Filter out email to avoid confusion/PII leakage if not needed
    relevant_fields = {
        k: v for k, v in recipient_data.items() 
        if 'email' not in k.lower()
    }
    
    fields_lines = []
    for k, v in relevant_fields.items():
        fields_lines.append(f'  {k}: {v or "(not provided)"}')
    fields_str = '\n'.join(fields_lines)
    
    # 3. Sections to Generate List
    sections_list = '\n'.join([
        f'- "{s.get("name")}" (ID: {s.get("id")})' 
        for s in personalized_sections
    ])
    
    return f"""You are generating personalized email content for a recipient.

EMAIL STRUCTURE (for context):
{email_structure}

---

SECTIONS TO GENERATE:
{sections_list}

---

RECIPIENT DATA:
{fields_str}

---

Generate the [GENERATE] sections for this recipient. Follow the instructions provided for each section.
Return content that flows naturally with the static sections around it.
Keep each section concise (1-3 sentences)."""


def generate_content(
    all_sections: List[Dict[str, Any]],
    recipient_data: Dict[str, Any]
) -> Dict[str, str]:
    """Generate content for a single recipient using Google GenAI.
    
    Args:
        all_sections: Full list of campaign sections
        recipient_data: Recipient metadata/CSV row
        
    Returns:
        Dictionary mapping section_id -> generated_content
    """
    personalized_sections = [
        s for s in all_sections 
        if s.get('mode') == 'personalized'
    ]
    
    if not personalized_sections:
        return {}
        
    prompt = build_prompt(all_sections, personalized_sections, recipient_data)
    
    try:
        response = client.models.generate_content(
            model='gemini-2.5-flash-lite',
            contents=prompt,
            config={
                'response_mime_type': 'application/json',
                'response_schema': GenerationResponse,
            },
        )
        
        # Parse Pydantic response
        # The SDK returns the parsed object directly if response_schema is passed?
        # Typically it returns a GenerateContentResponse object.
        # We need to check if .parsed is available (in v1.1+) or parse .text
        
        # Using .parsed property which is available when using schema
        if not response.parsed:
             raise ValueError("Empty response from AI")
             
        # Map back to dict
        result_map = {}
        for section in response.parsed.sections:
            result_map[section.section_id] = section.content
            
        return result_map
        
    except Exception as e:
        print(f"AI Generation Error: {e}")
        # Re-raise to trigger retry logic in main loop
        raise e
