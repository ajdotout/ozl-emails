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


def generate_unsubscribe_url(email: str) -> str:
    """Generate a signed unsubscribe URL."""
    secret = Config.UNSUBSCRIBE_SECRET.encode('utf-8')
    msg = email.lower().encode('utf-8')
    
    token = hmac.new(secret, msg, hashlib.sha256).hexdigest()[:16]
    base_url = Config.FRONTEND_URL
    
    params = urlencode({'email': email, 'token': token})
    return f"{base_url}/api/unsubscribe?{params}"


def generate_email_html(
    sections: List[Dict[str, Any]],
    subject_line: str,
    recipient_data: Dict[str, Any],
    generated_content: Optional[Dict[str, str]] = None
) -> str:
    """Generate the full email HTML."""
    from shared.email import replace_variables
    
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
            button_text = s_content
            if s_mode == 'personalized':
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
            final_text = ""
            
            if s_mode == 'personalized':
                if generated_content and s_id in generated_content:
                    final_text = generated_content[s_id]
                else:
                    final_text = f"[{s_name} - Missing Content]" 
            else:
                final_text = replace_variables(s_content, recipient_data)
                
            paragraphs = final_text.split('\n\n')
            p_htmls = []
            for p in paragraphs:
                processed = p.replace('\n', '<br>')
                processed = re.sub(r'<strong>(.*?)</strong>', r'<strong>\1</strong>', processed)
                p_htmls.append(f'<p style="margin: 0 0 16px 0; font-size: 15px; color: {BRAND["textMuted"]}; line-height: 1.6;">{processed}</p>')
                
            sections_html_parts.append(''.join(p_htmls))
            
    sections_html = ''.join(sections_html_parts)
    
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

    <div style="padding: 20px 20px 18px 20px;">
      {sections_html or '<p style="color: #9ca3af; font-style: italic;">No content available</p>'}
    </div>

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
    from shared.email import replace_variables
    
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

        if s_mode == 'personalized':
            final_text = (
                generated_content.get(s_id)
                if generated_content and s_id in generated_content
                else f"[{s_name} - Missing Content]"
            )
        else:
            final_text = replace_variables(s_content, recipient_data)

        paragraphs = final_text.split('\n\n')
        for p in paragraphs:
            cleaned = re.sub(r'<[^>]+>', '', p)
            lines.append(cleaned)
        lines.append("")

    lines.append("")
    lines.append("----")
    lines.append(f"To unsubscribe, visit: {unsubscribe_url}")

    while lines and lines[-1] == "":
        lines.pop()

    return "\r\n".join(lines)

