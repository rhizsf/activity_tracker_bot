import os
import logging
import asyncio
from datetime import datetime, timedelta
import pytz
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import (
    ContextTypes,
    ConversationHandler,
)
import spreadsheet_utils

# Set up logging
logger = logging.getLogger("DailyActivityBot.Handlers")

# Conversation States
CATEGORY, TOPIC, START_TIME, DURATION = range(4)

# Categories Mapping
CATEGORIES = {
    "1": "Coding",
    "2": "Reading",
    "3": "Relaxing",
    "4": "Daily Obligations"
}

def authorized_only(func):
    """
    Decorator to ensure that only the authorized TELEGRAM_CHAT_ID 
    can execute bot commands and receive reminders.
    """
    async def wrapper(update: Update, context: ContextTypes.DEFAULT_TYPE, *args, **kwargs):
        chat_id = os.getenv("TELEGRAM_CHAT_ID")
        if not chat_id:
            logger.warning("TELEGRAM_CHAT_ID is not configured in .env. Skipping check.")
            return await func(update, context, *args, **kwargs)
        
        try:
            authorized_id = int(chat_id)
        except ValueError:
            logger.error("Invalid TELEGRAM_CHAT_ID in .env. Must be an integer.")
            return
        
        current_id = None
        if update.effective_chat:
            current_id = update.effective_chat.id
        
        if current_id != authorized_id:
            logger.warning(f"Unauthorized access attempt by Chat ID: {current_id}")
            if update.message:
                await update.message.reply_text("⛔ Access Denied: You are not authorized to use this bot.")
            elif update.callback_query:
                await update.callback_query.answer("⛔ Access Denied.", show_alert=True)
            return
        
        return await func(update, context, *args, **kwargs)
    return wrapper

def get_tz():
    """Helper to retrieve local timezone."""
    tz_str = os.getenv("TIMEZONE", "Asia/Jakarta")
    return pytz.timezone(tz_str)

@authorized_only
async def start_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Greets the user and shows available commands and sleep goals with interactive buttons."""
    welcome_text = (
        "📊 **Daily Activity Tracker Bot**\n\n"
        "Welcome! This bot helps you log your study plans and track your habits in real-time.\n\n"
        "🎯 **Target Routine Goals:**\n"
        "• Sleep: **22:00 WIB**\n"
        "• Wake Up: **05:00 WIB**\n\n"
        "🎛️ **Quick Actions Control Panel:**\n"
        "Select a button below to quickly run any action:"
    )
    keyboard = [
        [
            InlineKeyboardButton("📅 Plan Activity", callback_data="menu_plan"),
            InlineKeyboardButton("🧠 Habit Check", callback_data="menu_habit")
        ],
        [
            InlineKeyboardButton("🚨 Trigger SOS", callback_data="menu_sos"),
            InlineKeyboardButton("💡 Get Help", callback_data="menu_help")
        ]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)
    await update.message.reply_text(welcome_text, reply_markup=reply_markup, parse_mode="Markdown")

@authorized_only
async def help_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Provides detailed assistance and usage rules."""
    help_text = (
        "💡 **How to Use the Daily Activity Tracker Bot:**\n\n"
        "1️⃣ **Planning an Activity (`/plan`):**\n"
        "   - Select a category (Coding, Reading, Relaxing, or Obligations).\n"
        "   - Type in the topic description.\n"
        "   - Type the start time. Supports `14:30`, `in 10m` (minutes), or `now`.\n"
        "   - Type the duration. Supports `45m` (minutes) or `1.5h` / `2` (hours).\n"
        "   - **Pre-Activity Alert:** Triggers 10 minutes prior to warm up.\n"
        "   - **Post-Activity Check-In:** Prompts you at the end to check if you completed the task.\n\n"
        "2️⃣ **Daily Habits Check (`/habit_check`):**\n"
        "   - Log 90/20 breaks and learning environment safety.\n\n"
        "3️⃣ **Emergency Interrupter (`/sos`):**\n"
        "   - Use this command if you are experiencing focus lapses or negative urges during relaxing periods.\n"
        "   - Demands 5 push-ups and breathing exercises to break loops.\n\n"
        "4️⃣ **Automatic Reminders:**\n"
        "   - **21:45 WIB:** Sleep preparation alert.\n"
        "   - **05:15 WIB:** Morning wake-up check."
    )
    await update.message.reply_text(help_text, parse_mode="Markdown")

# --- /plan Conversation Handlers ---

@authorized_only
async def plan_start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Start of the activity planning wizard."""
    keyboard = [
        [InlineKeyboardButton("💻 Coding", callback_data="cat_1")],
        [InlineKeyboardButton("📚 Reading", callback_data="cat_2")],
        [InlineKeyboardButton("🧘 Relaxing", callback_data="cat_3")],
        [InlineKeyboardButton("🏛️ Daily Obligations", callback_data="cat_4")]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)
    text = "📋 Select the activity category:"
    if update.callback_query:
        query = update.callback_query
        await query.answer()
        await query.edit_message_text(text, reply_markup=reply_markup)
    else:
        await update.message.reply_text(text, reply_markup=reply_markup)
    return CATEGORY

async def plan_category_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Stores the chosen category and asks for the topic."""
    query = update.callback_query
    await query.answer()
    
    cat_code = query.data.split("_")[1]
    category = CATEGORIES.get(cat_code, "Other")
    context.user_data["plan_category"] = category
    
    await query.edit_message_text(
        text=f"📂 Category selected: **{category}**\n\n📝 Enter the specific topic or activity description:"
    )
    return TOPIC

async def plan_topic(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Stores the topic and asks for the start time with interactive options."""
    topic = update.message.text.strip()
    if not topic:
        await update.message.reply_text("Topic cannot be empty. Please enter a valid description:")
        return TOPIC
    
    context.user_data["plan_topic"] = topic
    
    keyboard = [
        [
            InlineKeyboardButton("⏰ Sekarang (Now)", callback_data="time_now"),
            InlineKeyboardButton("⏰ +15 Menit", callback_data="time_15m")
        ],
        [
            InlineKeyboardButton("⏰ +30 Menit", callback_data="time_30m"),
            InlineKeyboardButton("⌨️ Input Manual", callback_data="time_manual")
        ]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    start_info = (
        f"📝 Topic: **{topic}**\n\n"
        f"⏰ Kapan Anda ingin memulai aktivitas ini?\n"
        f"Pilih salah satu tombol interaktif di bawah atau klik 'Input Manual':"
    )
    await update.message.reply_text(start_info, reply_markup=reply_markup, parse_mode="Markdown")
    return START_TIME

async def plan_start_time_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Processes start time buttons and moves to duration selection."""
    query = update.callback_query
    await query.answer()
    
    selection = query.data
    local_tz = get_tz()
    now_local = datetime.now(local_tz)
    
    start_dt = None
    
    if selection == "time_now":
        start_dt = now_local
    elif selection == "time_15m":
        start_dt = now_local + timedelta(minutes=15)
    elif selection == "time_30m":
        start_dt = now_local + timedelta(minutes=30)
    elif selection == "time_manual":
        # Ask user to type it manually
        await query.edit_message_text(
            text=(
                "⏰ **Input Waktu Manual**\n\n"
                "Silakan ketik waktu mulai dalam format berikut:\n"
                "• `in 10m` (dalam 10 menit)\n"
                "• `18:30` (jam spesifik hari ini)"
            ),
            parse_mode="Markdown"
        )
        return START_TIME

    context.user_data["plan_start_dt"] = start_dt
    
    keyboard = [
        [
            InlineKeyboardButton("⏳ 30 Menit", callback_data="dur_30m"),
            InlineKeyboardButton("⏳ 45 Menit", callback_data="dur_45m")
        ],
        [
            InlineKeyboardButton("⏳ 1 Jam", callback_data="dur_1h"),
            InlineKeyboardButton("⏳ 1.5 Jam", callback_data="dur_1.5h")
        ],
        [
            InlineKeyboardButton("⏳ 2 Jam", callback_data="dur_2h"),
            InlineKeyboardButton("⌨️ Input Manual", callback_data="dur_manual")
        ]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    duration_info = (
        f"⏰ Waktu Mulai: **{start_dt.strftime('%H:%M WIB (%Y-%m-%d)')}**\n\n"
        f"⏳ Berapa durasi aktivitas ini?\n"
        f"Pilih salah satu tombol interaktif di bawah atau klik 'Input Manual':"
    )
    await query.edit_message_text(duration_info, reply_markup=reply_markup, parse_mode="Markdown")
    return DURATION

async def plan_start_time(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Parses and stores manual text start time, then presents duration options."""
    raw_input = update.message.text.strip().lower()
    local_tz = get_tz()
    now_local = datetime.now(local_tz)
    
    start_dt = None
    
    try:
        if raw_input == "now":
            start_dt = now_local
        elif raw_input.startswith("in ") and raw_input.endswith("m"):
            mins = int(raw_input.split(" ")[1][:-1])
            start_dt = now_local + timedelta(minutes=mins)
        elif ":" in raw_input:
            time_parts = raw_input.split(":")
            hour = int(time_parts[0])
            minute = int(time_parts[1])
            start_dt = now_local.replace(hour=hour, minute=minute, second=0, microsecond=0)
            if start_dt < now_local:
                start_dt += timedelta(days=1)
        else:
            raise ValueError
    except Exception:
        await update.message.reply_text(
            "⚠️ Format tidak valid. Ketik `now`, `in 15m`, atau jam 24h seperti `18:30`:"
        )
        return START_TIME

    context.user_data["plan_start_dt"] = start_dt
    
    keyboard = [
        [
            InlineKeyboardButton("⏳ 30 Menit", callback_data="dur_30m"),
            InlineKeyboardButton("⏳ 45 Menit", callback_data="dur_45m")
        ],
        [
            InlineKeyboardButton("⏳ 1 Jam", callback_data="dur_1h"),
            InlineKeyboardButton("⏳ 1.5 Jam", callback_data="dur_1.5h")
        ],
        [
            InlineKeyboardButton("⏳ 2 Jam", callback_data="dur_2h"),
            InlineKeyboardButton("⌨️ Input Manual", callback_data="dur_manual")
        ]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    duration_info = (
        f"⏰ Waktu Mulai: **{start_dt.strftime('%H:%M WIB (%Y-%m-%d)')}**\n\n"
        f"⏳ Berapa durasi aktivitas ini?\n"
        f"Pilih salah satu tombol interaktif di bawah atau klik 'Input Manual':"
    )
    await update.message.reply_text(duration_info, reply_markup=reply_markup, parse_mode="Markdown")
    return DURATION

async def plan_duration_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Processes duration buttons, logging to spreadsheet and ending conversation."""
    query = update.callback_query
    await query.answer()
    
    selection = query.data
    
    if selection == "dur_manual":
        await query.edit_message_text(
            text=(
                "⏳ **Input Durasi Manual**\n\n"
                "Silakan ketik durasi aktivitas (misalnya: `45m`, `1.5h`, atau `2`):"
            ),
            parse_mode="Markdown"
        )
        return DURATION
        
    duration_hours = 0.0
    duration_delta = None
    
    if selection == "dur_30m":
        duration_hours = 0.5
        duration_delta = timedelta(minutes=30)
    elif selection == "dur_45m":
        duration_hours = 0.75
        duration_delta = timedelta(minutes=45)
    elif selection == "dur_1h":
        duration_hours = 1.0
        duration_delta = timedelta(hours=1)
    elif selection == "dur_1.5h":
        duration_hours = 1.5
        duration_delta = timedelta(hours=1.5)
    elif selection == "dur_2h":
        duration_hours = 2.0
        duration_delta = timedelta(hours=2)

    category = context.user_data["plan_category"]
    topic = context.user_data["plan_topic"]
    start_dt = context.user_data["plan_start_dt"]
    end_dt = start_dt + duration_delta
    
    date_str = start_dt.strftime("%Y-%m-%d")
    start_str = start_dt.strftime("%H:%M")
    end_str = end_dt.strftime("%H:%M")
    
    await query.edit_message_text(text="⏳ Menyimpan rencana ke Google Sheets...")
    
    success = await spreadsheet_utils.log_activity(
        date_str=date_str,
        category=category,
        topic=topic,
        start_time=start_str,
        end_time=end_str,
        status="Pending",
        duration=round(duration_hours, 2)
    )
    
    if not success:
        await query.edit_message_text("❌ Database Sync Failed. Plan was not logged. Try `/plan` again.")
        return ConversationHandler.END

    chat_id = update.effective_chat.id
    
    lead_time = timedelta(minutes=10)
    pre_alert_dt = start_dt - lead_time
    local_tz = get_tz()
    now_local = datetime.now(local_tz)
    
    if pre_alert_dt > now_local:
        context.job_queue.run_once(
            pre_activity_reminder,
            when=pre_alert_dt,
            chat_id=chat_id,
            name=f"pre_{category}_{topic}",
            data={"category": category, "topic": topic, "start_time": start_str}
        )
        logger.info(f"Scheduled pre-activity reminder for {topic} at {pre_alert_dt}")

    if category == "Relaxing":
        context.job_queue.run_once(
            relaxing_active_warning,
            when=start_dt,
            chat_id=chat_id,
            name=f"relax_warn_{topic}",
            data={"topic": topic}
        )
        logger.info(f"Scheduled relaxing active warning at {start_dt}")

    context.job_queue.run_once(
        post_activity_checkin,
        when=end_dt,
        chat_id=chat_id,
        name=f"post_{category}_{topic}",
        data={"category": category, "topic": topic}
    )
    logger.info(f"Scheduled post-activity checkin for {topic} at {end_dt}")

    summary = (
        f"✅ **Rencana aktivitas berhasil disimpan!**\n\n"
        f"📁 Kategori: **{category}**\n"
        f"📝 Topik: **{topic}**\n"
        f"📅 Tanggal: **{date_str}**\n"
        f"⏰ Waktu: **{start_str} - {end_str} WIB** ({round(duration_hours, 2)} jam)\n\n"
        f"🔔 Pengingat telah dijadwalkan secara otomatis."
    )
    keyboard = [[InlineKeyboardButton("🏠 Back to Start", callback_data="back_to_menu")]]
    reply_markup = InlineKeyboardMarkup(keyboard)
    await query.edit_message_text(summary, reply_markup=reply_markup, parse_mode="Markdown")
    return ConversationHandler.END

async def plan_duration(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Parses manual text duration, logs to spreadsheet, schedules notifications, and finishes."""
    raw_input = update.message.text.strip().lower()
    duration_hours = 0.0
    duration_delta = None
    
    try:
        if raw_input.endswith("m"):
            mins = float(raw_input[:-1])
            duration_hours = mins / 60.0
            duration_delta = timedelta(minutes=mins)
        elif raw_input.endswith("h"):
            hours = float(raw_input[:-1])
            duration_hours = hours
            duration_delta = timedelta(hours=hours)
        else:
            hours = float(raw_input)
            duration_hours = hours
            duration_delta = timedelta(hours=hours)
            
        if duration_hours <= 0:
            raise ValueError
    except ValueError:
        await update.message.reply_text("⚠️ Durasi tidak valid. Masukkan angka positif seperti `45m`, `1.5h`, atau `2`:")
        return DURATION

    category = context.user_data["plan_category"]
    topic = context.user_data["plan_topic"]
    start_dt = context.user_data["plan_start_dt"]
    end_dt = start_dt + duration_delta
    
    date_str = start_dt.strftime("%Y-%m-%d")
    start_str = start_dt.strftime("%H:%M")
    end_str = end_dt.strftime("%H:%M")
    
    await update.message.reply_text("⏳ Menyimpan rencana ke Google Sheets...")
    success = await spreadsheet_utils.log_activity(
        date_str=date_str,
        category=category,
        topic=topic,
        start_time=start_str,
        end_time=end_str,
        status="Pending",
        duration=round(duration_hours, 2)
    )
    
    if not success:
        await update.message.reply_text("❌ Database Sync Failed. Plan was not logged. Try `/plan` again.")
        return ConversationHandler.END

    chat_id = update.effective_chat.id
    
    lead_time = timedelta(minutes=10)
    pre_alert_dt = start_dt - lead_time
    local_tz = get_tz()
    now_local = datetime.now(local_tz)
    
    if pre_alert_dt > now_local:
        context.job_queue.run_once(
            pre_activity_reminder,
            when=pre_alert_dt,
            chat_id=chat_id,
            name=f"pre_{category}_{topic}",
            data={"category": category, "topic": topic, "start_time": start_str}
        )
        logger.info(f"Scheduled pre-activity reminder for {topic} at {pre_alert_dt}")

    if category == "Relaxing":
        context.job_queue.run_once(
            relaxing_active_warning,
            when=start_dt,
            chat_id=chat_id,
            name=f"relax_warn_{topic}",
            data={"topic": topic}
        )
        logger.info(f"Scheduled relaxing active warning at {start_dt}")

    context.job_queue.run_once(
        post_activity_checkin,
        when=end_dt,
        chat_id=chat_id,
        name=f"post_{category}_{topic}",
        data={"category": category, "topic": topic}
    )
    logger.info(f"Scheduled post-activity checkin for {topic} at {end_dt}")

    summary = (
        f"✅ **Rencana aktivitas berhasil disimpan!**\n\n"
        f"📁 Kategori: **{category}**\n"
        f"📝 Topik: **{topic}**\n"
        f"📅 Tanggal: **{date_str}**\n"
        f"⏰ Waktu: **{start_str} - {end_str} WIB** ({round(duration_hours, 2)} jam)\n\n"
        f"🔔 Pengingat telah dijadwalkan secara otomatis."
    )
    keyboard = [[InlineKeyboardButton("🏠 Back to Start", callback_data="back_to_menu")]]
    reply_markup = InlineKeyboardMarkup(keyboard)
    await update.message.reply_text(summary, reply_markup=reply_markup, parse_mode="Markdown")
    return ConversationHandler.END

async def plan_cancel(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Cancels the conversation flow."""
    await update.message.reply_text("❌ Planning cancelled.")
    return ConversationHandler.END

# --- Job Callbacks ---

async def pre_activity_reminder(context: ContextTypes.DEFAULT_TYPE):
    """Sends a warm-up reminder 10 minutes before the activity starts."""
    job = context.job
    data = job.data
    text = (
        f"🔔 **Anti-Gagal-Fokus Warm-up Alert**\n\n"
        f"Your planned block **{data['category']}** is starting in **10 minutes**!\n"
        f"📝 Topic: *{data['topic']}*\n"
        f"⏰ Start Time: *{data['start_time']} WIB*\n\n"
        f"Clear your desk, disable distraction tabs, and prepare your mindset."
    )
    await context.bot.send_message(chat_id=job.chat_id, text=text, parse_mode="Markdown")

async def relaxing_active_warning(context: ContextTypes.DEFAULT_TYPE):
    """Sends a protective alert when a relaxing/healing period starts to avoid isolated urges."""
    job = context.job
    text = (
        f"⚠️ **Anti-Gagal-Fokus Alert: Relaxing Block Started**\n\n"
        f"You are starting a Relaxing session: *{job.data['topic']}*.\n\n"
        f"🔴 **Important Rules for Isolated Hours:**\n"
        f"1. **Keep the environment open:** Work in an open room or keep the door wide open.\n"
        f"2. **Maintain high awareness:** If you experience any loss of focus, drop and do **5 push-ups** immediately!\n"
        f"3. **Trigger Protection:** If urges persist, trigger `/sos` instantly."
    )
    await context.bot.send_message(chat_id=job.chat_id, text=text, parse_mode="Markdown")

async def post_activity_checkin(context: ContextTypes.DEFAULT_TYPE):
    """Asks the user if the activity was completed once it ends."""
    job = context.job
    data = job.data
    category = data["category"]
    topic = data["topic"]
    
    keyboard = [
        [
            InlineKeyboardButton("✅ Yes", callback_data=f"act_yes|{category}|{topic}"),
            InlineKeyboardButton("❌ No", callback_data=f"act_no|{category}|{topic}")
        ]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    text = (
        f"🏁 **Activity Duration Ended!**\n\n"
        f"Did you successfully complete this session?\n"
        f"📁 Category: **{category}**\n"
        f"📝 Topic: **{topic}**"
    )
    await context.bot.send_message(chat_id=job.chat_id, text=text, reply_markup=reply_markup, parse_mode="Markdown")

# --- Check-in Callback Query Handlers ---

async def activity_completion_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Processes study completion click, updating spreadsheet and message."""
    query = update.callback_query
    await query.answer()
    
    # Callback format: act_yes|Category|Topic or act_no|Category|Topic
    parts = query.data.split("|")
    action = parts[0]
    category = parts[1]
    topic = parts[2]
    
    status = "Completed" if action == "act_yes" else "Missed"
    
    await query.edit_message_text(text=f"⏳ Logging completion status: **{status}** to Google Sheets...")
    
    success = await spreadsheet_utils.update_activity_status(category, topic, status)
    
    if success:
        if status == "Completed":
            response_text = (
                f"✅ **Session Completed!**\n\n"
                f"📁 Category: **{category}**\n"
                f"📝 Topic: **{topic}**\n"
                f"🎉 Great job! The entry has been archived in Google Sheets."
            )
        else:
            response_text = (
                f"❌ **Session Missed**\n\n"
                f"📁 Category: **{category}**\n"
                f"📝 Topic: **{topic}**\n"
                f"⚠️ Entry logged as 'Missed'. Focus on physical grounding! Drop and do **5 push-ups** right now to reset."
            )
    else:
        response_text = "⚠️ Status update completed, but could not locate matching Pending record in Google Sheets."
        
    keyboard = [[InlineKeyboardButton("🏠 Back to Start", callback_data="back_to_menu")]]
    reply_markup = InlineKeyboardMarkup(keyboard)
    await query.edit_message_text(text=response_text, reply_markup=reply_markup, parse_mode="Markdown")

# --- /habit_check Flow ---

@authorized_only
async def habit_check_start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Presents the first wellness habit question: 90/20 Break rule."""
    keyboard = [
        [
            InlineKeyboardButton("✅ Yes", callback_data="hab_break|Yes"),
            InlineKeyboardButton("❌ No", callback_data="hab_break|No")
        ]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)
    text = "🧠 **Wellness Habit Check (1/2)**\n\nDid you follow the **90/20 break rule** today?"
    if update.callback_query:
        query = update.callback_query
        await query.answer()
        await query.edit_message_text(text, reply_markup=reply_markup, parse_mode="Markdown")
    else:
        await update.message.reply_text(text, reply_markup=reply_markup, parse_mode="Markdown")

async def habit_break_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Logs 90/20 Break response and displays second question: Location Safety."""
    query = update.callback_query
    await query.answer()
    
    value = query.data.split("|")[1]
    
    # Get local date
    local_tz = get_tz()
    today_str = datetime.now(local_tz).strftime("%Y-%m-%d")
    
    await spreadsheet_utils.log_habit_and_sleep(today_str, "90/20 Break", value)
    
    keyboard = [
        [
            InlineKeyboardButton("✅ Yes", callback_data="hab_loc|Yes"),
            InlineKeyboardButton("❌ No", callback_data="hab_loc|No")
        ]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)
    await query.edit_message_text(
        text=f"🧠 **Wellness Habit Check (2/2)**\n\nWas your learning location **safe and free from distractions**?",
        reply_markup=reply_markup,
        parse_mode="Markdown"
    )

async def habit_loc_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Logs Location Safety and wraps up wellness check."""
    query = update.callback_query
    await query.answer()
    
    value = query.data.split("|")[1]
    local_tz = get_tz()
    today_str = datetime.now(local_tz).strftime("%Y-%m-%d")
    
    await spreadsheet_utils.log_habit_and_sleep(today_str, "Location Safe", value)
    
    keyboard = [[InlineKeyboardButton("🏠 Back to Start", callback_data="back_to_menu")]]
    reply_markup = InlineKeyboardMarkup(keyboard)
    await query.edit_message_text(
        text="✨ **Habits Logged Successfully!**\n\nBoth 90/20 Breaks and Workspace Safety have been saved. Maintain discipline!",
        reply_markup=reply_markup
    )

# --- Sleep & Wake Scheduler & Callbacks ---

async def sleep_preparation_alert(context: ContextTypes.DEFAULT_TYPE):
    """Scheduled task at 21:45 WIB daily to remind user of sleep goal."""
    keyboard = [
        [InlineKeyboardButton("🛌 Going to sleep now", callback_data="sleep_btn|Yes")],
        [InlineKeyboardButton("⚠️ I am staying up late", callback_data="sleep_btn|No")]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)
    text = (
        "🌙 **Daily Sleep Wind-Down Alert**\n\n"
        "It is now **21:45 WIB**. Your target bedtime is **22:00 WIB**.\n"
        "Please close your books, turn off screens, and wind down.\n\n"
        "Are you going to bed at 22:00?"
    )
    await context.bot.send_message(chat_id=context.job.chat_id, text=text, reply_markup=reply_markup)

async def sleep_btn_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Logs sleep target adherence in Google Sheets."""
    query = update.callback_query
    await query.answer()
    
    value = query.data.split("|")[1]
    local_tz = get_tz()
    today_str = datetime.now(local_tz).strftime("%Y-%m-%d")
    
    await spreadsheet_utils.log_habit_and_sleep(today_str, "Sleep 10PM", value)
    
    if value == "Yes":
        response = "🌙 **Sleep Adherence Logged!**\nGood night! Sleep well, prepare to wake up strong at 05:00 AM."
    else:
        response = "⚠️ **Late Night Warning!**\nLate sleep logged. Keep it to a minimum; try to rest as soon as possible."
        
    keyboard = [[InlineKeyboardButton("🏠 Back to Start", callback_data="back_to_menu")]]
    reply_markup = InlineKeyboardMarkup(keyboard)
    await query.edit_message_text(text=response, reply_markup=reply_markup, parse_mode="Markdown")

async def morning_wake_check(context: ContextTypes.DEFAULT_TYPE):
    """Scheduled task at 05:15 WIB daily to log wake adherence."""
    keyboard = [
        [InlineKeyboardButton("☀️ Yes, woke up at 05:00", callback_data="wake_btn|Yes")],
        [InlineKeyboardButton("❌ No, slept in", callback_data="wake_btn|No")]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)
    text = (
        "☀️ **Morning Wake-Up Tracker**\n\n"
        "It is **05:15 WIB**. Did you successfully wake up at **05:00 AM** today?"
    )
    await context.bot.send_message(chat_id=context.job.chat_id, text=text, reply_markup=reply_markup)

async def wake_btn_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Logs wake adherence in Google Sheets."""
    query = update.callback_query
    await query.answer()
    
    value = query.data.split("|")[1]
    local_tz = get_tz()
    today_str = datetime.now(local_tz).strftime("%Y-%m-%d")
    
    await spreadsheet_utils.log_habit_and_sleep(today_str, "Wake Up 5AM", value)
    
    if value == "Yes":
        response = "☀️ **Wake-Up Adherence Logged!**\nExcellent job starting your day at 5:00 AM. Maintain high focus today."
    else:
        response = "⚠️ **Sleep-in Logged.**\nRemember, consistency in waking up is the foundation of self-control. Drop and do **5 push-ups** now to shake off the morning sluggishness!"
        
    keyboard = [[InlineKeyboardButton("🏠 Back to Start", callback_data="back_to_menu")]]
    reply_markup = InlineKeyboardMarkup(keyboard)
    await query.edit_message_text(text=response, reply_markup=reply_markup, parse_mode="Markdown")

# --- /sos Command Flow (Emergency Interrupter) ---

@authorized_only
async def sos_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Trigger of the emergency anti-gagal-fokus interrupter."""
    keyboard = [
        [InlineKeyboardButton("💪 I have done 5 push-ups!", callback_data="sos_pushups")]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    sos_text = (
        "🚨 **ANTI-GAGAL-FOKUS ALERT: EMERGENCY INTERRUPT TRIGGERED** 🚨\n\n"
        "We need to break the cycle of distraction or procrastination immediately!\n\n"
        "Physical Grounding Protocol:\n"
        "👉 **DROP AND DO 5 PUSH-UPS RIGHT NOW!**\n\n"
        "Force the blood back to your muscles, break the cognitive loop, and change your physical posture. "
        "Click the button below once you have completed all 5 repetitions."
    )
    if update.callback_query:
        query = update.callback_query
        await query.answer()
        await query.edit_message_text(sos_text, reply_markup=reply_markup)
    else:
        await update.message.reply_text(sos_text, reply_markup=reply_markup)

async def sos_pushups_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Proceeds to breathing after somatic verification."""
    query = update.callback_query
    await query.answer()
    
    keyboard = [
        [InlineKeyboardButton("🧘 I have taken 3 deep breaths!", callback_data="sos_breathing")]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    breathing_text = (
        "💪 **Physical grounding completed!** Excellent work taking action.\n\n"
        "Now let's ground your nervous system:\n"
        "1. Close your eyes.\n"
        "2. Inhale deeply through your nose for **4 seconds**...\n"
        "3. Hold your breath for **4 seconds**...\n"
        "4. Exhale slowly through your mouth for **6 seconds**...\n\n"
        "Repeat this pattern **3 times**, then click the button below."
    )
    await query.edit_message_text(text=breathing_text, reply_markup=reply_markup)

async def sos_breathing_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Presents active redirection choices to channel energy positively."""
    query = update.callback_query
    await query.answer()
    
    keyboard = [
        [InlineKeyboardButton("💻 Code for 15m", callback_data="sos_redirect|Coding")],
        [InlineKeyboardButton("📚 Read 10 pages", callback_data="sos_redirect|Reading")],
        [InlineKeyboardButton("🏛️ Daily Duty/Worship", callback_data="sos_redirect|Worship")],
        [InlineKeyboardButton("❌ Dismiss Protection", callback_data="sos_redirect|Dismiss")]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    redirect_text = (
        "🧘 **Mental grounding completed. Loop broken.**\n\n"
        "Your focus is now reset. What **constructive, open-space activity** will you immediately redirect your energy toward?"
    )
    await query.edit_message_text(text=redirect_text, reply_markup=reply_markup)

async def sos_redirect_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Processes redirection and finalizes the SOS flow."""
    query = update.callback_query
    await query.answer()
    
    selection = query.data.split("|")[1]
    
    if selection == "Dismiss":
        final_text = "✨ **Protection dismissed.** Stay vigilant and always work in an open environment."
    else:
        final_text = (
            f"🚀 **Action Selected: {selection}!**\n\n"
            f"Excellent choice. Start immediately and do not open any browser tabs that are unrelated to this task. "
            f"You are in full control."
        )
        
    keyboard = [[InlineKeyboardButton("🏠 Back to Start", callback_data="back_to_menu")]]
    reply_markup = InlineKeyboardMarkup(keyboard)
    await query.edit_message_text(text=final_text, reply_markup=reply_markup)

async def menu_button_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Router for main menu buttons."""
    query = update.callback_query
    await query.answer()
    
    action = query.data
    
    if action == "menu_habit":
        await habit_check_start(update, context)
    elif action == "menu_sos":
        await sos_command(update, context)
    elif action == "menu_help":
        help_text = (
            "💡 **How to Use the Daily Activity Tracker Bot:**\n\n"
            "1️⃣ **Planning an Activity (`/plan`):**\n"
            "   - Select a category (Coding, Reading, Relaxing, or Obligations).\n"
            "   - Type in the topic description.\n"
            "   - Type the start time. Supports `14:30`, `in 10m` (minutes), or `now`.\n"
            "   - Type the duration. Supports `45m` (minutes) or `1.5h` / `2` (hours).\n"
            "   - **Pre-Activity Alert:** Triggers 10 minutes prior to warm up.\n"
            "   - **Post-Activity Check-In:** Prompts you at the end to check if you completed the task.\n\n"
            "2️⃣ **Daily Habits Check (`/habit_check`):**\n"
            "   - Log 90/20 breaks and learning environment safety.\n\n"
            "3️⃣ **Emergency Interrupter (`/sos`):**\n"
            "   - Use this command if you are experiencing focus lapses or negative urges during relaxing periods.\n"
            "   - Demands 5 push-ups and breathing exercises to break loops.\n\n"
            "4️⃣ **Automatic Reminders:**\n"
            "   - **21:45 WIB:** Sleep preparation alert.\n"
            "   - **05:15 WIB:** Morning wake-up check."
        )
        keyboard = [[InlineKeyboardButton("🔙 Back to Menu", callback_data="back_to_menu")]]
        reply_markup = InlineKeyboardMarkup(keyboard)
        await query.edit_message_text(help_text, reply_markup=reply_markup, parse_mode="Markdown")
    elif action == "back_to_menu":
        welcome_text = (
            "📊 **Daily Activity Tracker Bot**\n\n"
            "Welcome! This bot helps you log your study plans and track your habits in real-time.\n\n"
            "🎯 **Target Routine Goals:**\n"
            "• Sleep: **22:00 WIB**\n"
            "• Wake Up: **05:00 WIB**\n\n"
            "🎛️ **Quick Actions Control Panel:**\n"
            "Select a button below to quickly run any action:"
        )
        keyboard = [
            [
                InlineKeyboardButton("📅 Plan Activity", callback_data="menu_plan"),
                InlineKeyboardButton("🧠 Habit Check", callback_data="menu_habit")
            ],
            [
                InlineKeyboardButton("🚨 Trigger SOS", callback_data="menu_sos"),
                InlineKeyboardButton("💡 Get Help", callback_data="menu_help")
            ]
        ]
        reply_markup = InlineKeyboardMarkup(keyboard)
        await query.edit_message_text(welcome_text, reply_markup=reply_markup, parse_mode="Markdown")
