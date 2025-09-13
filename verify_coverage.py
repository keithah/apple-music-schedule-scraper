#!/usr/bin/env python3
"""Verify 24-hour coverage for each station"""

import pandas as pd
import re
from datetime import datetime, timedelta

def parse_time_to_minutes(time_str):
    """Convert time string to minutes since midnight"""
    if not time_str:
        return -1
    
    time_str = time_str.strip().upper()
    
    # Try 24-hour format first (HH:MM)
    match_24h = re.match(r'(\d{1,2}):(\d{2})', time_str)
    if match_24h:
        hour = int(match_24h.group(1))
        minute = int(match_24h.group(2))
        return hour * 60 + minute
    
    # Fallback to 12-hour format
    match = re.match(r'(\d{1,2})(?::(\d{2}))?\s*(AM|PM)', time_str)
    if not match:
        return -1
    
    hour = int(match.group(1))
    minute = int(match.group(2) or 0)
    period = match.group(3)
    
    if period == 'PM' and hour != 12:
        hour += 12
    elif period == 'AM' and hour == 12:
        hour = 0
    
    return hour * 60 + minute

def verify_station_coverage(df, station_name):
    """Verify 24-hour coverage for a station"""
    station_shows = df[df['station'] == station_name].copy()
    
    # Skip gap entries
    station_shows = station_shows[~station_shows['show_title'].str.contains('MISSING', na=False)]
    
    print(f"\n=== {station_name} ===")
    print(f"Total shows (excluding gaps): {len(station_shows)}")
    
    # Parse all time slots
    show_times = []
    for _, show in station_shows.iterrows():
        time_slot = show['time_slot_utc']  # Use UTC times
        if not time_slot or 'MISSING' in str(show['show_title']):
            continue
            
        # Extract start and end times - handle both 24h and 12h formats
        time_match = re.search(r'(\d{1,2}:\d{2})\s*[–-]\s*(\d{1,2}:\d{2})', time_slot, re.I)
        if not time_match:
            # Fallback to 12-hour format
            time_match = re.search(r'(\d{1,2}(?::\d{2})?\s*(?:AM|PM)?)\s*[–-]\s*(\d{1,2}(?::\d{2})?\s*(?:AM|PM))', time_slot, re.I)
        if time_match:
            start_str = time_match.group(1).strip()
            end_str = time_match.group(2).strip()
            
            # Handle missing AM/PM
            if 'AM' not in end_str.upper() and 'PM' not in end_str.upper():
                if 'AM' in start_str.upper():
                    end_str += 'AM'
                elif 'PM' in start_str.upper():
                    end_str += 'PM'
            
            start_minutes = parse_time_to_minutes(start_str)
            end_minutes = parse_time_to_minutes(end_str)
            
            # Handle day rollover
            if end_minutes < start_minutes:
                end_minutes += 24 * 60
            
            show_times.append({
                'title': show['show_title'],
                'time_slot': time_slot,
                'start': start_minutes,
                'end': end_minutes,
                'duration': end_minutes - start_minutes
            })
    
    # Sort by start time
    show_times.sort(key=lambda x: x['start'])
    
    # Check coverage
    total_coverage = 0
    gaps = []
    
    for i, show in enumerate(show_times):
        total_coverage += show['duration']
        
        # Check for gaps
        if i < len(show_times) - 1:
            next_show = show_times[i + 1]
            gap = next_show['start'] - show['end']
            
            if gap > 5:  # More than 5 minutes gap
                gap_start_hour = show['end'] // 60
                gap_start_min = show['end'] % 60
                gap_end_hour = next_show['start'] // 60
                gap_end_min = next_show['start'] % 60
                
                gaps.append({
                    'gap_minutes': gap,
                    'after_show': show['title'],
                    'before_show': next_show['title'],
                    'gap_time': f"{gap_start_hour:02d}:{gap_start_min:02d} - {gap_end_hour:02d}:{gap_end_min:02d}"
                })
    
    print(f"Total coverage: {total_coverage} minutes ({total_coverage/60:.1f} hours)")
    print(f"Expected: 1440 minutes (24 hours)")
    print(f"Coverage: {(total_coverage/1440)*100:.1f}%")
    
    if gaps:
        print(f"\nGaps found ({len(gaps)}):")
        for gap in gaps:
            print(f"  - {gap['gap_minutes']} min gap at {gap['gap_time']} (between '{gap['after_show']}' and '{gap['before_show']}')")
    else:
        print("\nNo significant gaps found!")
    
    # Show first few and last few shows
    print(f"\nFirst 5 shows:")
    for show in show_times[:5]:
        start_h, start_m = show['start'] // 60, show['start'] % 60
        end_h, end_m = show['end'] // 60, show['end'] % 60
        print(f"  {start_h:02d}:{start_m:02d}-{end_h:02d}:{end_m:02d} ({show['duration']}min) - {show['title']}")
    
    print(f"\nLast 5 shows:")
    for show in show_times[-5:]:
        start_h, start_m = show['start'] // 60, show['start'] % 60
        end_h, end_m = show['end'] // 60, show['end'] % 60
        print(f"  {start_h:02d}:{start_m:02d}-{end_h:02d}:{end_m:02d} ({show['duration']}min) - {show['title']}")
    
    return total_coverage >= 1430  # Allow for small gaps

def main():
    df = pd.read_csv('apple_music_schedule.csv')
    
    stations = df['station'].unique()
    print(f"Checking coverage for {len(stations)} stations...")
    
    all_good = True
    for station in stations:
        is_covered = verify_station_coverage(df, station)
        if not is_covered:
            all_good = False
    
    print(f"\n{'='*50}")
    if all_good:
        print("✅ All stations appear to have 24-hour coverage!")
        print("The gap detection may be too aggressive.")
    else:
        print("❌ Some stations have significant gaps.")
        print("Gap detection is working correctly.")

if __name__ == "__main__":
    main()