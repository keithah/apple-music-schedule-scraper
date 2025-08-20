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
from typing import List, Dict, Optional

class AppleMusicScheduleScraper:
    def __init__(self):
        self.stations = {
            "Apple Music 1": "https://music.apple.com/us/radio/ra.978194965",
            "Apple Music Hits": "https://music.apple.com/us/radio/ra.1498155548", 
            "Apple Music Country": "https://music.apple.com/us/radio/ra.1498157166",
            "Apple Music Club": "https://music.apple.com/us/radio/ra.1740613864",
            "Apple Music Chill": "https://music.apple.com/us/radio/ra.1740613859",
            "Apple Music Classical": "https://music.apple.com/us/radio/ra.1740614260"
        }
        
    def fetch_page(self, url: str) -> tuple[Optional[str], dict]:
        """Fetch a specific Apple Music radio page using Playwright and extract image URLs."""
        try:
            with sync_playwright() as p:
                browser = p.chromium.launch(headless=True)
                page = browser.new_page()
                
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
    
    def extract_show_data(self, element, image_data: dict = None) -> Optional[Dict]:
        """Extract show data from a schedule element."""
        try:
            # Get all text content
            full_text = element.get_text(separator=' ', strip=True)
            
            # Extract time slot
            time_match = re.search(r'(\d{1,2}\s*[–-]\s*\d{1,2}\s*(AM|PM))', full_text, re.I)
            time_slot = time_match.group(1) if time_match else None
            
            # Extract show title - look for various title patterns
            title = None
            
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
                        # Remove time slot from beginning of title if it exists
                        if time_slot:
                            candidate_title = re.sub(r'^' + re.escape(time_slot) + r'\s*', '', candidate_title)
                        title = candidate_title
                        break
            
            # If no title found, try to extract from structured text
            if not title and full_text:
                lines = [line.strip() for line in full_text.split('\n') if line.strip()]
                for line in lines:
                    # Skip time-only lines
                    if re.match(r'^\d{1,2}\s*[–-]\s*\d{1,2}\s*(AM|PM)$', line, re.I):
                        continue
                    # Take the first non-time line as potential title
                    if line and len(line) > 3:
                        # Remove time slot from beginning of title if it exists
                        if time_slot:
                            line = re.sub(r'^' + re.escape(time_slot) + r'\s*', '', line)
                        title = line
                        break
            
            # Extract description
            description = None
            desc_selectors = [
                '[class*="description"]', '[class*="subtitle"]', 
                'p', '.typography-body', '[class*="summary"]'
            ]
            
            for selector in desc_selectors:
                desc_elem = element.select_one(selector)
                if desc_elem:
                    desc_text = desc_elem.get_text(strip=True)
                    if desc_text and desc_text != title and not re.match(r'^\d{1,2}\s*[–-]\s*\d{1,2}\s*(AM|PM)$', desc_text, re.I):
                        # Remove time slot from beginning of description if it exists
                        if time_slot:
                            desc_text = re.sub(r'^' + re.escape(time_slot) + r'\s*', '', desc_text)
                        description = desc_text
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
        with open(filename, 'w', encoding='utf-8') as f:
            json.dump({
                'scraped_at': datetime.now().isoformat(),
                'stations_scraped': list(self.stations.keys()),
                'shows': shows
            }, f, indent=2, ensure_ascii=False)
        print(f"Schedule saved to {filename}")
    
    def save_to_csv(self, shows: List[Dict], filename: str = "apple_music_schedule.csv"):
        """Save schedule data to CSV file."""
        if not shows:
            print("No shows to save to CSV")
            return
            
        # Prepare data for CSV
        csv_data = []
        for show in shows:
            csv_data.append({
                'station': show.get('station', ''),
                'time_slot': show.get('time_slot', ''),
                'show_title': show.get('title', ''),
                'description': show.get('description', ''),
                'image_url': show.get('artwork_url', ''),
                'show_url': show.get('show_url', ''),
                'scraped_at': datetime.now().isoformat()
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