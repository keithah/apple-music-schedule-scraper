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
                
                # Extract image URLs using JavaScript - debug version
                image_data = page.evaluate("""
                    () => {
                        const imageMap = {};
                        const debugInfo = {};
                        
                        // Get all images 
                        const allImages = document.querySelectorAll('img');
                        debugInfo.totalImages = allImages.length;
                        
                        const mzstaticImages = document.querySelectorAll('img[src*="mzstatic.com"]');
                        debugInfo.mzstaticImages = mzstaticImages.length;
                        
                        // Get all images and their src attributes for debugging
                        const allImageSrcs = Array.from(allImages).map(img => img.src).filter(src => src && src.length > 10);
                        debugInfo.imageSources = allImageSrcs.slice(0, 10); // First 10 for debugging
                        
                        // Look for show elements more specifically
                        const potentialShows = document.querySelectorAll('[class*="item"], [class*="card"], [class*="tile"], [role="listitem"], li, [class*="show"]');
                        debugInfo.potentialShows = potentialShows.length;
                        
                        potentialShows.forEach((element, index) => {
                            const text = element.textContent.trim();
                            
                            // Look for time pattern to identify show blocks
                            if (text.match(/\\d{1,2}\\s*[–-]\\s*\\d{1,2}\\s*(AM|PM)/i)) {
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
                        
                        debugInfo.imageMapSize = Object.keys(imageMap).length;
                        
                        return {
                            imageMap: imageMap,
                            debug: debugInfo
                        };
                    }
                """)
                
                print(f"Debug info for {url}: {image_data.get('debug', {})}")
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
        # Try different selectors for schedule items
        selectors = [
            '[data-testid*="schedule"]',
            '[data-testid*="show"]',
            '[data-testid*="program"]',
            '.schedule-item',
            '.show-item',
            '[class*="schedule"]',
            '[class*="show"]',
            '[class*="item"]'
        ]
        
        schedule_items = []
        for selector in selectors:
            items = soup.select(selector)
            if items:
                schedule_items = items
                break
        
        if not schedule_items:
            # Fallback: look for any elements containing time patterns
            time_elements = soup.find_all(string=re.compile(r'\d{1,2}\s*[–-]\s*\d{1,2}\s*(AM|PM)', re.I))
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
    
    def _convert_utc_to_pacific(self, time_slot_utc: str) -> str:
        """Convert UTC time slot to Pacific time."""
        if not time_slot_utc:
            return None
            
        try:
            # Parse different time slot formats
            # Formats: "11PM – 12AM", "7:05 – 9 PM", "10AM – 12PM"
            patterns = [
                # Pattern 1: Both times have AM/PM (11PM – 12AM)
                r'(\d{1,2}(?::\d{2})?(?:AM|PM))\s*[–-]\s*(\d{1,2}(?::\d{2})?(?:AM|PM))',
                # Pattern 2: Only end time has AM/PM (9 – 10 PM)
                r'(\d{1,2}(?::\d{2})?)\s*[–-]\s*(\d{1,2}(?::\d{2})?\s*(?:AM|PM))',
                # Pattern 3: No AM/PM on either
                r'(\d{1,2}(?::\d{2})?)\s*[–-]\s*(\d{1,2}(?::\d{2})?)',
            ]
            
            match = None
            for pattern in patterns:
                match = re.match(pattern, time_slot_utc, re.I)
                if match:
                    break
                    
            if not match:
                return time_slot_utc
                
            start_str = match.group(1)
            end_str = match.group(2)
            
            # Parse start time
            start_hour, start_min, start_period = self._parse_time_component(start_str)
            end_hour, end_min, end_period = self._parse_time_component(end_str)
            
            # Infer missing AM/PM periods
            if end_period is None and start_period:
                # If end hour is less than start, it probably switches periods
                if end_hour < start_hour:
                    end_period = 'AM' if start_period == 'PM' else 'PM'
                else:
                    end_period = start_period
            elif start_period is None and end_period:
                # If start doesn't have period but end does (like "9 – 10 PM")
                if start_hour > end_hour:
                    # Spans midnight, start is previous period
                    start_period = 'AM' if end_period == 'PM' else 'PM'
                else:
                    # Same period
                    start_period = end_period
                    
            # Convert to 24-hour format
            if start_period == 'PM' and start_hour != 12:
                start_hour += 12
            elif start_period == 'AM' and start_hour == 12:
                start_hour = 0
                
            if end_period == 'PM' and end_hour != 12:
                end_hour += 12
            elif end_period == 'AM' and end_hour == 12:
                end_hour = 0
            
            # Apply Pacific Time offset (UTC-8 for PST, UTC-7 for PDT)
            # Current date determines if we're in PDT or PST
            pacific_tz = pytz.timezone('America/Los_Angeles')
            now = datetime.now(pacific_tz)
            is_dst = bool(now.dst())
            offset = 7 if is_dst else 8
            
            # Subtract offset hours (if result is negative, add 24)
            start_hour = start_hour - offset
            if start_hour < 0:
                start_hour += 24
            end_hour = end_hour - offset
            if end_hour < 0:
                end_hour += 24
            
            # Convert back to 12-hour format with correct AM/PM
            if start_hour == 0:
                display_start_hour = 12
                start_period = 'AM'
            elif start_hour < 12:
                display_start_hour = start_hour
                start_period = 'AM'
            elif start_hour == 12:
                display_start_hour = 12
                start_period = 'PM'
            else:
                display_start_hour = start_hour - 12
                start_period = 'PM'
                
            if end_hour == 0:
                display_end_hour = 12
                end_period = 'AM'
            elif end_hour < 12:
                display_end_hour = end_hour
                end_period = 'AM'
            elif end_hour == 12:
                display_end_hour = 12
                end_period = 'PM'
            else:
                display_end_hour = end_hour - 12
                end_period = 'PM'
            
            # Format the result
            if start_min > 0:
                start_formatted = f"{display_start_hour}:{start_min:02d}{start_period}"
            else:
                start_formatted = f"{display_start_hour}{start_period}"
                
            if end_min > 0:
                end_formatted = f"{display_end_hour}:{end_min:02d}{end_period}"
            else:
                end_formatted = f"{display_end_hour}{end_period}"
            
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
        cleaned = re.sub(r'^(?:LIVE\s*[·•]?\s*)?(\d{1,2}(?::\d{2})?(?:AM|PM)?\s*[–-]\s*\d{1,2}(?::\d{2})?(?:AM|PM))\s*', '', cleaned, flags=re.I)
        
        # Additional cleanup for remaining patterns
        cleaned = re.sub(r'^(\d{1,2}\s*[–-]\s*\d{1,2}\s*(?:AM|PM))\s*', '', cleaned, flags=re.I)
        
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
            
            # Extract time slot using improved regex - prefer complete/longer time patterns
            patterns = [
                r'(\d{1,2}(?:AM|PM)\s*[–-]\s*\d{1,2}(?:AM|PM))',              # 11PM - 12AM
                r'(\d{1,2}:\d{2}(?:AM|PM)\s*[–-]\s*\d{1,2}:\d{2}(?:AM|PM))',  # 7:05PM - 9:00PM
                r'(\d{1,2}:\d{2}\s*[–-]\s*\d{1,2}:\d{2}\s*(?:AM|PM))',        # 7:05 - 9:00 PM
                r'(\d{1,2}:\d{2}\s*[–-]\s*\d{1,2}\s*(?:AM|PM))',              # 7:05 - 9 PM  
                r'(\d{1,2}\s*[–-]\s*\d{1,2}:\d{2}\s*(?:AM|PM))',              # 7 - 9:00 PM
                r'(\d{1,2}\s*[–-]\s*\d{1,2}\s*(?:AM|PM))'                     # 7 - 9 PM
            ]
            
            all_matches = []
            for pattern in patterns:
                matches = re.findall(pattern, full_text, re.I)
                all_matches.extend(matches)
            
            time_slot = None
            if all_matches:
                # Prefer the longest/most complete time pattern
                time_slot = max(all_matches, key=len)
            
            # Extract show title and description using improved algorithm
            title = None
            description = None
            
            # Smart extraction of title and description
            # Clean the input text first
            clean_text = self._clean_title_description(full_text, time_slot, is_description=False)
            
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
                
                # Extract description from remaining words
                if title_end_idx and title_end_idx < len(words):
                    description = ' '.join(words[title_end_idx:])
            
            # Fallback: try element-based extraction if smart extraction failed
            if not title:
                # Try different selectors for title
                title_selectors = [
                    'h1', 'h2', 'h3', 'h4', 'h5', 'h6',
                    '[class*="title"]', '[class*="name"]', '[class*="heading"]',
                    'strong', 'b', '.typography-headline'
                ]
                
                for selector in title_selectors:
                    title_elem = element.select_one(selector)
                    if title_elem:
                        candidate_title = title_elem.get_text(strip=True)
                        # Skip if it's just the time
                        if candidate_title and not re.match(r'^\d{1,2}\s*[–-]\s*\d{1,2}\s*(AM|PM)$', candidate_title, re.I):
                            # Clean up the title
                            candidate_title = self._clean_title_description(candidate_title, time_slot, is_description=False)
                            if candidate_title:  # Only set if something meaningful remains
                                title = candidate_title
                                break
            
            # Clean up description by removing title duplication (if not already extracted above)
            if description and title:
                description = self._clean_title_description(description, time_slot, is_description=True, title=title)
            
            # Fallback: try element-based description extraction if smart extraction didn't find one
            if not description:
                desc_selectors = [
                    '[class*="description"]', '[class*="subtitle"]', 
                    'p', '.typography-body', '[class*="summary"]'
                ]
                
                for selector in desc_selectors:
                    desc_elem = element.select_one(selector)
                    if desc_elem:
                        desc_text = desc_elem.get_text(strip=True)
                        if desc_text and desc_text != title and not re.match(r'^\d{1,2}\s*[–-]\s*\d{1,2}\s*(AM|PM)$', desc_text, re.I):
                            # Clean up the description, removing title duplication
                            cleaned_desc = self._clean_title_description(desc_text, time_slot, is_description=True, title=title)
                            # Make sure it's different from title and meaningful
                            if cleaned_desc and cleaned_desc != title and len(cleaned_desc) > 5:
                                description = cleaned_desc
                                break
            
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
                return {
                    'time_slot': time_slot,
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
    
    def save_to_csv(self, shows: List[Dict], filename: str = "apple_music_schedule.csv"):
        """Save schedule data to CSV file."""
        if not shows:
            print("No shows to save to CSV")
            return
            
        # Get current time in Pacific Time
        pacific_tz = pytz.timezone('America/Los_Angeles')
        scraped_at = datetime.now(pacific_tz).isoformat()
        
        # Prepare data for CSV with new column order
        csv_data = []
        for show in shows:
            time_slot_utc = show.get('time_slot', '')
            time_slot_pacific = self._convert_utc_to_pacific(time_slot_utc)
            
            csv_data.append({
                'station': show.get('station', ''),
                'time_slot_pacific': time_slot_pacific,
                'show_title': show.get('title', ''),
                'description': show.get('description', ''),
                'time_slot_utc': time_slot_utc,
                'show_image_url': show.get('artwork_url', ''),
                'show_url': show.get('show_url', ''),
                'scraped_at': scraped_at
            })
        
        # Create DataFrame and save to CSV
        df = pd.DataFrame(csv_data)
        df.to_csv(filename, index=False, encoding='utf-8')
        print(f"Schedule saved to {filename}")

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