import os
import logging
import asyncio
from datetime import datetime
import pytz
import gspread
from google.oauth2.service_account import Credentials
from dotenv import load_dotenv

# Set up logging
logger = logging.getLogger("DailyActivityBot.SpreadsheetUtils")

load_dotenv()

# Global Lock to prevent concurrent write operations to the Google Sheet
sheet_lock = asyncio.Lock()

# Scopes required for Google Sheets and Drive API
SCOPES = [
    "https://www.googleapis.com/auth/spreadsheets",
    "https://www.googleapis.com/auth/drive"
]

def _get_client():
    """Helper to authenticate and return a gspread client (runs synchronously)."""
    creds_path = os.getenv("GOOGLE_CREDS_FILE", "credentials.json")
    if not os.path.exists(creds_path):
        raise FileNotFoundError(
            f"Credentials file not found at '{creds_path}'. "
            f"Please download your service account JSON and place it in the root directory."
        )
    creds = Credentials.from_service_account_file(creds_path, scopes=SCOPES)
    return gspread.authorize(creds)

async def init_spreadsheet():
    """
    Asynchronously checks and initializes the worksheets and headers in Google Sheets.
    If the sheet or worksheets do not exist, it sets them up.
    """
    async with sheet_lock:
        try:
            # Run the synchronous gspread connection in a separate thread
            client = await asyncio.to_thread(_get_client)
            sheet_name = os.getenv("GOOGLE_SHEET_NAME", "Daily Activity Tracker")
            
            try:
                spreadsheet = await asyncio.to_thread(client.open, sheet_name)
            except gspread.exceptions.SpreadsheetNotFound:
                logger.error(
                    f"Spreadsheet '{sheet_name}' not found. Make sure you created it "
                    f"and shared it with the client email in your service account credentials."
                )
                raise
            
            # Initialize Activity Log sheet
            try:
                activity_ws = await asyncio.to_thread(spreadsheet.worksheet, "Activity Log")
            except gspread.exceptions.WorksheetNotFound:
                logger.info("Creating 'Activity Log' worksheet...")
                activity_ws = await asyncio.to_thread(
                    spreadsheet.add_worksheet, title="Activity Log", rows=1000, cols=8
                )
                headers = ["Date", "Category", "Topic", "Start Time", "End Time", "Status", "Duration (Hours)", "Timestamp"]
                await asyncio.to_thread(activity_ws.append_row, headers)
            
            # Initialize Habit & Sleep Tracker sheet
            try:
                habit_ws = await asyncio.to_thread(spreadsheet.worksheet, "Habit & Sleep Tracker")
            except gspread.exceptions.WorksheetNotFound:
                logger.info("Creating 'Habit & Sleep Tracker' worksheet...")
                habit_ws = await asyncio.to_thread(
                    spreadsheet.add_worksheet, title="Habit & Sleep Tracker", rows=1000, cols=6
                )
                headers = ["Date", "Wake Up 5AM", "Sleep 10PM", "Location Safe", "90/20 Break", "Timestamp"]
                await asyncio.to_thread(habit_ws.append_row, headers)
                
            logger.info("Google Sheets initialized successfully.")
        except Exception as e:
            logger.error(f"Error during Google Sheets initialization: {e}")
            raise

async def log_activity(date_str, category, topic, start_time, end_time, status, duration):
    """
    Logs an activity entry (dynamic plan, completed or missed) to the Activity Log sheet.
    """
    async with sheet_lock:
        try:
            client = await asyncio.to_thread(_get_client)
            sheet_name = os.getenv("GOOGLE_SHEET_NAME", "Daily Activity Tracker")
            spreadsheet = await asyncio.to_thread(client.open, sheet_name)
            ws = await asyncio.to_thread(spreadsheet.worksheet, "Activity Log")
            
            tz_str = os.getenv("TIMEZONE", "Asia/Jakarta")
            local_tz = pytz.timezone(tz_str)
            timestamp = datetime.now(local_tz).strftime("%Y-%m-%d %H:%M:%S")
            
            row_data = [date_str, category, topic, start_time, end_time, status, duration, timestamp]
            await asyncio.to_thread(ws.append_row, row_data)
            logger.info(f"Successfully logged activity '{topic}' to Activity Log.")
            return True
        except Exception as e:
            logger.error(f"Failed to log activity: {e}")
            return False

async def update_activity_status(category, topic, status):
    """
    Finds the last 'Pending' activity entry for a given category and topic
    and updates its status to 'Completed' or 'Missed'.
    """
    async with sheet_lock:
        try:
            client = await asyncio.to_thread(_get_client)
            sheet_name = os.getenv("GOOGLE_SHEET_NAME", "Daily Activity Tracker")
            spreadsheet = await asyncio.to_thread(client.open, sheet_name)
            ws = await asyncio.to_thread(spreadsheet.worksheet, "Activity Log")
            
            # Fetch all rows from the worksheet
            records = await asyncio.to_thread(ws.get_all_records)
            
            # Look from the bottom (latest) to find a matching "Pending" activity
            row_index = -1
            # get_all_records returns dictionaries; worksheet rows are 1-indexed, headers are row 1
            for i, record in enumerate(reversed(records)):
                if (record.get("Category") == category and 
                    record.get("Topic") == topic and 
                    record.get("Status") == "Pending"):
                    # Calculate correct row index (records is 0-indexed, reversed, so length - i + 1)
                    # +1 because spreadsheet is 1-indexed, +1 because headers occupy row 1
                    row_index = len(records) - i + 1
                    break
            
            if row_index != -1:
                # Column 6 is "Status" (Date, Category, Topic, Start Time, End Time, Status)
                await asyncio.to_thread(ws.update_cell, row_index, 6, status)
                logger.info(f"Updated activity '{topic}' status to '{status}' at row {row_index}.")
                return True
            else:
                logger.warning(f"No pending activity found for Category: {category}, Topic: {topic}.")
                return False
        except Exception as e:
            logger.error(f"Failed to update activity status: {e}")
            return False

async def log_habit_and_sleep(date_str, field_name, value):
    """
    Logs or updates a habit metric for a specific date in the Habit & Sleep Tracker.
    This performs a date-based upsert (one row per date).
    
    Fields supported:
      - 'Wake Up 5AM'
      - 'Sleep 10PM'
      - 'Location Safe'
      - '90/20 Break'
    """
    async with sheet_lock:
        try:
            client = await asyncio.to_thread(_get_client)
            sheet_name = os.getenv("GOOGLE_SHEET_NAME", "Daily Activity Tracker")
            spreadsheet = await asyncio.to_thread(client.open, sheet_name)
            ws = await asyncio.to_thread(spreadsheet.worksheet, "Habit & Sleep Tracker")
            
            # Fields and their corresponding column index
            # Columns: ["Date", "Wake Up 5AM", "Sleep 10PM", "Location Safe", "90/20 Break", "Timestamp"]
            field_cols = {
                "Wake Up 5AM": 2,
                "Sleep 10PM": 3,
                "Location Safe": 4,
                "90/20 Break": 5
            }
            
            if field_name not in field_cols:
                logger.error(f"Unsupported habit field: {field_name}")
                return False
            
            col_idx = field_cols[field_name]
            records = await asyncio.to_thread(ws.get_all_records)
            
            row_index = -1
            for i, record in enumerate(records):
                if record.get("Date") == date_str:
                    row_index = i + 2  # +2 due to 1-indexed spreadsheet and headers row
                    break
            
            tz_str = os.getenv("TIMEZONE", "Asia/Jakarta")
            local_tz = pytz.timezone(tz_str)
            timestamp = datetime.now(local_tz).strftime("%Y-%m-%d %H:%M:%S")
            
            if row_index != -1:
                # Row exists, update the specific cell and the timestamp
                await asyncio.to_thread(ws.update_cell, row_index, col_idx, value)
                await asyncio.to_thread(ws.update_cell, row_index, 6, timestamp)
                logger.info(f"Updated habit '{field_name}' to '{value}' for date {date_str}.")
            else:
                # Row does not exist, append a new row
                # Columns: Date, Wake Up 5AM, Sleep 10PM, Location Safe, 90/20 Break, Timestamp
                row_data = [date_str, "", "", "", "", timestamp]
                # Insert the value in the correct index (0-indexed list equivalent)
                row_data[col_idx - 1] = value
                await asyncio.to_thread(ws.append_row, row_data)
                logger.info(f"Appended new habit row for date {date_str} with {field_name} = {value}.")
                
            return True
        except Exception as e:
            logger.error(f"Failed to log habit/sleep: {e}")
            return False
