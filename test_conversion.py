#!/usr/bin/env python3
"""Test the UTC to Pacific conversion logic"""

import sys
sys.path.append('.')

from scrape_apple_music_schedule import AppleMusicScheduleScraper

def test_conversion():
    scraper = AppleMusicScheduleScraper()
    
    # Test cases from your screenshot
    test_cases = [
        "5 – 7 AM",      # Should become 10PM - 12AM Pacific (5AM UTC - 7 hours = 10PM previous day)
        "10PM – 12AM",   # Should become 3PM - 5PM Pacific
        "4 – 5 AM",      # Should become 9PM - 10PM Pacific (previous day)
        "1 – 3 AM",      # Should become 6PM - 8PM Pacific (previous day)
        "7 – 9 AM",      # Should become 12AM - 2AM Pacific
        "12 – 1 AM",     # Should become 5PM - 6PM Pacific (previous day)
    ]
    
    print("🔍 Testing UTC to Pacific conversion:")
    print("="*60)
    
    for utc_time in test_cases:
        pacific_time = scraper._convert_utc_to_pacific(utc_time)
        print(f"UTC: {utc_time:12} → Pacific: {pacific_time}")
    
    print("\nNote: We are in PDT (UTC-7) during summer")

if __name__ == "__main__":
    test_conversion()
