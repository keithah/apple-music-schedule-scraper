#!/usr/bin/env python3
"""Test the UTC to Pacific time conversion logic"""

import re
import pytz
from datetime import datetime

def _parse_time_component(time_str: str):
    """Parse a time component like '7:05 PM' or '11PM' into hour, minute, period."""
    time_str = time_str.strip()
    
    # Check for AM/PM attached to time
    am_pm_match = re.match(r'(\d{1,2})(?::(\d{2}))?(?:\s*)?(AM|PM)', time_str, re.I)
    if am_pm_match:
        hour = int(am_pm_match.group(1))
        minute = int(am_pm_match.group(2) or 0)
        period = am_pm_match.group(3).upper()
        return hour, minute, period
        
    # Just numbers without AM/PM
    num_match = re.match(r'(\d{1,2})(?::(\d{2}))?', time_str)
    if num_match:
        hour = int(num_match.group(1))
        minute = int(num_match.group(2) or 0)
        return hour, minute, None
        
    return None, None, None

def convert_utc_to_pacific(time_slot_utc: str) -> str:
    """Convert UTC time slot to Pacific time."""
    if not time_slot_utc:
        return None
        
    print(f"Input UTC time: {time_slot_utc}")
    
    # Parse the time range
    pattern = r'(\d{1,2}(?::\d{2})?)\s*[–-]\s*(\d{1,2}(?::\d{2})?\s*(?:AM|PM))'
    match = re.match(pattern, time_slot_utc, re.I)
    
    if not match:
        print("No match found")
        return time_slot_utc
        
    start_str = match.group(1)
    end_str = match.group(2)
    print(f"Parsed: start='{start_str}', end='{end_str}'")
    
    # Parse components
    start_hour, start_min, start_period = _parse_time_component(start_str)
    end_hour, end_min, end_period = _parse_time_component(end_str)
    print(f"Start: {start_hour}:{start_min:02d} {start_period}")
    print(f"End: {end_hour}:{end_min:02d} {end_period}")
    
    # Infer start period from end period
    if start_period is None and end_period:
        # Special case: if start is 12 and end is AM, start should also be AM (midnight)
        if start_hour == 12 and end_period == 'AM':
            start_period = 'AM'
        # Special case: if start is 12 and end is PM, start should also be PM (noon)  
        elif start_hour == 12 and end_period == 'PM':
            start_period = 'PM'
        elif start_hour > end_hour:
            # Spans midnight, start is previous period
            start_period = 'AM' if end_period == 'PM' else 'PM'
        else:
            # Same period
            start_period = end_period
    
    print(f"After inference - Start: {start_hour}:{start_min:02d} {start_period}")
    
    # Convert to 24-hour format
    if start_period == 'PM' and start_hour != 12:
        start_hour_24 = start_hour + 12
    elif start_period == 'AM' and start_hour == 12:
        start_hour_24 = 0
    else:
        start_hour_24 = start_hour
        
    if end_period == 'PM' and end_hour != 12:
        end_hour_24 = end_hour + 12
    elif end_period == 'AM' and end_hour == 12:
        end_hour_24 = 0
    else:
        end_hour_24 = end_hour
    
    print(f"24-hour UTC: {start_hour_24}:{start_min:02d} - {end_hour_24}:{end_min:02d}")
    
    # Apply Pacific Time offset
    pacific_tz = pytz.timezone('America/Los_Angeles')
    now = datetime.now(pacific_tz)
    is_dst = bool(now.dst())
    offset = 7 if is_dst else 8
    print(f"Offset: -{offset} hours (DST: {is_dst})")
    
    # Subtract offset
    start_hour_pacific = start_hour_24 - offset
    if start_hour_pacific < 0:
        start_hour_pacific += 24
        
    end_hour_pacific = end_hour_24 - offset
    if end_hour_pacific < 0:
        end_hour_pacific += 24
    
    print(f"24-hour Pacific: {start_hour_pacific}:{start_min:02d} - {end_hour_pacific}:{end_min:02d}")
    
    # Convert back to 12-hour format
    # Start time
    if start_hour_pacific == 0:
        display_start_hour = 12
        start_period_pacific = 'AM'
    elif start_hour_pacific < 12:
        display_start_hour = start_hour_pacific
        start_period_pacific = 'AM'
    elif start_hour_pacific == 12:
        display_start_hour = 12
        start_period_pacific = 'PM'
    else:
        display_start_hour = start_hour_pacific - 12
        start_period_pacific = 'PM'
        
    # End time
    if end_hour_pacific == 0:
        display_end_hour = 12
        end_period_pacific = 'AM'
    elif end_hour_pacific < 12:
        display_end_hour = end_hour_pacific
        end_period_pacific = 'AM'
    elif end_hour_pacific == 12:
        display_end_hour = 12
        end_period_pacific = 'PM'
    else:
        display_end_hour = end_hour_pacific - 12
        end_period_pacific = 'PM'
    
    print(f"12-hour Pacific: {display_start_hour}:{start_min:02d} {start_period_pacific} - {display_end_hour}:{end_min:02d} {end_period_pacific}")
    
    # Format result
    if start_period_pacific == end_period_pacific:
        # Same period - only show AM/PM on end time
        if start_min > 0:
            start_formatted = f"{display_start_hour}:{start_min:02d}"
        else:
            start_formatted = f"{display_start_hour}"
            
        if end_min > 0:
            end_formatted = f"{display_end_hour}:{end_min:02d}{end_period_pacific}"
        else:
            end_formatted = f"{display_end_hour}{end_period_pacific}"
    else:
        # Different periods - show AM/PM on both times
        if start_min > 0:
            start_formatted = f"{display_start_hour}:{start_min:02d}{start_period_pacific}"
        else:
            start_formatted = f"{display_start_hour}{start_period_pacific}"
            
        if end_min > 0:
            end_formatted = f"{display_end_hour}:{end_min:02d}{end_period_pacific}"
        else:
            end_formatted = f"{display_end_hour}{end_period_pacific}"
    
    result = f"{start_formatted} – {end_formatted}"
    print(f"Final result: {result}")
    return result

# Test the problematic case
print("=== Testing UTC '12 – 2 AM' (should become Pacific '5 – 7 PM') ===")
result1 = convert_utc_to_pacific("12 – 2 AM")
print()

print("=== Testing UTC '12 – 1 PM' (should become Pacific '5 – 6 AM') ===") 
result2 = convert_utc_to_pacific("12 – 1 PM")
print()