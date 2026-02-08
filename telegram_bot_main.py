import os
import logging
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ApplicationBuilder, ContextTypes, CommandHandler, CallbackQueryHandler

# ---------------------------------------------------------
# CONFIGURATION
# ---------------------------------------------------------

TOKEN = os.environ["BOT_TOKEN"]
ROOT_FOLDER = "drive"

logging.basicConfig(
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    level=logging.INFO,
)

# ---------------------------------------------------------
# HELPER FUNCTIONS
# ---------------------------------------------------------

def get_keyboard(current_path: str, root_path: str) -> InlineKeyboardMarkup:
    keyboard = []

    try:
        items = sorted(os.listdir(current_path))
    except FileNotFoundError:
        items = []

    for item in items:
        if item.lower() == "desktop.ini" or item.startswith("."):
            continue

        full_path = os.path.join(current_path, item)
        rel_path = os.path.relpath(full_path, root_path)

        if os.path.isdir(full_path):
            text = f"📂 {item}"
            callback_data = f"d:{rel_path}"
        else:
            text = f"📄 {item}"
            callback_data = f"f:{rel_path}"

        if len(callback_data.encode("utf-8")) > 64:
            continue

        keyboard.append([InlineKeyboardButton(text, callback_data=callback_data)])

    if os.path.abspath(current_path) != os.path.abspath(root_path):
        parent_path = os.path.relpath(os.path.dirname(current_path), root_path)
        callback = "root" if parent_path == "." else f"d:{parent_path}"
        keyboard.append([InlineKeyboardButton("⬅️ Retour / Back", callback_data=callback)])

    return InlineKeyboardMarkup(keyboard)

# ---------------------------------------------------------
# HANDLERS
# ---------------------------------------------------------

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    os.makedirs(ROOT_FOLDER, exist_ok=True)

    keyboard = get_keyboard(ROOT_FOLDER, ROOT_FOLDER)
    await update.message.reply_text("📚 Student Drive:", reply_markup=keyboard)

async def button_click(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()

    data = query.data

    if data == "root":
        keyboard = get_keyboard(ROOT_FOLDER, ROOT_FOLDER)
        await query.edit_message_text(text="📚 Root Directory:", reply_markup=keyboard)
        return

    try:
        type_prefix, rel_path = data.split(":", 1)
        full_path = os.path.join(ROOT_FOLDER, rel_path)
    except ValueError:
        return

    if type_prefix == "d":
        if not os.path.exists(full_path) or not os.path.isdir(full_path):
            await query.edit_message_text("❌ Folder not found.")
            return

        keyboard = get_keyboard(full_path, ROOT_FOLDER)

        if not keyboard.inline_keyboard:
            await query.edit_message_text(
                text=f"📂 {os.path.basename(full_path)} is empty.",
                reply_markup=keyboard,
            )
        else:
            await query.edit_message_text(
                text=f"📂 {os.path.basename(full_path)}",
                reply_markup=keyboard,
            )

    elif type_prefix == "f":
        if not os.path.exists(full_path) or not os.path.isfile(full_path):
            await query.edit_message_text("❌ File not found.")
            return

        await query.message.reply_text(f"⬇️ Sending {os.path.basename(full_path)}.")
        try:
            with open(full_path, "rb") as f:
                await context.bot.send_document(
                    chat_id=query.message.chat_id,
                    document=f,
                    filename=os.path.basename(full_path),
                )
        except Exception as e:
            await query.message.reply_text(f"❌ Error sending file: {e}")

# ---------------------------------------------------------
# MAIN
# ---------------------------------------------------------

if __name__ == "__main__":
    os.makedirs(ROOT_FOLDER, exist_ok=True)

    print("✅ Bot is starting.")

    application = ApplicationBuilder().token(TOKEN).build()
    application.add_handler(CommandHandler("start", start))
    application.add_handler(CallbackQueryHandler(button_click))

    application.run_polling(allowed_updates=Update.ALL_TYPES)