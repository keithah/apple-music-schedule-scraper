#!/usr/bin/env python3
"""Debug script to check what HTML we're getting from Apple Music"""

from playwright.sync_api import sync_playwright
from bs4 import BeautifulSoup
import re

def fetch_and_debug(url):
    print(f"\n{'='*60}")
    print(f"Fetching: {url}")
    print('='*60)
    
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        context = browser.new_context(
            timezone_id='America/Los_Angeles',
            locale='en-US'
        )
        page = context.new_page()
        
        # Navigate to the page
        page.goto(url, wait_until="networkidle")
        
        # Wait for content
        page.wait_for_timeout(5000)
        
        # Try to wait for actual content
        try:
            page.wait_for_selector('[class*="item"], [class*="show"], [role="listitem"]', timeout=10000)
        except:
            print("WARNING: Could not find expected selectors")
        
        # Get the page content
        html = page.content()
        
        # Parse with BeautifulSoup
        soup = BeautifulSoup(html, 'html.parser')
        
        # Look for time patterns in the HTML
        time_pattern = re.compile(r'\d{1,2}(?::\d{2})?\s*(?:AM|PM)?\s*[–-]\s*\d{1,2}(?::\d{2})?\s*(?:AM|PM)', re.I)
        
        # Find all text containing time patterns
        time_elements = soup.find_all(string=time_pattern)
        
        print(f"\nFound {len(time_elements)} elements with time patterns:")
        for i, elem in enumerate(time_elements[:5]):  # Show first 5
            parent = elem.parent
            full_text = parent.get_text(strip=True)[:200] if parent else elem[:200]
            print(f"\n{i+1}. Time found: {elem.strip()}")
            print(f"   Parent text: {full_text}")
        
        # Check what selectors we're finding
        selectors_to_test = [
            '[data-testid]',
            '[class*="schedule"]',
            '[class*="show"]',
            '[class*="item"]',
            'li',
            'article'
        ]
        
        print("\n\nSelector matches:")
        for selector in selectors_to_test:
            elements = soup.select(selector)
            print(f"{selector}: {len(elements)} elements")
            
            # Check if any contain time patterns
            with_times = 0
            for elem in elements:
                if time_pattern.search(elem.get_text()):
                    with_times += 1
            if with_times > 0:
                print(f"  -> {with_times} contain time patterns")
        
        # Look for Dale Play specifically
        dale_play_elements = soup.find_all(string=re.compile(r'dale\s*play', re.I))
        print(f"\n\nSearching for 'Dale Play':")
        print(f"Found {len(dale_play_elements)} elements containing 'Dale Play':")
        for i, elem in enumerate(dale_play_elements):
            parent = elem.parent
            full_text = parent.get_text(strip=True)[:300] if parent else elem[:300]
            print(f"\n{i+1}. Dale Play found: '{elem.strip()}'")
            print(f"   Parent text: {full_text}")
            
        # Look for shows around 5-7 AM time slot
        five_to_seven_pattern = re.compile(r'5.*7.*AM|5.*AM.*7', re.I)
        five_seven_elements = soup.find_all(string=five_to_seven_pattern)
        print(f"\n\nSearching for 5-7 AM time slot:")
        print(f"Found {len(five_seven_elements)} elements with 5-7 AM pattern:")
        for i, elem in enumerate(five_seven_elements):
            parent = elem.parent
            # Get more context - parent's parent text
            grandparent = parent.parent if parent else None
            context_text = grandparent.get_text(strip=True)[:400] if grandparent else (parent.get_text(strip=True)[:400] if parent else elem[:400])
            print(f"\n{i+1}. Time slot found: '{elem.strip()}'")
            print(f"   Context: {context_text}")

        # Save a sample of HTML for debugging
        with open(f"debug_{url.split('/')[-1]}.html", 'w') as f:
            f.write(html[:50000])  # First 50k chars
            
        context.close()
        browser.close()

# Test with Apple Música Uno
fetch_and_debug("https://music.apple.com/radio/ra.1740613864")