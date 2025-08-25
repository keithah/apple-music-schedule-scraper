# Apple Music Radio Schedule Scraper

A Python script that scrapes schedule information from multiple Apple Music radio stations and outputs the data in CSV and JSON formats.

## Features

- Scrapes 6 Apple Music radio stations:
  - Apple Music 1
  - Apple Music Hits
  - Apple Music Country
  - Apple Music Club
  - Apple Music Chill
  - Apple Música Uno

- Extracts show information including:
  - Station name
  - Time slot
  - Show title
  - Description
  - Image URL
  - Show URL

- Outputs data in both CSV and JSON formats with dual time zones
- Converts UTC schedule times to Pacific Time automatically
- Automated scraping via GitHub Actions (runs twice daily at 1:30 AM and 1:30 PM Pacific Time)

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
- `apple_music_schedule.csv` - CSV format with time zones and show details
- `apple_music_schedule.json` - JSON format with metadata and show details

## GitHub Actions

The repository includes a GitHub Actions workflow that:
- Runs automatically twice daily at 8:30 AM and 8:30 PM UTC (1:30 AM and 1:30 PM Pacific Time)
- Can be triggered manually via workflow dispatch
- Auto-triggers when scraper code, requirements, or workflow files are pushed
- Commits updated schedule data with UTC to Pacific time conversion
- Uploads artifacts for each run

## Output Format

### CSV Columns
- `station`: Radio station name
- `time_slot_pacific`: Show time in Pacific Time (e.g., "2PM – 4PM")
- `show_title`: Name of the show
- `description`: Show description
- `time_slot_utc`: Show time in UTC (e.g., "9 – 11 PM")
- `show_image_url`: Artwork/image URL
- `show_url`: Link to show page
- `scraped_at`: Timestamp of data collection in Pacific Time

## Radio Stations

- **Apple Music 1**: `https://music.apple.com/us/radio/ra.978194965`
- **Apple Music Hits**: `https://music.apple.com/us/radio/ra.1498155548`
- **Apple Music Country**: `https://music.apple.com/us/radio/ra.1498157166`
- **Apple Music Club**: `https://music.apple.com/radio/ra.1740613859`
- **Apple Music Chill**: `https://music.apple.com/radio/ra.1740614260`
- **Apple Música Uno**: `https://music.apple.com/radio/ra.1740613864`