import os
import logging
import datetime
import pytz
from dotenv import load_dotenv
from telegram.ext import (
    ApplicationBuilder,
    CommandHandler,
    CallbackQueryHandler,
    MessageHandler,
    filters,
    ConversationHandler,
)
import spreadsheet_utils
from bot_handlers import (
    start_command,
    help_command,
    plan_start,
    plan_category_callback,
    plan_topic,
    plan_start_time,
    plan_duration,
    plan_cancel,
    activity_completion_callback,
    habit_check_start,
    habit_break_callback,
    habit_loc_callback,
    sleep_preparation_alert,
    sleep_btn_callback,
    morning_wake_check,
    wake_btn_callback,
    sos_command,
    sos_pushups_callback,
    sos_breathing_callback,
    sos_redirect_callback,
    CATEGORY,
    TOPIC,
    START_TIME,
    DURATION,
)

# Configure elegant console logging
logging.basicConfig(
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    level=logging.INFO
)
logger = logging.getLogger("DailyActivityBot.Main")

load_dotenv()

async def post_init(application) -> None:
    """
    Runs asynchronous initialization operations, such as setting up 
    the Google Sheets connection and registering background cron tasks.
    """
    logger.info("Initializing spreadsheet worksheets and headers...")
    try:
        await spreadsheet_utils.init_spreadsheet()
    except Exception as e:
        logger.error(f"Spreadsheet initialization failed: {e}")
        # We don't crash, but log a severe warning
    
    # Retrieve scheduler configurations
    chat_id_env = os.getenv("TELEGRAM_CHAT_ID")
    tz_str = os.getenv("TIMEZONE", "Asia/Jakarta")
    local_tz = pytz.timezone(tz_str)
    
    if not chat_id_env:
        logger.warning("TELEGRAM_CHAT_ID is not set in .env. Daily sleep/wake schedulers cannot be registered.")
        return
        
    try:
        chat_id = int(chat_id_env)
    except ValueError:
        logger.error("TELEGRAM_CHAT_ID must be a valid integer.")
        return

    # 1. Register Daily Bedtime Preparation Alert at 21:45 WIB
    sleep_time = datetime.time(hour=21, minute=45, second=0, tzinfo=local_tz)
    application.job_queue.run_daily(
        sleep_preparation_alert,
        time=sleep_time,
        chat_id=chat_id,
        name="daily_sleep_alert"
    )
    logger.info(f"Registered daily sleep preparation reminder at 21:45 {tz_str}.")

    # 2. Register Daily Morning Wake-up Check at 05:15 WIB
    wake_time = datetime.time(hour=5, minute=15, second=0, tzinfo=local_tz)
    application.job_queue.run_daily(
        morning_wake_check,
        time=wake_time,
        chat_id=chat_id,
        name="daily_wake_check"
    )
    logger.info(f"Registered daily morning wake-up check at 05:15 {tz_str}.")


def main() -> None:
    """Entry point of the application."""
    token = os.getenv("TELEGRAM_BOT_TOKEN")
    if not token:
        logger.critical("TELEGRAM_BOT_TOKEN is not configured in .env. Exiting.")
        return

    # Build the Application and link post_init hook
    application = (
        ApplicationBuilder()
        .token(token)
        .post_init(post_init)
        .build()
    )

    # 1. Define Conversation Handler for `/plan`
    plan_conv_handler = ConversationHandler(
        entry_points=[CommandHandler("plan", plan_start)],
        states={
            CATEGORY: [CallbackQueryHandler(plan_category_callback, pattern="^cat_")],
            TOPIC: [MessageHandler(filters.TEXT & ~filters.COMMAND, plan_topic)],
            START_TIME: [MessageHandler(filters.TEXT & ~filters.COMMAND, plan_start_time)],
            DURATION: [MessageHandler(filters.TEXT & ~filters.COMMAND, plan_duration)],
        },
        fallbacks=[CommandHandler("cancel", plan_cancel)],
        per_message=False,
    )
    application.add_handler(plan_conv_handler)

    # 2. Add Commands
    application.add_handler(CommandHandler("start", start_command))
    application.add_handler(CommandHandler("help", help_command))
    application.add_handler(CommandHandler("habit_check", habit_check_start))
    application.add_handler(CommandHandler("sos", sos_command))

    # 3. Add Callback Query Handlers
    application.add_handler(CallbackQueryHandler(activity_completion_callback, pattern="^act_"))
    application.add_handler(CallbackQueryHandler(habit_break_callback, pattern="^hab_break"))
    application.add_handler(CallbackQueryHandler(habit_loc_callback, pattern="^hab_loc"))
    application.add_handler(CallbackQueryHandler(sleep_btn_callback, pattern="^sleep_btn"))
    application.add_handler(CallbackQueryHandler(wake_btn_callback, pattern="^wake_btn"))
    application.add_handler(CallbackQueryHandler(sos_pushups_callback, pattern="^sos_pushups$"))
    application.add_handler(CallbackQueryHandler(sos_breathing_callback, pattern="^sos_breathing$"))
    application.add_handler(CallbackQueryHandler(sos_redirect_callback, pattern="^sos_redirect"))

    # Start the bot polling execution loop
    logger.info("Daily Activity Tracker Bot is starting up. Polling Telegram servers...")
    application.run_polling()


if __name__ == "__main__":
    main()
