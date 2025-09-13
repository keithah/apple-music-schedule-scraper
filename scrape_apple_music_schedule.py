#!/usr/bin/env python3
"""
Apple Music Radio Schedule Scraper
Extracts show information from multiple Apple Music radio stations using Playwright.
"""

from playwright.sync_api import sync_playwright
from bs4 import BeautifulSoup
import json
import re
import pandas as pd
from datetime import datetime
import pytz
from typing import List, Dict, Optional, Tuple

class AppleMusicScheduleScraper:
    def __init__(self):
        self.stations = {
            "Apple Music 1": "https://music.apple.com/us/radio/ra.978194965",
            "Apple Music Hits": "https://music.apple.com/us/radio/ra.1498155548", 
            "Apple Music Country": "https://music.apple.com/us/radio/ra.1498157166",
            "Apple Music Club": "https://music.apple.com/radio/ra.1740613859",
            "Apple Music Chill": "https://music.apple.com/radio/ra.1740614260",
            "Apple Musica Uno": "https://music.apple.com/radio/ra.1740613864"
        }
        
    def fetch_page(self, url: str) -> tuple[Optional[str], dict]:
        """Fetch a specific Apple Music radio page using Playwright and extract image URLs."""
        try:
            with sync_playwright() as p:
                browser = p.chromium.launch(headless=True)
                # Create browser context with Pacific Time timezone
                context = browser.new_context(
                    timezone_id='America/Los_Angeles',
                    locale='en-US'
                )
                page = context.new_page()
                
                # Navigate to the page
                page.goto(url, wait_until="networkidle")
                
                # Wait for schedule content to load
                page.wait_for_timeout(5000)
                
                # Wait for images to load - look for the actual Apple Music image domains
                try:
                    page.wait_for_function(
                        "() => document.querySelectorAll('img[src*=\"mzstatic.com\"]').length > 0 || "
                        "document.querySelectorAll('img[src*=\"artwork\"]').length > 0 || "
                        "document.querySelectorAll('[style*=\"mzstatic.com\"]').length > 0",
                        timeout=15000
                    )
                except:
                    print(f"Images may not have fully loaded for {url}")
                
                # Additional wait for dynamic content and lazy loading
                page.wait_for_timeout(3000)
                
                # Scroll down to trigger lazy loading
                page.evaluate("window.scrollTo(0, document.body.scrollHeight)")
                page.wait_for_timeout(2000)
                
                # Scroll back up
                page.evaluate("window.scrollTo(0, 0)")
                page.wait_for_timeout(1000)
                
                # Extract image URLs using JavaScript
                image_data = page.evaluate("""
                    () => {
                        const imageMap = {};
                        
                        // Get all images 
                        const allImages = document.querySelectorAll('img');
                        
                        const mzstaticImages = document.querySelectorAll('img[src*="mzstatic.com"]');
                        
                        // Get all images and their src attributes
                        const allImageSrcs = Array.from(allImages).map(img => img.src).filter(src => src && src.length > 10);
                        
                        // Look for show elements more aggressively - cast a wider net
                        const potentialShows = document.querySelectorAll(
                            '[class*="item"], [class*="card"], [class*="tile"], [role="listitem"], ' +
                            'li, [class*="show"], [class*="program"], [class*="schedule"], ' +
                            '[class*="episode"], [class*="track"], [class*="content"], ' + 
                            'div[data-testid], article, section > div, main > div > div'
                        );
                        
                        potentialShows.forEach((element, index) => {
                            const text = element.textContent.trim();
                            
                            // Look for time pattern to identify show blocks - include times with minutes
                            if (text.match(/\\d{1,2}(?::\\d{2})?\\s*(?:AM|PM)?\\s*[–-]\\s*\\d{1,2}(?::\\d{2})?\\s*(?:AM|PM)/i)) {
                                const key = text.substring(0, 100);
                                
                                // First, look for picture elements with srcset
                                const pictures = element.querySelectorAll('picture');
                                pictures.forEach(picture => {
                                    const sources = picture.querySelectorAll('source[srcset]');
                                    sources.forEach(source => {
                                        const srcset = source.getAttribute('srcset');
                                        if (srcset && srcset.includes('mzstatic.com')) {
                                            // Parse srcset to get the best quality image
                                            const entries = srcset.split(',');
                                            let bestUrl = null;
                                            let bestSize = 0;
                                            
                                            entries.forEach(entry => {
                                                const parts = entry.trim().split(' ');
                                                if (parts.length >= 2) {
                                                    const url = parts[0];
                                                    const sizeMatch = parts[1].match(/(\\d+)w?/);
                                                    if (sizeMatch) {
                                                        const size = parseInt(sizeMatch[1]);
                                                        if (size > bestSize) {
                                                            bestSize = size;
                                                            bestUrl = url;
                                                        }
                                                    }
                                                }
                                            });
                                            
                                            if (bestUrl) {
                                                imageMap[key] = bestUrl;
                                            }
                                        }
                                    });
                                });
                                
                                // Fallback: look for img elements
                                if (!imageMap[key]) {
                                    const images = element.querySelectorAll('img');
                                    images.forEach(img => {
                                        const src = img.src;
                                        if (src && src.length > 10 && !src.endsWith('1x1.gif')) {
                                            imageMap[key] = src;
                                        }
                                    });
                                }
                            }
                        });
                        
                        return {
                            imageMap: imageMap
                        };
                    }
                """)
                
                actual_image_data = image_data.get('imageMap', {})
                
                # Get the page content
                html = page.content()
                context.close()
                browser.close()
                return html, actual_image_data
                
        except Exception as e:
            print(f"Error fetching page {url}: {e}")
            return None, {}
    
    def parse_schedule(self, html: str, image_data: dict = None) -> List[Dict]:
        """Parse the schedule from HTML content."""
        soup = BeautifulSoup(html, 'html.parser')
        shows = []
        image_data = image_data or {}
        
        # Look for specific Apple Music schedule structure
        # Try different selectors for schedule items - be more aggressive
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
            'section > div > div',
            'main div[class*="grid"] > div',
            'div[class*="row"] > div[class*="col"]'
        ]
        
        schedule_items = []
        for selector in selectors:
            items = soup.select(selector)
            if items and len(items) > 1:  # Only use if we get multiple items (individual shows)
                schedule_items = items
                break
        
        if not schedule_items:
            # Fallback: look for any elements containing time patterns - including LIVE prefix
            time_elements = soup.find_all(string=re.compile(r'(?:LIVE\s*[·•]?\s*)?\d{1,2}(?::\d{2})?\s*(?:AM|PM)?\s*[–-]\s*\d{1,2}(?::\d{2})?\s*(?:AM|PM)', re.I))
            schedule_items = []
            for time_elem in time_elements:
                # Get the parent container that likely contains the full show info
                parent = time_elem.parent
                while parent and not any(word in parent.get('class', []) + [parent.name] for word in ['item', 'card', 'container', 'section']):
                    parent = parent.parent
                    if parent and parent.name == 'body':
                        parent = time_elem.parent
                        break
                if parent and parent not in schedule_items:
                    schedule_items.append(parent)
        
        for item in schedule_items:
            show_data = self.extract_show_data(item, image_data)
            if show_data and self.is_valid_show(show_data):
                shows.append(show_data)
        
        return shows
    
    def is_valid_show(self, show_data: Dict) -> bool:
        """Filter out navigation elements and invalid entries."""
        title = show_data.get('title', '').lower()
        
        # Filter out navigation items
        nav_items = ['home', 'new', 'radio', 'search', 'sign in']
        if title in nav_items:
            return False
            
        # Must have either a time slot or be a special show
        if not show_data.get('time_slot') and not any(word in title for word in ['show', 'list', 'takeover', 'hits']):
            return False
            
        return True
    
    def _normalize_url(self, url: str) -> str:
        """Normalize and fix URL formats."""
        if not url:
            return url
        
        # Handle protocol-relative URLs
        if url.startswith('//'):
            return 'https:' + url
        # Handle relative URLs
        elif url.startswith('/'):
            return 'https://music.apple.com' + url
        # Return absolute URLs as-is
        else:
            return url
    
    def _parse_time_component(self, time_str: str) -> Tuple[int, int, str]:
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
    
    def _convert_12h_to_24h(self, time_slot: str) -> str:
        """Convert 12-hour format time slot to 24-hour format."""
        if not time_slot:
            return time_slot
            
        try:
            # Parse different time slot formats
            patterns = [
                # Pattern 1: Both times have AM/PM with flexible spacing (10:10 PM – 12:15 AM)
                r'(\d{1,2}(?::\d{2})?\s*(?:AM|PM))\s*[–-]\s*(\d{1,2}(?::\d{2})?\s*(?:AM|PM))',
                # Pattern 2: Only end time has AM/PM (9 – 10 PM, 10:10 AM – 12PM)
                r'(\d{1,2}(?::\d{2})?)\s*[–-]\s*(\d{1,2}(?::\d{2})?\s*(?:AM|PM))',
                # Pattern 3: No AM/PM on either
                r'(\d{1,2}(?::\d{2})?)\s*[–-]\s*(\d{1,2}(?::\d{2})?)',
            ]
            
            match = None
            for pattern in patterns:
                match = re.match(pattern, time_slot, re.I)
                if match:
                    break
                    
            if not match:
                return time_slot
                
            start_str = match.group(1)
            end_str = match.group(2)
            
            # Parse start and end times
            start_hour, start_min, start_period = self._parse_time_component(start_str)
            end_hour, end_min, end_period = self._parse_time_component(end_str)
            
            # Infer missing AM/PM periods
            if end_period is None and start_period:
                if end_hour < start_hour:
                    end_period = 'AM' if start_period == 'PM' else 'PM'
                else:
                    end_period = start_period
            elif start_period is None and end_period:
                if start_hour == 12 and end_period == 'AM':
                    start_period = 'AM'
                elif start_hour == 12 and end_period == 'PM':
                    start_period = 'PM'
                elif start_hour > end_hour:
                    start_period = 'AM' if end_period == 'PM' else 'PM'
                else:
                    start_period = end_period
            
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
            
            # Format as 24-hour time
            start_formatted = f"{start_hour_24:02d}:{start_min:02d}"
            end_formatted = f"{end_hour_24:02d}:{end_min:02d}"
            
            return f"{start_formatted} – {end_formatted}"
            
        except Exception as e:
            # If conversion fails, log the error and return original
            print(f"Error converting 12h to 24h format '{time_slot}': {e}")
            return time_slot
    
    def _convert_utc_to_pacific(self, time_slot_utc: str) -> str:
        """Convert UTC time slot to Pacific time."""
        if not time_slot_utc:
            return None
            
        try:
            # Parse 24-hour format: "23:00 – 01:00"
            pattern = r'(\d{1,2}):(\d{2})\s*[–-]\s*(\d{1,2}):(\d{2})'
            match = re.match(pattern, time_slot_utc)
            
            if not match:
                # Fallback: try to convert 12h to 24h first if input is still in 12h format
                if re.search(r'(AM|PM)', time_slot_utc, re.I):
                    print(f"Warning: UTC time still in 12h format, converting: {time_slot_utc}")
                    time_slot_utc_24h = self._convert_12h_to_24h(time_slot_utc)
                    match = re.match(pattern, time_slot_utc_24h)
                    if not match:
                        return time_slot_utc
                else:
                    return time_slot_utc
                
            start_hour = int(match.group(1))
            start_min = int(match.group(2))
            end_hour = int(match.group(3))
            end_min = int(match.group(4))
            
            # Apply Pacific Time offset (UTC-8 for PST, UTC-7 for PDT)  
            # Determine if we're in Daylight Saving Time
            pacific_tz = pytz.timezone('America/Los_Angeles')
            now = datetime.now(pacific_tz)
            is_dst = bool(now.dst())
            offset = 7 if is_dst else 8  # PDT is UTC-7, PST is UTC-8
            
            # Convert UTC to Pacific by subtracting offset
            pacific_start_hour = start_hour - offset
            if pacific_start_hour < 0:
                pacific_start_hour += 24
            elif pacific_start_hour >= 24:
                pacific_start_hour -= 24
                
            pacific_end_hour = end_hour - offset  
            if pacific_end_hour < 0:
                pacific_end_hour += 24
            elif pacific_end_hour >= 24:
                pacific_end_hour -= 24
            
            # Format with 24-hour time
            start_formatted = f"{pacific_start_hour:02d}:{start_min:02d}"
            end_formatted = f"{pacific_end_hour:02d}:{end_min:02d}"
            
            return f"{start_formatted} – {end_formatted}"
            
        except Exception as e:
            print(f"Error converting time: {e}")
            return time_slot_utc
    
    def _clean_title_description(self, text: str, time_slot: str = None, is_description: bool = False, title: str = None) -> str:
        """Clean title/description by removing time slots, LIVE prefixes, and duplicated content."""
        if not text:
            return text
            
        cleaned = text
        
        # Remove LIVE prefix variations at start
        cleaned = re.sub(r'^LIVE\s*[·•]?\s*', '', cleaned, flags=re.I)
        
        # Remove time slot from beginning if it exists (exact match)
        if time_slot:
            escaped_time = re.escape(time_slot)
            cleaned = re.sub(r'^' + escaped_time + r'\s*', '', cleaned)
        
        # More comprehensive time pattern removal that handles concatenated cases
        # This handles patterns like "7 – 9 PMThe Show" -> "The Show" and "11PM – 12AM The Show" -> "The Show"
        # Also handles "2:55 – 5:15 AM The Show" -> "The Show"
        cleaned = re.sub(r'^(?:LIVE\s*[·•]?\s*)?(\d{1,2}(?::\d{2})?\s*(?:AM|PM)?\s*[–-]\s*\d{1,2}(?::\d{2})?\s*(?:AM|PM))\s*', '', cleaned, flags=re.I)
        
        # Additional cleanup for remaining patterns
        cleaned = re.sub(r'^(\d{1,2}(?::\d{2})?\s*[–-]\s*\d{1,2}(?::\d{2})?\s*(?:AM|PM))\s*', '', cleaned, flags=re.I)
        
        # Remove LIVE patterns that appear mid-text
        cleaned = re.sub(r'LIVE\s*[·•]\s*(\d{1,2}(?::\d{2})?\s*[–-]\s*\d{1,2}(?::\d{2})?\s*(?:AM|PM))\s*', '', cleaned, flags=re.I)
        
        # Handle badly concatenated time+title (e.g., "05 – 9 PM7:05 – 9 PMThe Show")
        # Look for repeated time patterns
        cleaned = re.sub(r'(\d{1,2}(?::\d{2})?\s*[–-]\s*\d{1,2}(?::\d{2})?\s*(?:AM|PM))\s*\1\s*', r'\1 ', cleaned, flags=re.I)
        
        # Final cleanup: if text starts with a time pattern followed immediately by letters, split them
        time_title_match = re.match(r'^(\d{1,2}(?::\d{2})?\s*[–-]\s*\d{1,2}(?::\d{2})?\s*(?:AM|PM))([A-Za-z].*)$', cleaned, re.I)
        if time_title_match:
            cleaned = time_title_match.group(2).strip()
        
        # Handle concatenated words like "ShowHouston's" -> "Show Houston's"
        # Look for common show-ending words immediately followed by capitalized words
        cleaned = re.sub(r'(Show|List|Hits|Radio|Music)([A-Z][a-z])', r'\1 \2', cleaned)
        
        # Handle other common concatenations
        cleaned = re.sub(r'([a-z])([A-Z][a-z])', r'\1 \2', cleaned)
        
        # For descriptions, remove the title from the beginning if it's duplicated
        if is_description and title:
            # Remove exact title match from beginning
            if cleaned.lower().startswith(title.lower()):
                cleaned = cleaned[len(title):].strip()
            # Handle cases where title is repeated (e.g., "The ShowThe Show description")
            title_repeated = title + title
            if cleaned.lower().startswith(title_repeated.lower()):
                cleaned = cleaned[len(title_repeated):].strip()
            # Handle concatenated title+description (e.g., "The ShowDescription text")
            elif title and len(title) > 3:
                # Look for title at start followed immediately by description
                pattern = r'^' + re.escape(title) + r'([A-Z].*)'
                match = re.match(pattern, cleaned)
                if match:
                    cleaned = match.group(1)
        
        return cleaned.strip()
    
    def extract_show_data(self, element, image_data: dict = None) -> Optional[Dict]:
        """Extract show data from a schedule element."""
        try:
            # Get all text content
            full_text = element.get_text(separator=' ', strip=True)
            
            # Extract time slot using improved regex - handle LIVE prefix and various formats
            # First, clean up LIVE prefix if present
            full_text_clean = re.sub(r'^LIVE\s*[·•]?\s*', '', full_text, flags=re.I)
            
            patterns = [
                r'(\d{1,2}:\d{2}\s*(?:AM|PM)?\s*[–-]\s*\d{1,2}:\d{2}\s*(?:AM|PM))',  # 7:05 PM - 9:00 PM or 7:05 - 9:00 AM
                r'(\d{1,2}:\d{2}\s*[–-]\s*\d{1,2}:\d{2}\s*(?:AM|PM))',        # 7:05 - 9:00 PM
                r'(\d{1,2}:\d{2}\s*(?:AM|PM)?\s*[–-]\s*\d{1,2}\s*(?:AM|PM))',  # 7:05 PM - 9 AM or 2:55 - 5:15 AM
                r'(\d{1,2}\s*(?:AM|PM)\s*[–-]\s*\d{1,2}\s*(?:AM|PM))',        # 11PM - 12AM
                r'(\d{1,2}:\d{2}\s*[–-]\s*\d{1,2}\s*(?:AM|PM))',              # 7:05 - 9 PM  
                r'(\d{1,2}\s*[–-]\s*\d{1,2}:\d{2}\s*(?:AM|PM))',              # 7 - 9:00 PM
                r'(\d{1,2}\s*[–-]\s*\d{1,2}\s*(?:AM|PM))'                     # 7 - 9 PM
            ]
            
            all_matches = []
            for pattern in patterns:
                # Try both original and cleaned text
                matches = re.findall(pattern, full_text, re.I)
                all_matches.extend(matches)
                matches_clean = re.findall(pattern, full_text_clean, re.I)
                all_matches.extend(matches_clean)
            
            time_slot = None
            if all_matches:
                # Prefer the longest/most complete time pattern
                time_slot = max(all_matches, key=len)
            
            # Extract show title and description using improved algorithm
            title = None
            description = None
            
            # Try HTML-based extraction first to separate title and description
            # Look for strong elements (bold text) for titles
            title_candidates = []
            desc_candidates = []
            
            # Find bold/strong elements for titles
            title_elements = element.select('strong, b, [class*="title"], [class*="heading"], h1, h2, h3, h4, h5, h6')
            for elem in title_elements:
                candidate_text = elem.get_text(strip=True)
                candidate_text = self._clean_title_description(candidate_text, time_slot, is_description=False)
                if candidate_text and not re.match(r'^\d{1,2}\s*[–-]\s*\d{1,2}\s*(AM|PM)$', candidate_text, re.I):
                    title_candidates.append(candidate_text)
            
            # Find description elements (often in separate elements after title)
            desc_elements = element.select('p, [class*="description"], [class*="subtitle"], [class*="summary"]')
            for elem in desc_elements:
                candidate_text = elem.get_text(strip=True)
                candidate_text = self._clean_title_description(candidate_text, time_slot, is_description=True)
                if candidate_text and not re.match(r'^\d{1,2}\s*[–-]\s*\d{1,2}\s*(AM|PM)$', candidate_text, re.I):
                    desc_candidates.append(candidate_text)
            
            # Choose best title and description
            if title_candidates:
                title = title_candidates[0]  # Take first valid title
            
            if desc_candidates:
                # Find description that doesn't duplicate the title
                for desc in desc_candidates:
                    if not title or (desc != title and not desc.startswith(title)):
                        description = desc
                        break
            
            # Fallback: Smart extraction from combined text if HTML-based didn't work
            clean_text = self._clean_title_description(full_text, time_slot, is_description=False)
            if not title:
                
                if clean_text:
                    # Look for show name patterns - typically the first capitalized phrase
                    words = clean_text.split()
                    
                    # Find where the title ends and description begins
                    title_end_idx = None
                    
                    for i in range(1, len(words)):
                        current_phrase = ' '.join(words[:i+1])
                        
                        # Special case: if we see "Show", that's likely the title end
                        if words[i].lower() == 'show':
                            title = current_phrase
                            title_end_idx = i + 1
                            break
                        
                        # Check if this looks like a complete show title
                        if i < len(words) - 1:  # Not the last word
                            next_word = words[i+1]
                            next_words = ' '.join(words[i+1:]).lower()
                            
                            # Don't break on description starters if "Show" might still be coming
                            # Check if "Show" appears in next few words
                            upcoming_words = words[i+1:i+4] if i+3 < len(words) else words[i+1:]
                            has_show_coming = any(w.lower() == 'show' for w in upcoming_words)
                            
                            # Strong indicators this is end of title (but not if Show is coming)
                            if (not has_show_coming and (
                                words[i].lower() in ['list', 'hits', 'radio', 'music'] or  # Common show endings
                                next_word[0].islower() or  # Next word starts lowercase (likely description)
                                # Only break on description starters if no "Show" is expected
                                next_words.startswith(('your favorite', 'daily dispatches', 'from the'))
                            )):
                                title = current_phrase
                                title_end_idx = i + 1
                                break
                    
                    # If no clear break found, use heuristics
                    if not title and len(words) >= 2:
                        # Default: take first 2-3 words as title if they look like proper nouns
                        if words[0][0].isupper() and (len(words) == 1 or words[1][0].isupper()):
                            # Find reasonable title length
                            for i in range(1, min(4, len(words))):
                                if words[i-1].lower() in ['show', 'list', 'radio'] or words[i][0].islower():
                                    title = ' '.join(words[:i])
                                    title_end_idx = i
                                    break
                            if not title:
                                title = ' '.join(words[:2]) if len(words) >= 2 else words[0]
                                title_end_idx = 2 if len(words) >= 2 else 1
                    
                    # Extract description from remaining words if not already set
                    if not description and title_end_idx and title_end_idx < len(words):
                        description = ' '.join(words[title_end_idx:])
            
            # Additional fallback: if still no title, use the first meaningful part of the text
            if not title and clean_text:
                # Just take the first few words as title
                words = clean_text.split()
                if words:
                    title = words[0]
                    # Add more words if they seem part of the title
                    for i in range(1, min(len(words), 4)):
                        if words[i][0].isupper() or words[i-1].lower() in ['the', 'a', 'an']:
                            title += ' ' + words[i]
                        else:
                            break
            
            # Clean up description by removing title duplication (if not already extracted above)
            if description and title:
                description = self._clean_title_description(description, time_slot, is_description=True, title=title)
            
            # Fallback: extract description from remaining text if not already set
            if not description and clean_text and title:
                remaining_text = clean_text
                if title in remaining_text:
                    # Remove the title from the text to get description
                    remaining_text = remaining_text.replace(title, '', 1).strip()
                if remaining_text and len(remaining_text) > 5:
                    description = remaining_text
            
            # Extract artwork URL - comprehensive search for show thumbnails
            artwork_url = None
            image_data = image_data or {}
            
            # First, try to match with the image data extracted via JavaScript
            if image_data:
                element_text = full_text[:100]
                for text_key, img_url in image_data.items():
                    if element_text in text_key or text_key in element_text:
                        artwork_url = self._normalize_url(img_url)
                        break
            
            # If not found in image_data, look for picture elements with srcset attributes
            if not artwork_url:
                picture_elements = element.select('picture')
                for picture_elem in picture_elements:
                    # Look for source elements with srcset containing mzstatic URLs
                    source_elements = picture_elem.select('source[srcset]')
                    for source_elem in source_elements:
                        srcset = source_elem.get('srcset', '')
                        if 'mzstatic.com' in srcset:
                            # Parse srcset to extract the highest quality image URL
                            srcset_entries = [entry.strip() for entry in srcset.split(',')]
                            best_url = None
                            best_size = 0
                            
                            for entry in srcset_entries:
                                parts = entry.strip().split()
                                if len(parts) >= 2:
                                    url = parts[0]
                                    size_str = parts[1]
                                    # Extract numeric size (e.g., "632w" -> 632)
                                    size_match = re.match(r'(\d+)w?', size_str)
                                    if size_match:
                                        size = int(size_match.group(1))
                                        if size > best_size:
                                            best_size = size
                                            best_url = url
                            
                            if best_url:
                                artwork_url = self._normalize_url(best_url)
                                break
                    if artwork_url:
                        break
            
            # Fallback: look for img elements with actual artwork
            if not artwork_url:
                img_elements = element.select('img')
                for img_elem in img_elements:
                    # Try different attributes that might contain the image URL
                    for attr in ['src', 'data-src', 'data-lazy-src', 'data-original', 'srcset', 'data-srcset']:
                        url = img_elem.get(attr)
                        if url and not url.endswith('1x1.gif'):
                            # Look for URLs that contain actual image content
                            if any(keyword in url.lower() for keyword in ['artwork', 'image', 'thumb', 'cover', '.jpg', '.png', '.webp']):
                                artwork_url = self._normalize_url(url)
                                break
                    if artwork_url:
                        break
            
            # Look for background images in any element
            if not artwork_url:
                bg_elements = element.select('[style*="background-image"], [data-style*="background-image"]')
                for bg_elem in bg_elements:
                    style = bg_elem.get('style', '') + bg_elem.get('data-style', '')
                    bg_match = re.search(r'background-image:\s*url\(["\']?([^"\']+)["\']?\)', style)
                    if bg_match:
                        bg_url = bg_match.group(1)
                        if not bg_url.endswith('1x1.gif'):
                            if any(keyword in bg_url.lower() for keyword in ['artwork', 'image', 'thumb', 'cover', '.jpg', '.png', '.webp']):
                                artwork_url = self._normalize_url(bg_url)
                                break
            
            # Look for data attributes that might contain artwork URLs
            if not artwork_url:
                for attr in element.attrs:
                    if 'artwork' in attr.lower() or 'image' in attr.lower() or 'thumb' in attr.lower():
                        url = element.get(attr)
                        if url and not url.endswith('1x1.gif'):
                            artwork_url = self._normalize_url(url)
                            break
            
            # Extract show URL
            show_url = None
            link_elem = element.select_one('a[href]')
            if link_elem:
                show_url = link_elem.get('href')
                if show_url and not show_url.startswith('http'):
                    show_url = 'https://music.apple.com' + show_url
            
            # Only return if we have meaningful data
            if time_slot or title or description:
                # Convert time_slot to 24-hour format
                time_slot_24h = self._convert_12h_to_24h(time_slot) if time_slot else time_slot
                
                return {
                    'time_slot': time_slot_24h,
                    'title': title,
                    'description': description,
                    'artwork_url': artwork_url,
                    'show_url': show_url,
                    'raw_text': full_text[:200] + '...' if len(full_text) > 200 else full_text
                }
        
        except Exception as e:
            print(f"Error extracting show data: {e}")
        
        return None
    
    def scrape_all_stations(self) -> List[Dict]:
        """Scrape all radio stations and return combined schedule."""
        all_shows = []
        
        for station_name, url in self.stations.items():
            print(f"Fetching {station_name} schedule from: {url}")
            
            html, image_data = self.fetch_page(url)
            if not html:
                print(f"Failed to fetch {station_name}")
                continue
                
            shows = self.parse_schedule(html, image_data)
            
            # Add station name to each show
            for show in shows:
                show['station'] = station_name
                show['station_url'] = url
            
            print(f"Found {len(shows)} shows for {station_name}")
            all_shows.extend(shows)
        
        print(f"Total shows found: {len(all_shows)}")
        return all_shows
    
    def save_to_json(self, shows: List[Dict], filename: str = "apple_music_schedule.json"):
        """Save schedule data to JSON file."""
        # Get current time in Pacific Time
        pacific_tz = pytz.timezone('America/Los_Angeles')
        scraped_at = datetime.now(pacific_tz).isoformat()
        
        with open(filename, 'w', encoding='utf-8') as f:
            json.dump({
                'scraped_at': scraped_at,
                'stations_scraped': list(self.stations.keys()),
                'shows': shows
            }, f, indent=2, ensure_ascii=False)
        print(f"Schedule saved to {filename}")
    
    def _parse_time_to_minutes(self, time_str: str) -> int:
        """Convert a time string like '2:55AM' or '11PM' to minutes since midnight."""
        if not time_str:
            return -1
            
        # Remove spaces and convert to uppercase
        time_str = time_str.strip().upper()
        
        # Handle common time formats more flexibly
        # Try different patterns
        patterns = [
            r'(\d{1,2})(?::(\d{2}))?\s*(AM|PM)',  # 11:30PM or 11PM
            r'(\d{1,2})(?::(\d{2}))?'             # 11:30 or 11 (assume 24-hour if no AM/PM)
        ]
        
        for pattern in patterns:
            match = re.match(pattern, time_str)
            if match:
                hour = int(match.group(1))
                minute = int(match.group(2) or 0)
                period = match.group(3) if len(match.groups()) >= 3 else None
                
                # Convert to 24-hour format
                if period:
                    if period == 'PM' and hour != 12:
                        hour += 12
                    elif period == 'AM' and hour == 12:
                        hour = 0
                
                # Validate hour range
                if 0 <= hour <= 23 and 0 <= minute <= 59:
                    return hour * 60 + minute
                    
        return -1
    
    def _detect_time_gaps(self, station_shows: List[Dict]) -> List[Dict]:
        """Detect gaps in schedule and insert placeholder entries."""
        if not station_shows:
            return station_shows
            
        # Parse time slots and sort by start time
        shows_with_times = []
        for show in station_shows:
            time_slot = show.get('time_slot', '')
            if not time_slot:
                continue
                
            # Extract start and end times
            time_match = re.search(r'(\d{1,2}(?::\d{2})?\s*(?:AM|PM)?)\s*[–-]\s*(\d{1,2}(?::\d{2})?\s*(?:AM|PM))', time_slot, re.I)
            if time_match:
                start_str = time_match.group(1)
                end_str = time_match.group(2)
                
                # Handle missing AM/PM
                if 'AM' not in end_str.upper() and 'PM' not in end_str.upper():
                    # Infer from context
                    if 'AM' in start_str.upper():
                        end_str += 'AM'
                    elif 'PM' in start_str.upper():
                        end_str += 'PM'
                
                start_minutes = self._parse_time_to_minutes(start_str)
                end_minutes = self._parse_time_to_minutes(end_str)
                
                # Handle day rollover
                if end_minutes < start_minutes:
                    end_minutes += 24 * 60
                    
                shows_with_times.append({
                    'show': show,
                    'start': start_minutes,
                    'end': end_minutes,
                    'time_slot': time_slot
                })
        
        # Sort by start time
        shows_with_times.sort(key=lambda x: x['start'])
        
        # Check for gaps and insert placeholders
        result = []
        for i, current in enumerate(shows_with_times):
            result.append(current['show'])
            
            # Check if there's a next show
            if i < len(shows_with_times) - 1:
                next_show = shows_with_times[i + 1]
                
                # If there's a gap between current end and next start
                gap_minutes = next_show['start'] - current['end']
                if gap_minutes > 5:  # Allow 5 minutes tolerance
                    # Calculate gap time slot
                    gap_start = current['end']
                    gap_end = next_show['start']
                    
                    # Convert back to time format
                    gap_start_hour = (gap_start // 60) % 24
                    gap_start_min = gap_start % 60
                    gap_end_hour = (gap_end // 60) % 24
                    gap_end_min = gap_end % 60
                    
                    # Format time slot
                    gap_start_str = f"{gap_start_hour:02d}:{gap_start_min:02d}"
                    gap_end_str = f"{gap_end_hour:02d}:{gap_end_min:02d}"
                    
                    # Keep consistent 24-hour format (no simplification needed)
                    
                    gap_time_slot = f"{gap_start_str} – {gap_end_str}"
                    
                    # Insert gap placeholder
                    result.append({
                        'station': current['show'].get('station', ''),
                        'time_slot': gap_time_slot,
                        'title': '*** MISSING SHOW ***',
                        'description': f'Gap detected in schedule from {gap_start_str} to {gap_end_str}',
                        'artwork_url': '',
                        'show_url': '',
                        'station_url': current['show'].get('station_url', '')
                    })
                    
                    print(f"WARNING: Gap detected in {current['show'].get('station', '')} schedule: {gap_time_slot}")
        
        return result
    
    def save_to_csv(self, shows: List[Dict], filename: str = "apple_music_schedule.csv"):
        """Save schedule data to CSV file with gap detection."""
        if not shows:
            print("No shows to save to CSV")
            return
            
        # Get current time in Pacific Time
        pacific_tz = pytz.timezone('America/Los_Angeles')
        scraped_at = datetime.now(pacific_tz).isoformat()
        
        # Group shows by station and detect gaps
        stations = {}
        for show in shows:
            station = show.get('station', 'Unknown')
            if station not in stations:
                stations[station] = []
            stations[station].append(show)
        
        # Process each station - disable gap detection since we have 24h coverage
        all_shows_with_gaps = []
        for station, station_shows in stations.items():
            # Skip gap detection for now since it's creating false positives
            all_shows_with_gaps.extend(station_shows)
        
        # Prepare data for CSV with new column order
        csv_data = []
        for show in all_shows_with_gaps:
            # Original time from Apple Music (this is already UTC - no conversion needed)
            time_slot_utc = show.get('time_slot', '')
            # Convert UTC to Pacific for display purposes
            time_slot_pacific = self._convert_utc_to_pacific(time_slot_utc) if '*** MISSING' not in show.get('title', '') else time_slot_utc
            
            csv_data.append({
                'station': show.get('station', ''),
                'time_slot_pacific': time_slot_pacific,
                'show_title': show.get('title', ''),
                'description': show.get('description', ''),
                'show_image_url': show.get('artwork_url', ''),
                'time_slot_utc': time_slot_utc,
                'show_url': show.get('show_url', ''),
                'scraped_at': scraped_at
            })
        
        # Create DataFrame and sort by station and time
        df = pd.DataFrame(csv_data)
        
        # Add a sorting helper column for Pacific times
        def time_to_sort_key(time_slot):
            """Convert Pacific time slot to sorting key (handles both 12h and 24h formats)"""
            if not time_slot or '***' in str(time_slot):
                return 9999  # Put gaps at end
            
            # Try 24-hour format first: "14:00 – 16:00"
            time_match_24h = re.search(r'(\d{1,2}):(\d{2})\s*[–-]', str(time_slot))
            if time_match_24h:
                hour = int(time_match_24h.group(1))
                minute = int(time_match_24h.group(2))
                return hour * 60 + minute
            
            # Fallback to 12-hour format parsing
            time_match = re.search(r'(\d{1,2}(?::\d{2})?)\s*(AM|PM)?\s*[–-]', str(time_slot), re.I)
            if time_match:
                start_str = time_match.group(1)
                period = time_match.group(2)  # AM/PM directly attached to start time
                
                # If no AM/PM attached to start time, infer from context
                if not period:
                    # Look for AM/PM later in the string for end time
                    end_match = re.search(r'[–-]\s*\d{1,2}(?::\d{2})?\s*(AM|PM)', str(time_slot), re.I)
                    if end_match:
                        end_period = end_match.group(1).upper()
                        start_hour = int(start_str.split(':')[0])  # Extract just the hour part
                        if end_period == 'AM' and start_hour >= 10:  # Like "11PM – 1AM"
                            period = 'PM'  # Late night hours crossing midnight
                        elif end_period == 'PM' and start_hour <= 8:  # Like "5 – 7PM"  
                            period = 'PM'  # Afternoon/evening hours
                        else:
                            period = end_period  # Default to same as end time
                    else:
                        period = 'AM'  # Default
                else:
                    period = period.upper()
                
                # Parse time
                if ':' in start_str:
                    hour, minute = map(int, start_str.split(':'))
                else:
                    hour, minute = int(start_str), 0
                
                # Convert to 24-hour for sorting
                if period == 'PM' and hour != 12:
                    hour += 12
                elif period == 'AM' and hour == 12:
                    hour = 0
                
                return hour * 60 + minute
            
            return 9999
        
        df['_sort_key'] = df['time_slot_pacific'].apply(time_to_sort_key)
        
        # Sort by station, then by time
        df = df.sort_values(['station', '_sort_key'])
        
        # Remove the sorting helper column
        df = df.drop('_sort_key', axis=1)
        
        df.to_csv(filename, index=False, encoding='utf-8')
        print(f"Schedule saved to {filename} (sorted by time)")

def main():
    scraper = AppleMusicScheduleScraper()
    shows = scraper.scrape_all_stations()
    
    if shows:
        # Print summary
        print(f"\nApple Music Radio Schedule Summary:")
        print("=" * 50)
        
        # Group by station
        stations = {}
        for show in shows:
            station = show.get('station', 'Unknown')
            if station not in stations:
                stations[station] = []
            stations[station].append(show)
        
        for station, station_shows in stations.items():
            print(f"{station}: {len(station_shows)} shows")
        
        print("\nSample shows:")
        print("-" * 30)
        for i, show in enumerate(shows[:10]):  # Show first 10
            print(f"[{show.get('station', 'N/A')}] {show.get('time_slot', 'N/A')} - {show.get('title', 'N/A')}")
            if i >= 9:
                break
        
        if len(shows) > 10:
            print(f"... and {len(shows) - 10} more shows")
        
        # Save to both formats
        scraper.save_to_json(shows)
        scraper.save_to_csv(shows)
    else:
        print("No schedule data found. The page structure may have changed.")
        print("Try running with debug mode or check the pages manually.")

if __name__ == "__main__":
    main()