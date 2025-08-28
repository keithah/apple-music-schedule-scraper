#!/usr/bin/env python3
"""Debug script to see exactly what times we're getting from Apple Música Uno"""

from playwright.sync_api import sync_playwright
from bs4 import BeautifulSoup
import re

def debug_apple_musica_uno():
    print("🔍 Debugging Apple Música Uno schedule extraction...")
    
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        context = browser.new_context(
            timezone_id='America/Los_Angeles',
            locale='en-US'
        )
        page = context.new_page()
        
        # Navigate to Apple Música Uno
        url = "https://music.apple.com/radio/ra.1740613864"
        page.goto(url, wait_until="networkidle")
        page.wait_for_timeout(5000)
        
        # Get the page content
        html = page.content()
        soup = BeautifulSoup(html, 'html.parser')
        
        # Look for schedule items using the same selectors as the main scraper
        selectors = [
            '[data-testid*="schedule"]',
            '[data-testid*="show"]', 
            '[data-testid*="program"]',
            '[data-testid*="episode"]',
            '[data-testid*="track"]',
            '.schedule-item',
            '.show-item',
            '[class*="schedule"]',
            '[class*="show"]',
            '[class*="program"]',
            '[class*="episode"]',
            '[class*="track-list"]',
            '[class*="content-item"]',
            '[class*="media-item"]',
            '[class*="item"][class*="list"]',
            '[class*="item"]:not([class*="nav"])',
            'li[role="listitem"]',
            'article',
            'section > div > div'
        ]
        
        schedule_items = []
        for selector in selectors:
            items = soup.select(selector)
            if items and len(items) > 1:
                schedule_items = items
                print(f"✅ Using selector: {selector} (found {len(items)} items)")
                break
        
        if not schedule_items:
            print("❌ No schedule items found with standard selectors")
            return
        
        print(f"\n📋 Found {len(schedule_items)} potential schedule items")
        print("="*80)
        
        # Time extraction patterns (same as main scraper)
        patterns = [
            r'(\d{1,2}:\d{2}\s*(?:AM|PM)?\s*[–-]\s*\d{1,2}:\d{2}\s*(?:AM|PM))',  # 7:05 PM - 9:00 PM
            r'(\d{1,2}:\d{2}\s*[–-]\s*\d{1,2}:\d{2}\s*(?:AM|PM))',              # 7:05 - 9:00 PM  
            r'(\d{1,2}:\d{2}\s*(?:AM|PM)?\s*[–-]\s*\d{1,2}\s*(?:AM|PM))',        # 7:05 PM - 9 AM
            r'(\d{1,2}\s*(?:AM|PM)\s*[–-]\s*\d{1,2}\s*(?:AM|PM))',              # 11PM - 12AM
            r'(\d{1,2}:\d{2}\s*[–-]\s*\d{1,2}\s*(?:AM|PM))',                    # 7:05 - 9 PM
            r'(\d{1,2}\s*[–-]\s*\d{1,2}:\d{2}\s*(?:AM|PM))',                    # 7 - 9:00 PM
            r'(\d{1,2}\s*[–-]\s*\d{1,2}\s*(?:AM|PM))'                           # 7 - 9 PM
        ]
        
        extracted_shows = []
        
        for i, item in enumerate(schedule_items):
            full_text = item.get_text(separator=' ', strip=True)
            
            # Clean LIVE prefix
            full_text_clean = re.sub(r'^LIVE\s*[·•]?\s*', '', full_text, flags=re.I)
            
            # Try to extract time slot
            time_slot = None
            for pattern in patterns:
                matches = re.findall(pattern, full_text, re.I)
                if matches:
                    time_slot = max(matches, key=len)  # Get the longest match
                    break
                matches_clean = re.findall(pattern, full_text_clean, re.I) 
                if matches_clean:
                    time_slot = max(matches_clean, key=len)
                    break
            
            if time_slot:
                # Extract show title from HTML elements
                title_elements = item.select('strong, b, [class*="title"], [class*="heading"], h1, h2, h3, h4, h5, h6')
                title = None
                
                for elem in title_elements:
                    candidate = elem.get_text(strip=True)
                    if candidate and not re.match(r'^\d{1,2}\s*[–-]\s*\d{1,2}\s*(AM|PM)$', candidate, re.I):
                        title = candidate
                        break
                
                if not title:
                    # Fallback: extract from full text
                    words = full_text_clean.split()
                    for word in words:
                        if not re.match(r'^\d', word) and len(word) > 2:
                            title = word
                            break
                
                extracted_shows.append({
                    'time_slot': time_slot,
                    'title': title or 'Unknown',
                    'full_text': full_text[:100] + '...' if len(full_text) > 100 else full_text
                })
                
                print(f"🎵 Show {len(extracted_shows)}:")
                print(f"   Time: {time_slot}")
                print(f"   Title: {title or 'Unknown'}")
                print(f"   Raw text: {full_text[:150]}{'...' if len(full_text) > 150 else ''}")
                print()
        
        context.close()
        browser.close()
        
        print(f"\n📊 SUMMARY: Extracted {len(extracted_shows)} shows")
        print("="*80)
        
        # Sort by time for easier comparison
        for show in sorted(extracted_shows, key=lambda x: x['time_slot']):
            print(f"{show['time_slot']} - {show['title']}")

if __name__ == "__main__":
    debug_apple_musica_uno()