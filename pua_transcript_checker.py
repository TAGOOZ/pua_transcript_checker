#!/usr/bin/env python3
"""
PUA Portal Transcript Checker
Logs into the PUA portal and checks for 2025 Fall courses.
Runs every hour and sends Telegram notification when Fall semester is found.
"""

import requests
from bs4 import BeautifulSoup
import re
import os
import time
from datetime import datetime

# Configuration - Use environment variables for sensitive data
USERNAME = os.environ.get("PUA_USERNAME", "")
PASSWORD = os.environ.get("PUA_PASSWORD", "")

# Telegram configuration
TELEGRAM_BOT_TOKEN = os.environ.get("TELEGRAM_BOT_TOKEN", "")
TELEGRAM_CHAT_ID = os.environ.get("TELEGRAM_CHAT_ID", "")

# Run mode: "once" for cron job, "loop" for continuous running
RUN_MODE = os.environ.get("RUN_MODE", "once")
CHECK_INTERVAL_SECONDS = int(os.environ.get("CHECK_INTERVAL_SECONDS", "3600"))  # Default 1 hour

BASE_URL = "https://portal.pua.edu.eg"
LOGIN_URL = f"{BASE_URL}/SelfService/Login.aspx?ReturnUrl=%2fSelfService%2fRecords%2fTranscripts.aspx"
TRANSCRIPT_URL = f"{BASE_URL}/SelfService/Records/Transcripts.aspx"

HEADERS = {
    'accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,image/apng,*/*;q=0.8,application/signed-exchange;v=b3;q=0.7',
    'accept-language': 'en-US,en;q=0.9',
    'cache-control': 'max-age=0',
    'content-type': 'application/x-www-form-urlencoded',
    'origin': BASE_URL,
    'referer': LOGIN_URL,
    'sec-ch-ua': '"Google Chrome";v="141", "Not?A_Brand";v="8", "Chromium";v="141"',
    'sec-ch-ua-mobile': '?0',
    'sec-ch-ua-platform': '"Linux"',
    'sec-fetch-dest': 'document',
    'sec-fetch-mode': 'navigate',
    'sec-fetch-site': 'same-origin',
    'sec-fetch-user': '?1',
    'upgrade-insecure-requests': '1',
    'user-agent': 'Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/141.0.0.0 Safari/537.36'
}


def log(message):
    """Print with timestamp."""
    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    print(f"[{timestamp}] {message}")


def retry_request(session, method, url, max_retries=3, **kwargs):
    """Make HTTP request with retry logic."""
    for attempt in range(max_retries):
        try:
            if method == 'GET':
                response = session.get(url, **kwargs)
            else:
                response = session.post(url, **kwargs)
            
            if response.status_code in [503, 502, 500]:
                wait_time = (attempt + 1) * 10  # 10s, 20s, 30s
                log(f"[!] Server error {response.status_code}, retrying in {wait_time}s... (attempt {attempt + 1}/{max_retries})")
                time.sleep(wait_time)
                continue
            
            return response
        except Exception as e:
            wait_time = (attempt + 1) * 10
            log(f"[!] Request failed: {e}, retrying in {wait_time}s... (attempt {attempt + 1}/{max_retries})")
            time.sleep(wait_time)
    
    return None


def get_login_tokens(session):
    """Fetch the login page and extract ASP.NET form tokens."""
    log("Fetching login page to get tokens...")
    response = retry_request(session, 'GET', LOGIN_URL, headers=HEADERS, timeout=30)
    
    if not response or response.status_code != 200:
        log(f"[!] Failed to fetch login page after retries")
        return None
    
    soup = BeautifulSoup(response.text, 'html.parser')
    
    tokens = {}
    viewstate = soup.find('input', {'name': '__VIEWSTATE'})
    viewstate_gen = soup.find('input', {'name': '__VIEWSTATEGENERATOR'})
    event_validation = soup.find('input', {'name': '__EVENTVALIDATION'})
    request_verification = soup.find('input', {'name': '__RequestVerificationToken'})
    
    if viewstate:
        tokens['__VIEWSTATE'] = viewstate.get('value', '')
    if viewstate_gen:
        tokens['__VIEWSTATEGENERATOR'] = viewstate_gen.get('value', '')
    if event_validation:
        tokens['__EVENTVALIDATION'] = event_validation.get('value', '')
    if request_verification:
        tokens['__RequestVerificationToken'] = request_verification.get('value', '')
    
    log(f"Extracted {len(tokens)} tokens")
    return tokens


def login(session, tokens):
    """Perform login to the portal."""
    log(f"Logging in as {USERNAME}...")
    
    form_data = {
        '__EVENTTARGET': '',
        '__EVENTARGUMENT': '',
        '__VIEWSTATE': tokens.get('__VIEWSTATE', ''),
        '__VIEWSTATEGENERATOR': tokens.get('__VIEWSTATEGENERATOR', ''),
        '__EVENTVALIDATION': tokens.get('__EVENTVALIDATION', ''),
        '__RequestVerificationToken': tokens.get('__RequestVerificationToken', ''),
        'ctl00$mainContent$lvLoginUser$ucLoginUser$lcLoginUser$UserName': USERNAME,
        'ctl00$mainContent$lvLoginUser$ucLoginUser$lcLoginUser$Password': PASSWORD,
        'ctl00$mainContent$lvLoginUser$ucLoginUser$lcLoginUser$LoginButton': 'Log In'
    }
    
    response = retry_request(session, 'POST', LOGIN_URL, headers=HEADERS, data=form_data, allow_redirects=True, timeout=30)
    
    if not response:
        log("[!] Login request failed after retries")
        return False
    
    if response.status_code == 200:
        if 'Login.aspx' in response.url and 'Please check your User Name' in response.text:
            log("[!] Login failed - invalid credentials")
            return False
        log(f"Login successful!")
        return True
    else:
        log(f"[!] Login request failed: {response.status_code}")
        return False


def get_transcripts(session):
    """Fetch the transcripts page."""
    log("Fetching transcripts page...")
    
    response = retry_request(session, 'GET', TRANSCRIPT_URL, headers=HEADERS, timeout=30)
    
    if not response or response.status_code != 200:
        log(f"[!] Failed to fetch transcripts after retries")
        return None
    
    if 'Login.aspx' in response.url:
        log("[!] Session expired - redirected to login")
        return None
    
    log("Transcripts page fetched successfully")
    return response.text


def extract_semester_data(header):
    """Extract courses and GPA from a semester section."""
    courses = []
    gpa = None
    
    parent_div = header.find_parent('div')
    if parent_div:
        next_sibling = parent_div.find_next_sibling('div')
        if next_sibling:
            course_table = next_sibling.find('table', class_='defaultTable')
            if course_table:
                rows = course_table.find_all('tr')
                for row in rows:
                    cells = row.find_all('td')
                    if cells and len(cells) >= 4:
                        course_code = cells[0].get_text(strip=True)
                        course_title = cells[1].get_text(strip=True)
                        grade = cells[3].get_text(strip=True) if len(cells) > 3 else ''
                        
                        if course_code:
                            courses.append({
                                'code': course_code,
                                'title': course_title,
                                'grade': grade
                            })
    
    # Find the GPA table (after courses table)
    # Look for "Overall:" row with GPA value
    all_tables = parent_div.find_next_siblings('table')
    for table in all_tables:
        overall_row = table.find('td', string=re.compile(r'Overall:', re.IGNORECASE))
        if overall_row:
            row = overall_row.find_parent('tr')
            if row:
                cells = row.find_all('td')
                if len(cells) >= 8:  # GPA is the last column
                    gpa = cells[-1].get_text(strip=True)
                    break
    
    return courses, gpa


def parse_transcript_courses(html_content):
    """Parse the transcripts page looking for 2025 Fall, fallback to 2025 Spring."""
    soup = BeautifulSoup(html_content, 'html.parser')
    
    # First, try to find 2025 Fall (the target)
    fall_2025_header = soup.find('h2', class_='transcripts', string=re.compile(r'2025\s*Fall', re.IGNORECASE))
    
    if fall_2025_header:
        log("🎉 Found '2025 Fall' section!")
        courses, gpa = extract_semester_data(fall_2025_header)
        return {'semester': '2025 Fall', 'courses': courses, 'gpa': gpa, 'is_target': True}
    
    # 2025 Fall not found, check for 2025 Spring
    log("'2025 Fall' NOT found yet!")
    
    spring_2025_header = soup.find('h2', class_='transcripts', string=re.compile(r'2025\s*Spring', re.IGNORECASE))
    
    if spring_2025_header:
        log("Found '2025 Spring' - Fall semester not released yet")
        courses, gpa = extract_semester_data(spring_2025_header)
        return {'semester': '2025 Spring', 'courses': courses, 'gpa': gpa, 'is_target': False}
    
    return None


def send_telegram_notification(message):
    """Send notification via Telegram."""
    if not TELEGRAM_BOT_TOKEN or not TELEGRAM_CHAT_ID:
        log("[!] Telegram not configured - skipping notification")
        return False
    
    url = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/sendMessage"
    data = {
        'chat_id': TELEGRAM_CHAT_ID,
        'text': message,
        'parse_mode': 'HTML'
    }
    
    try:
        response = requests.post(url, data=data, timeout=10)
        if response.status_code == 200:
            log("✅ Telegram notification sent!")
            return True
        else:
            log(f"[!] Telegram notification failed: {response.status_code}")
            return False
    except Exception as e:
        log(f"[!] Telegram error: {e}")
        return False


def format_telegram_message(result):
    """Format courses for Telegram."""
    if result['is_target']:
        message = "🎉 <b>2025 Fall Courses Released!</b>\n\n"
    else:
        message = "⏳ <b>2025 Fall NOT out yet</b>\n"
        message += f"<i>Latest: {result['semester']}</i>\n\n"
    
    for course in result['courses']:
        message += f"<b>{course['code']}</b> - {course['title']}: <b>{course['grade']}</b>\n"
    
    if result.get('gpa'):
        message += f"\n📊 <b>Overall GPA: {result['gpa']}</b>"
    
    return message


def check_transcript():
    """Main check function - returns True if 2025 Fall is found."""
    log("=" * 50)
    log("Starting transcript check...")
    log("=" * 50)
    
    session = requests.Session()
    
    try:
        # Get login tokens
        tokens = get_login_tokens(session)
        if not tokens:
            return False
        
        # Login
        if not login(session, tokens):
            return False
        
        # Get transcripts
        html_content = get_transcripts(session)
        if not html_content:
            return False
        
        # Parse for 2025 Fall
        result = parse_transcript_courses(html_content)
        
        if result and result['courses']:
            log(f"Semester: {result['semester']}")
            log(f"Courses found: {len(result['courses'])}")
            
            for course in result['courses']:
                log(f"  - {course['code']}: {course['title']} ({course['grade']})")
            
            # Send Telegram notification always
            telegram_message = format_telegram_message(result)
            send_telegram_notification(telegram_message)
            
            if result['is_target']:
                return True  # Target found!
            else:
                return False
        else:
            log("No transcript data found")
            return False
            
    except Exception as e:
        log(f"[!] Error during check: {e}")
        return False


def main():
    log("=" * 50)
    log("PUA Portal Transcript Checker")
    log(f"Target: 2025 Fall")
    log(f"Mode: {RUN_MODE}")
    log("=" * 50)
    
    if RUN_MODE == "loop":
        # Continuous mode - keep running
        log(f"Running in loop mode, checking every {CHECK_INTERVAL_SECONDS} seconds")
        
        while True:
            found = check_transcript()
            
            if found:
                log("🎉 TARGET FOUND! 2025 Fall is available!")
                log("Continuing to monitor for updates...")
            
            log(f"Next check in {CHECK_INTERVAL_SECONDS} seconds...")
            time.sleep(CHECK_INTERVAL_SECONDS)
    else:
        # Single run mode (for cron jobs)
        check_transcript()
        log("Single check complete.")


if __name__ == "__main__":
    main()
