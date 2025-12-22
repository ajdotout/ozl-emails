"""Prompt engineering and AI generation logic."""

import json
from typing import List, Dict, Any, Optional
from pydantic import BaseModel, Field

# Gemini imports - commented out for potential rollback
# from google import genai
from groq import Groq
from config import Config

# Initialize Groq client
groq_client = Groq(api_key=Config.GROQ_API_KEY)

# Gemini client initialization - commented out
# client = genai.Client(api_key=Config.GEMINI_API_KEY)


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
    """Generate content for a single recipient using Groq.

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

    # Try primary model first, fallback to base model on rate limits
    models_to_try = [
        "moonshotai/kimi-k2-instruct-0905",  # Primary model with version
        "moonshotai/kimi-k2-instruct"        # Fallback model without version suffix
    ]

    for model in models_to_try:
        try:
            # Groq implementation
            response = groq_client.chat.completions.create(
                model=model,
                messages=[
                    {
                        "role": "user",
                        "content": prompt,
                    }
                ],
                response_format={
                    "type": "json_schema",
                    "json_schema": {
                        "name": "generation_response",
                        "schema": GenerationResponse.model_json_schema(),
                    }
                },
            )

            # Parse JSON response from Groq
            response_content = response.choices[0].message.content
            if not response_content:
                raise ValueError("Empty response from AI")

            # Parse JSON and validate with Pydantic
            response_data = json.loads(response_content)
            parsed_response = GenerationResponse.model_validate(response_data)

            # Map back to dict
            result_map = {}
            for section in parsed_response.sections:
                result_map[section.section_id] = section.content

            return result_map

        except Exception as e:
            error_msg = str(e).lower()
            # Check if this is a rate limit error (429) and we have fallback models
            is_rate_limit = (
                "429" in error_msg or
                "rate limit" in error_msg or
                "too many requests" in error_msg or
                "quota exceeded" in error_msg
            )

            if is_rate_limit and model != models_to_try[-1]:
                print(f"Rate limit hit with model '{model}', trying fallback model '{models_to_try[models_to_try.index(model) + 1]}'")
                continue
            else:
                print(f"AI Generation Error with model '{model}': {e}")
                # Re-raise to trigger retry logic in main loop
                raise e
    
    # Gemini implementation - commented out for potential rollback
    # try:
    #     response = client.models.generate_content(
    #         model='gemini-2.5-flash-lite',
    #         contents=prompt,
    #         config={
    #             'response_mime_type': 'application/json',
    #             'response_schema': GenerationResponse,
    #         },
    #     )
    #     
    #     # Parse Pydantic response
    #     # The SDK returns the parsed object directly if response_schema is passed?
    #     # Typically it returns a GenerateContentResponse object.
    #     # We need to check if .parsed is available (in v1.1+) or parse .text
    #     
    #     # Using .parsed property which is available when using schema
    #     if not response.parsed:
    #          raise ValueError("Empty response from AI")
    #          
    #     # Map back to dict
    #     result_map = {}
    #     for section in response.parsed.sections:
    #         result_map[section.section_id] = section.content
    #         
    #     return result_map
    #     
    # except Exception as e:
    #     print(f"AI Generation Error: {e}")
    #     # Re-raise to trigger retry logic in main loop
    #     raise e
