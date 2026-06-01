# Daily Activity Tracker Bot

An end-to-end, professionally structured Telegram bot built with Python 3, leveraging `python-telegram-bot` (v20+ with asyncio) and `gspread` (Google Sheets API) for cloud-based activity and habit logging. This bot acts as a personal productivity assistant, scheduling daily habits, sleep monitoring (10:00 PM sleep / 5:00 AM wake), study session pre-alerts, post-session check-ins, and providing a psychological disruption mechanism `/sos` during closed relaxing periods.

---

## 📂 Repository Structure

```
daily activites notification/
│
├── .env.example              # Environment variables template
├── .gitignore                # File to exclude secrets and credential files from Git
├── requirements.txt          # Project dependencies
├── README.md                 # Project documentation
│
├── credentials.json          # Google Service Account credentials (user-provided, git-ignored)
├── spreadsheet_utils.py      # Google Sheets interface using gspread and google-auth
├── bot_handlers.py           # Commands, conversation flows, callbacks, and inline keyboards
└── main.py                   # Telegram Application init, scheduler, and active polling
```

---

## 🛠️ Tech Stack & Dependencies

- **Language:** Python 3.8+ (asyncio native)
- **Framework:** `python-telegram-bot[job-queue]` (v20+)
- **Storage:** Google Sheets API via `gspread` and `google-auth`
- **Secrets Management:** `python-dotenv`
- **Timezone Management:** `pytz` (handling `Asia/Jakarta` WIB time for task schedules)

---

## ⚡ Core Features

1. **Environment Configuration & Security Access-Control:** 
   - Utilizes `.env` to protect sensitive tokens (`TELEGRAM_BOT_TOKEN`, `TELEGRAM_CHAT_ID`).
   - Implements a custom authorization gate decorator to block unauthorized users, protecting spreadsheet privacy.
2. **Cloud Spreadsheet Logging (Google Sheets):**
   - Automatically establishes structure and column headers if missing:
     - **Activity Log:** Date, Category, Topic, Start Time, End Time, Status (Pending, Completed, Missed), Duration (Hours), Timestamp.
     - **Habit & Sleep Tracker:** Date, Wake Up 5AM (Yes/No), Sleep 10PM (Yes/No), Location Safe (Yes/No), 90/20 Break (Yes/No), Timestamp.
3. **Automated Sleep Schedule Tracking:**
   - Sleep Goal: **22:00 WIB** | Wake-Up Goal: **05:00 WIB**.
   - Dispatches a daily wind-down reminder at **21:45 WIB** to prepare for the 22:00 sleep threshold.
   - Dispatches a wake-up log check at **05:15 WIB** querying whether the 05:00 waking habit was met.
4. **Command `/plan` (Dynamic Study Session Scheduling):**
   - Launches a sequential wizard via `ConversationHandler`:
     1. Choose Category (`Coding`, `Reading`, `Relaxing`, `Daily Obligations`).
     2. Input specific Topic or Task details.
     3. Input Start Time (e.g. `15:30` or `in 15m`).
     4. Input Duration in hours/minutes.
   - Dynamically registers background scheduler jobs:
     - **Pre-Activity Warning:** Triggers 5-10 minutes prior to the study session to notify the user.
     - **Post-Activity Check-In:** Prompts the user with inline buttons ("Did you complete it?") as soon as the study block ends.
5. **Command `/habit_check`:**
   - Presents an inline keyboard checklist to log daily wellness habits, including the 90/20 break rule and workspace safety.
6. Command `/sos` & Anti-Gagal-Fokus Alert:
   - An emergency interrupter to break negative habits or lapses in concentration. Delivers immediate psychological disruption instructions, including a physical grounding directive to immediately do 5 push-ups, followed by mental grounding exercises.
   - Proactively reminds the user to maintain open surroundings and high awareness during "Relaxing" hours.

---

## ⚙️ Google Sheets API Setup

The bot stores logs directly in Google Sheets. To connect your Google Account:

1. **Create a Google Cloud Project:**
   - Go to the [Google Cloud Console](https://console.cloud.google.com/).
   - Create a new project.
2. **Enable APIs:**
   - Search for and enable the **Google Drive API** and the **Google Sheets API**.
3. **Create a Service Account:**
   - Go to **APIs & Services > Credentials**.
   - Click **Create Credentials** and choose **Service Account**.
   - Assign a name, skip role assignments, and click **Done**.
4. **Generate Keys:**
   - Click on the newly created Service Account under the list.
   - Navigate to the **Keys** tab, click **Add Key > Create New Key**, choose **JSON**, and download it.
5. **Save credentials:**
   - Move the downloaded JSON file into the root of this project and rename it to `credentials.json`.
6. **Create a Spreadsheet:**
   - Create a new Google Sheet named `Daily Activity Tracker` (or matching `GOOGLE_SHEET_NAME` in `.env`).
   - Open the spreadsheet, look at the URL, and ensure it contains standard columns (the bot will auto-generate sheets if you share it correctly).
   - Look inside `credentials.json` for the `client_email` field.
   - Click **Share** on your Google Sheet and add this email as an **Editor**.

---

## 🚀 Installation & Local Execution

### 1. Installation
```bash
# Navigate to project directory
cd "daily activites notification"

# Set up virtual environment
python -m venv venv
# Activate it
.\venv\Scripts\Activate.ps1   # PowerShell
# or
source venv/bin/activate       # Unix

# Install packages
pip install -r requirements.txt
```

### 2. Configuration
Copy the `.env.example` file to `.env` and fill in the values:
```bash
cp .env.example .env
```
Open `.env` and update:
```ini
TELEGRAM_BOT_TOKEN=1234567890:ABCdefGhIJKlmNoPQRsTUVwxyZ
TELEGRAM_CHAT_ID=987654321
GOOGLE_SHEET_NAME=Daily Activity Tracker
GOOGLE_CREDS_FILE=credentials.json
TIMEZONE=Asia/Jakarta
```

### 3. Running the Bot
```bash
python main.py
```

Upon launching, the bot connects to the Google Sheets API, validates worksheet structures, and registers your recurring sleep-wake scheduler routines.
