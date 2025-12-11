"""Email HTML generation and rendering."""

import hmac
import hashlib
import re
from typing import List, Dict, Any, Optional
from urllib.parse import urlencode

from config import Config


# Brand colors matching OutreachMarketing template
BRAND = {
    'primary': '#1e88e5',
    'primaryLight': '#bfdbfe',
    'textDark': '#111827',
    'textMuted': '#4b5563',
    'textLight': '#9ca3af',
    'bgLight': '#f3f4f6',
    'bgCard': '#ffffff',
    'bgFooter': '#f9fafb',
    'border': '#e5e7eb',
}


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


def generate_unsubscribe_url(email: str) -> str:
    """Generate a signed unsubscribe URL.
    
    Args:
        email: The recipient's email address
        
    Returns:
        Full unsubscribe URL
    """
    secret = Config.UNSUBSCRIBE_SECRET.encode('utf-8')
    msg = email.lower().encode('utf-8')
    
    token = hmac.new(secret, msg, hashlib.sha256).hexdigest()[:16]
    
    # Base URL hardcoded or from config? 
    # For now assuming prod/dev distinction handled via env or hardcoded as per TS file default
    # TS file had 'http://localhost:3000' fallback.
    # We should probably use an env var for APP_URL, but keeping it simple for now matching TS logic roughly
    # or better, use a configured domain.
    # Let's assume production for "ozlistings.com" if not set? 
    # Actually, let's just make it relative path if sent via SparkPost? 
    # No, email links must be absolute.
    # Let's add APP_URL to config later? For now, I'll use a placeholder or derived from domain.
    # But wait, unsubscribe is handled by the NEXT.JS app? Yes, /api/unsubscribe.
    # So it needs to point to the dashboard URL.
    
    base_url = "https://oz-dev-dash-ten.vercel.app"
    
    params = urlencode({'email': email, 'token': token})
    return f"{base_url}/api/unsubscribe?{params}"


def generate_email_html(
    sections: List[Dict[str, Any]],
    subject_line: str,
    recipient_data: Dict[str, Any],
    generated_content: Optional[Dict[str, str]] = None
) -> str:
    """Generate the full email HTML.
    
    Args:
        sections: List of section definitions
        subject_line: Email subject
        recipient_data: CSV row data for variable replacement
        generated_content: Map of section_id -> generated text (from AI)
        
    Returns:
        Full HTML string
    """
    processed_subject = replace_variables(subject_line, recipient_data)
    unsubscribe_url = generate_unsubscribe_url(recipient_data.get('Email', ''))
    
    sections_html_parts = []
    
    for section in sections:
        s_type = section.get('type', 'text')
        s_mode = section.get('mode', 'static')
        s_id = section.get('id', '')
        s_name = section.get('name', '')
        s_content = section.get('content', '')
        s_button_url = section.get('buttonUrl', '#')
        
        if s_type == 'button':
            # CTA Button
            button_text = s_content
            if s_mode == 'personalized':
                # Rare case, but if button text is personalized
                if generated_content and s_id in generated_content:
                    button_text = generated_content[s_id]
                else:
                    button_text = f"[{s_name} - AI Generated]"
            else:
                button_text = replace_variables(s_content, recipient_data)
                
            sections_html_parts.append(f'''
        <div style="margin: 24px 0; text-align: center;">
          <a href="{s_button_url}" style="
            background-color: {BRAND['primary']};
            color: #ffffff;
            padding: 14px 32px;
            border-radius: 8px;
            text-decoration: none;
            display: block;
            width: 100%;
            box-sizing: border-box;
            font-weight: 600;
            font-size: 16px;
            text-align: center;
          ">{button_text}</a>
        </div>
            ''')
            
        else:
            # Text Section
            final_text = ""
            
            if s_mode == 'personalized':
                if generated_content and s_id in generated_content:
                    final_text = generated_content[s_id]
                else:
                    # Fallback if no content generated (shouldn't happen in prod flow)
                    final_text = f"[{s_name} - Missing Content]" 
            else:
                final_text = replace_variables(s_content, recipient_data)
                
            # Formatting (Line breaks to <br>)
            # TypeScript used split.map.join
            paragraphs = final_text.split('\n\n')
            p_htmls = []
            for p in paragraphs:
                processed = p.replace('\n', '<br>')
                # Simple bold replacement if needed, but usually AI returns plain text or we allow markdown-ish?
                # The TS code did some regex replacing for <strong> and <a href>.
                # We can replicate that simply.
                processed = re.sub(r'<strong>(.*?)</strong>', r'<strong>\1</strong>', processed)
                # Link handling might stay as is if user inputs HTML, but primarily we expect plain text from AI
                
                p_htmls.append(f'<p style="margin: 0 0 16px 0; font-size: 15px; color: {BRAND["textMuted"]}; line-height: 1.6;">{processed}</p>')
                
            sections_html_parts.append(''.join(p_htmls))
            
    sections_html = ''.join(sections_html_parts)
    
    # Full Template
    return f'''
<!DOCTYPE html>
<html>
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1.0">
  <title>{processed_subject}</title>
</head>
<body style="
  font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, 'Helvetica Neue', Arial, sans-serif, 'Apple Color Emoji', 'Segoe UI Emoji', 'Segoe UI Symbol';
  background-color: {BRAND['bgLight']};
  margin: 0;
  padding: 16px 0;
  font-size: 15px;
  line-height: 1.6;
">
  <div style="
    width: 100%;
    max-width: 640px;
    margin: 0 auto;
    background-color: {BRAND['bgCard']};
    border-radius: 16px;
    border: 1px solid {BRAND['border']};
    overflow: hidden;
    box-shadow: 0 18px 45px rgba(15, 23, 42, 0.08), 0 8px 20px rgba(15, 23, 42, 0.06);
  ">
    <!-- Header -->
    <div style="
      background-color: {BRAND['primary']};
      padding: 18px 20px;
    ">
      <table cellpadding="0" cellspacing="0" border="0" width="100%">
        <tr>
          <td width="140" valign="middle">
            <img 
              src="https://ozlistings.com/oz-listings-horizontal2-logo-white.webp" 
              alt="OZListings" 
              width="140" 
              height="32" 
              style="display: block; max-width: 140px; height: auto;"
            >
          </td>
          <td valign="middle" style="padding-left: 12px;">
            <div style="
              margin: 0;
              font-size: 11px;
              letter-spacing: 0.14em;
              text-transform: uppercase;
              color: {BRAND['primaryLight']};
            ">OZListings</div>
            <div style="
              margin: 2px 0 0 0;
              font-size: 18px;
              line-height: 1.4;
              color: #ffffff;
              font-weight: 800;
            ">{processed_subject or 'Email Preview'}</div>
          </td>
        </tr>
      </table>
    </div>

    <!-- Main Content -->
    <div style="padding: 20px 20px 18px 20px;">
      {sections_html or '<p style="color: #9ca3af; font-style: italic;">No content available</p>'}
    </div>

    <!-- Footer -->
    <div style="
      border-top: 1px solid {BRAND['border']};
      padding: 12px 24px 20px 24px;
      background-color: {BRAND['bgFooter']};
    ">
      <p style="
        margin: 0 0 4px 0;
        font-size: 11px;
        color: {BRAND['textLight']};
      ">
        This email was sent to you because you're listed as a developer with
        an Opportunity Zone project. If you'd prefer not to receive these
        emails, you can <a href="{unsubscribe_url}" style="color: {BRAND['primary']}; text-decoration: underline;">unsubscribe</a>.
      </p>
      <p style="
        margin: 0;
        font-size: 11px;
        color: {BRAND['textLight']};
      ">
        © 2024 OZListings. All rights reserved.
      </p>
    </div>
  </div>
</body>
</html>
'''


def generate_email_text(
    sections: List[Dict[str, Any]],
    subject_line: str,
    recipient_data: Dict[str, Any],
    generated_content: Optional[Dict[str, str]] = None
) -> str:
    """Generate a plain text email body."""
    processed_subject = replace_variables(subject_line, recipient_data)
    unsubscribe_url = generate_unsubscribe_url(recipient_data.get('Email', ''))

    lines: List[str] = []

    for section in sections:
        s_type = section.get('type', 'text')
        s_mode = section.get('mode', 'static')
        s_id = section.get('id', '')
        s_name = section.get('name', '')
        s_content = section.get('content', '')
        s_button_url = section.get('buttonUrl', '')

        if s_type == 'button':
            # Render CTA as text line
            button_text = s_content
            if s_mode == 'personalized':
                button_text = (
                    generated_content.get(s_id)
                    if generated_content and s_id in generated_content
                    else f"[{s_name} - AI Generated]"
                )
            else:
                button_text = replace_variables(s_content, recipient_data)

            lines.append(f"{button_text} -> {s_button_url or 'https://'}")
            continue

        # Text sections
        if s_mode == 'personalized':
            final_text = (
                generated_content.get(s_id)
                if generated_content and s_id in generated_content
                else f"[{s_name} - Missing Content]"
            )
        else:
            final_text = replace_variables(s_content, recipient_data)

        # Preserve paragraph breaks with blank lines
        paragraphs = final_text.split('\n\n')
        for p in paragraphs:
            # Strip any stray HTML tags to keep text clean
            cleaned = re.sub(r'<[^>]+>', '', p)
            lines.append(cleaned)
        # Add a blank line between sections
        lines.append("")

    # Footer
    lines.append("")
    lines.append("----")
    lines.append(f"To unsubscribe, visit: {unsubscribe_url}")

    # Remove trailing blank lines
    while lines and lines[-1] == "":
        lines.pop()

    return "\n".join(lines)
