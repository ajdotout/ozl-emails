from fastapi import APIRouter, Request, HTTPException
from pydantic import BaseModel
from typing import List
import logging
from shared.webhook_processor import record_bounce, record_unsubscribe, record_spam_complaint, record_delivered

router = APIRouter()

# Commenting out strict Pydantic models to accept raw payloads for debugging
# class SparkPostEvent(BaseModel):
#     event_type: str
#     recipient: str
#     metadata: dict
#     timestamp: str
#     fb_source: str = None  # For spam complaints
#     fb_type: str = None    # For spam complaints
#
# class WebhookPayload(BaseModel):
#     events: List[SparkPostEvent]

@router.post("/sparkpost")
async def sparkpost_webhook(request: Request):
    """Handle SparkPost webhooks - processing actual SparkPost format"""

    try:
        # Get raw payload
        payload = await request.json()

        # Uncomment and fix processing logic now that we know the payload format
        # Verify webhook signature (if configured)
        # verify_webhook_signature(request)

        processed = 0
        errors = 0

        # SparkPost sends an array of events
        if isinstance(payload, list):
            events_to_process = payload
        else:
            events_to_process = [payload]

        for event_wrapper in events_to_process:
            try:
                # Extract the actual event data from the nested structure
                if 'msys' in event_wrapper:
                    msys_data = event_wrapper['msys']

                    # Determine which type of event this is
                    if 'message_event' in msys_data:
                        event_data = msys_data['message_event']
                    elif 'track_event' in msys_data:
                        event_data = msys_data['track_event']
                    elif 'unsubscribe_event' in msys_data:
                        event_data = msys_data['unsubscribe_event']
                    else:
                        logging.warning(f"Unknown event structure: {event_wrapper}")
                        errors += 1
                        continue

                    # Extract event type
                    event_type = event_data.get('type')
                    if not event_type:
                        logging.warning(f"No type field in event: {event_data}")
                        errors += 1
                        continue

                    # Log event type received
                    print(f"📧 Event type received: {event_type}")

                    # Extract recipient email (handle different event types)
                    recipient = None
                    if event_type in ['bounce', 'unsubscribe', 'spam_complaint', 'delivery', 'click', 'open', 'initial_open']:
                        # Email events
                        recipient = event_data.get('rcpt_to') or event_data.get('raw_rcpt_to')
                    elif event_type == 'sms_status':
                        # SMS events - use phone number as recipient
                        recipient = event_data.get('sms_dst')
                    # Other events might not need recipients (like injection, delay, etc.)

                    # Skip events that require recipients but don't have them
                    if event_type in ['bounce', 'unsubscribe', 'spam_complaint', 'delivery', 'click', 'open', 'initial_open'] and not recipient:
                        errors += 1
                        continue

                    # Extract campaign_id (may not be present for all event types)
                    campaign_id = event_data.get('campaign_id')

                    # Parse campaign_id to extract UUID if it's in "name - uuid" format
                    if campaign_id and " - " in campaign_id:
                        # Split on " - " and take the last part (the UUID)
                        campaign_id = campaign_id.split(" - ")[-1]

                    # For events that need campaign_id (bounces, unsubscribes, etc.)
                    email_events_requiring_campaign = ['bounce', 'unsubscribe', 'spam_complaint', 'delivery', 'click', 'open', 'initial_open']
                    if event_type in email_events_requiring_campaign and not campaign_id:
                        errors += 1
                        continue

                    # Process based on event type
                    try:
                        if event_type == "bounce":
                            print(f"🔍 Processing bounce: campaign_id={campaign_id}, recipient={recipient}")
                            await record_bounce(campaign_id, recipient, event_data)
                        elif event_type == "unsubscribe":
                            # Could be list_unsubscribe or link_unsubscribe
                            await record_unsubscribe(campaign_id, recipient, event_data)
                        elif event_type == "spam_complaint":
                            await record_spam_complaint(campaign_id, recipient, event_data)
                        elif event_type == "delivery":
                            await record_delivered(campaign_id, recipient, event_data)
                        else:
                            # Event type received but not processed
                            pass

                        processed += 1
                    except Exception as e:
                        # Log error but continue processing other events
                        print(f"❌ Error processing {event_type}: {e}")
                        errors += 1
                        continue

                else:
                    errors += 1

            except Exception as e:
                print(f"❌ Error processing event: {e}")
                errors += 1

        return {
            "status": "processed",
            "events_processed": processed,
            "errors": errors
        }

    except Exception as e:
        print(f"❌ Webhook error: {e}")
        return {
            "status": "error",
            "message": f"Failed to process webhook: {str(e)}"
        }

