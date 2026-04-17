"""
Scrapes Profile Performance stats from Psychology Today and stores a
daily snapshot in the central dashboard DB.

Called from each optimizer's engagement.py after the touch completes,
passing in the already-logged-in Playwright page object.
"""

import sys
import os
import logging
import subprocess
from datetime import date

# Allow importing from pt_dashboard regardless of calling directory
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from sheets_db import init_sheet, upsert_snapshot

logger = logging.getLogger(__name__)

# Selectors for the Profile Performance section
STATS_URL = "https://member.psychologytoday.com/us/home"


def _windows_alert(profile_name, reason):
    """Pop a Windows notification when stats collection fails."""
    message = f"PT stats collection failed for {profile_name}: {reason}"
    try:
        subprocess.run([
            "powershell", "-NoProfile", "-Command",
            f"""
            Add-Type -AssemblyName System.Windows.Forms
            [System.Windows.Forms.MessageBox]::Show(
                '{message}',
                'PT Dashboard Alert',
                [System.Windows.Forms.MessageBoxButtons]::OK,
                [System.Windows.Forms.MessageBoxIcon]::Warning
            )
            """
        ], timeout=10)
    except Exception:
        pass  # Don't crash the touch if the alert itself fails


async def scrape_stats(page, profile_name: str):
    """
    Scrape stats from the PT dashboard page (already logged in).
    Stores snapshot in dashboard DB. Shows Windows alert on failure.
    """
    init_sheet()
    today = date.today().isoformat()

    try:
        # Navigate to dashboard if not already there
        if "member.psychologytoday.com/us/home" not in page.url:
            await page.goto(STATS_URL, wait_until="domcontentloaded")
            await page.wait_for_timeout(2000)

        # Wait for the Profile Performance section to render
        await page.wait_for_selector("text=Profile Performance", timeout=15000)
        await page.wait_for_selector("text=Total Contacts", timeout=10000)
        await page.wait_for_timeout(2000)  # Let numbers finish loading

        def safe_int(s):
            try:
                return int(str(s).strip().replace(",", ""))
            except (ValueError, AttributeError):
                return 0

        # Grab all visible text and parse — much more reliable than DOM selectors
        body_text = await page.inner_text("body")
        lines = [l.strip() for l in body_text.splitlines() if l.strip()]

        def value_after(label):
            """Return the first numeric token that follows a line matching label."""
            for i, line in enumerate(lines):
                if line == label:
                    # Look ahead up to 3 lines for a number
                    for j in range(i + 1, min(i + 4, len(lines))):
                        candidate = lines[j].replace(",", "")
                        if candidate.isdigit():
                            return int(candidate)
            return 0

        total_contacts = value_after("Total Contacts")
        calls          = value_after("Calls")
        emails         = value_after("Emails")
        web_visits     = value_after("Web Visits")

        # Profile Views and Results Views appear as "Profile Views: \n170"
        profile_views = results_views = 0
        for i, line in enumerate(lines):
            if line.startswith("Profile Views"):
                # number may be on same line or next line
                rest = line.replace("Profile Views:", "").replace("Profile Views", "").strip()
                if rest.replace(",", "").isdigit():
                    profile_views = safe_int(rest)
                elif i + 1 < len(lines) and lines[i + 1].replace(",", "").isdigit():
                    profile_views = safe_int(lines[i + 1])
            if line.startswith("Results Views"):
                rest = line.replace("Results Views:", "").replace("Results Views", "").strip()
                if rest.replace(",", "").isdigit():
                    results_views = safe_int(rest)
                elif i + 1 < len(lines) and lines[i + 1].replace(",", "").isdigit():
                    results_views = safe_int(lines[i + 1])

        # Sanity check — if everything is 0, something likely didn't load
        if total_contacts == 0 and profile_views == 0 and results_views == 0:
            raise ValueError("All stats read as zero — page may not have loaded correctly")

        upsert_snapshot(
            profile_name=profile_name,
            date=today,
            total_contacts=total_contacts,
            calls=calls,
            emails=emails,
            web_visits=web_visits,
            profile_views=profile_views,
            results_views=results_views,
        )
        logger.info(
            f"Stats saved for {profile_name}: contacts={total_contacts}, "
            f"calls={calls}, emails={emails}, web_visits={web_visits}, "
            f"profile_views={profile_views}, results_views={results_views}"
        )

    except Exception as e:
        logger.error(f"Stats collection failed for {profile_name}: {e}")
        _windows_alert(profile_name, str(e))
