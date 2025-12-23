"""Scheduling utilities for email campaigns."""

from datetime import datetime, timedelta
from zoneinfo import ZoneInfo
from typing import Dict, List, Tuple
from config import Config


BASE_DOMAINS = [
    # Original 7 domains
    'connect-ozlistings.com',
    'engage-ozlistings.com',
    'get-ozlistings.com',
    'join-ozlistings.com',
    'outreach-ozlistings.com',
    'ozlistings-reach.com',
    'reach-ozlistings.com',
    # New warmed domains
    'access-ozlistings.com',
    'contact-ozlistings.com',
    'direct-ozlistings.com',
    'grow-ozlistings.com',
    'growth-ozlistings.com',
    'link-ozlistings.com',
    'network-ozlistings.com',
    'ozlistings-access.com',
    'ozlistings-connect.com',
    'ozlistings-contact.com',
    'ozlistings-direct.com',
    'ozlistings-engage.com',
    'ozlistings-get.com',
    'ozlistings-grow.com',
    'ozlistings-join.com',
    'ozlistings-link.com',
    'ozlistings-network.com',
    'ozlistings-outreach.com',
    'ozlistings-team.com',
    'ozlistngs-growth.com',
    'team-ozlistings.com',
]


def generate_domain_config(sender: str) -> List[Dict[str, str]]:
    """Generate domain configuration for a sender.
    
    Args:
        sender: 'todd_vitzthum' or 'jeff_richmond'
        
    Returns:
        List of domain config dictionaries
    """
    sender_local = 'todd.vitzthum' if sender == 'todd_vitzthum' else 'jeff.richmond'
    display_name = 'Todd Vitzthum' if sender == 'todd_vitzthum' else 'Jeff Richmond'

    return [
        {
            'domain': domain,
            'sender_local': sender_local,
            'display_name': display_name,
        }
        for domain in BASE_DOMAINS
    ]


def create_date_in_timezone(
    timezone: str,
    year: int,
    month: int,
    day: int,
    hour: int,
    minute: int = 0,
    second: int = 0
) -> datetime:
    """Create a datetime in the specified timezone."""
    tz = ZoneInfo(timezone)
    local_dt = datetime(year, month, day, hour, minute, second, tzinfo=tz)
    return local_dt.astimezone(ZoneInfo("UTC"))


def next_weekday_start(
    zoned_time: datetime,
    timezone: str,
    working_hour_start: int,
    skip_weekends: bool = True
) -> datetime:
    """Get the next weekday start time."""
    # Ensure zoned_time is in the target timezone
    tz = ZoneInfo(timezone)
    if zoned_time.tzinfo is None:
        zoned_time = zoned_time.replace(tzinfo=ZoneInfo("UTC")).astimezone(tz)
    elif zoned_time.tzinfo != tz:
        zoned_time = zoned_time.astimezone(tz)
    
    next_day = zoned_time.replace(hour=0, minute=0, second=0, microsecond=0)
    next_day += timedelta(days=1)

    # Advance past weekend if needed
    if skip_weekends:
        while next_day.weekday() >= 5:  # Saturday = 5, Sunday = 6
            next_day += timedelta(days=1)

    return create_date_in_timezone(
        timezone,
        next_day.year,
        next_day.month,
        next_day.day,
        working_hour_start
    )


def get_start_time_in_timezone(
    timezone: str,
    working_hour_start: int,
    working_hour_end: int,
    skip_weekends: bool = True
) -> datetime:
    """Get the start time for scheduling in the specified timezone."""
    now_utc = datetime.now(ZoneInfo("UTC"))
    tz = ZoneInfo(timezone)
    zoned_time = now_utc.astimezone(tz)
    
    # Ensure we're working with timezone-aware datetime
    if zoned_time.tzinfo is None:
        zoned_time = zoned_time.replace(tzinfo=tz)

    # If weekend, start next weekday at start hour
    if skip_weekends and zoned_time.weekday() >= 5:
        return next_weekday_start(zoned_time, timezone, working_hour_start, skip_weekends)

    hour = zoned_time.hour
    if hour < working_hour_start:
        return create_date_in_timezone(
            timezone,
            zoned_time.year,
            zoned_time.month,
            zoned_time.day,
            working_hour_start
        )
    elif hour >= working_hour_end:
        return next_weekday_start(zoned_time, timezone, working_hour_start, skip_weekends)
    else:
        return create_date_in_timezone(
            timezone,
            zoned_time.year,
            zoned_time.month,
            zoned_time.day,
            zoned_time.hour,
            zoned_time.minute,
            zoned_time.second
        )


def adjust_to_working_hours(
    candidate_time: datetime,
    timezone: str,
    working_hour_end: int,
    working_hour_start: int,
    skip_weekends: bool = True
) -> datetime:
    """Adjust a candidate time to be within working hours."""
    tz = ZoneInfo(timezone)
    # Ensure candidate_time is timezone-aware
    if candidate_time.tzinfo is None:
        candidate_time = candidate_time.replace(tzinfo=ZoneInfo("UTC"))
    zoned_time = candidate_time.astimezone(tz)

    # Weekend => next weekday start
    if skip_weekends and zoned_time.weekday() >= 5:
        return next_weekday_start(zoned_time, timezone, working_hour_start, skip_weekends)

    boundary_end = create_date_in_timezone(
        timezone,
        zoned_time.year,
        zoned_time.month,
        zoned_time.day,
        working_hour_end
    )

    if candidate_time >= boundary_end:
        return next_weekday_start(zoned_time, timezone, working_hour_start, skip_weekends)

    return candidate_time

