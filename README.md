# Apple Music Radio Schedule Scraper

A Python script that scrapes schedule information from multiple Apple Music radio stations and outputs the data in CSV and JSON formats.

## Features

- Scrapes 6 Apple Music radio stations:
  - Apple Music 1
  - Apple Music Hits
  - Apple Music Country
  - Apple Music Club
  - Apple Music Chill
  - Apple Music Classical

- Extracts show information including:
  - Station name
  - Time slot
  - Show title
  - Description
  - Image URL
  - Show URL

- Outputs data in both CSV and JSON formats
- Automated scraping via GitHub Actions (runs every 6 hours)

## Installation

1. Clone the repository
2. Create a virtual environment:
   ```bash
   python3 -m venv venv
   source venv/bin/activate
   ```
3. Install dependencies:
   ```bash
   pip install -r requirements.txt
   playwright install chromium
   ```

## Usage

Run the scraper:
```bash
python scrape_apple_music_schedule.py
```

This will create two output files:
- `apple_music_schedule.csv` - CSV format with columns: station, time_slot, show_title, description, image_url, show_url, scraped_at
- `apple_music_schedule.json` - JSON format with metadata and show details

## GitHub Actions

The repository includes a GitHub Actions workflow that:
- Runs automatically every 6 hours
- Can be triggered manually
- Commits updated schedule data
- Uploads artifacts for each run

## Output Format

### CSV Columns
- `station`: Radio station name
- `time_slot`: Show time (e.g., "2 – 4 AM")
- `show_title`: Name of the show
- `description`: Show description
- `image_url`: Artwork/image URL
- `show_url`: Link to show page
- `scraped_at`: Timestamp of data collection

## Radio Stations

- **Apple Music 1**: `https://music.apple.com/us/radio/ra.978194965`
- **Apple Music Hits**: `https://music.apple.com/us/radio/ra.1498155548`
- **Apple Music Country**: `https://music.apple.com/us/radio/ra.1498157166`
- **Apple Music Club**: `https://music.apple.com/us/radio/ra.1740613864`
- **Apple Music Chill**: `https://music.apple.com/us/radio/ra.1740613859`
- **Apple Music Classical**: `https://music.apple.com/us/radio/ra.1740614260`