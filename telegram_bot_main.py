import os
import logging
import uuid
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ApplicationBuilder, ContextTypes, CommandHandler, CallbackQueryHandler

# ---------------------------------------------------------
# CONFIGURATION
# ---------------------------------------------------------
# Better practice: Use environment variables (e.g., os.environ.get('BOT_TOKEN'))
TOKEN = os.environ.get('BOT_TOKEN') 
ROOT_FOLDER = 'drive'

# Map long paths to short IDs to bypass Telegram's 64-byte callback limit
path_cache = {}

logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)

# ---------------------------------------------------------
# HELPER FUNCTIONS
# ---------------------------------------------------------

def get_short_path(path):
    """Stores a long path and returns a short ID."""
    for key, val in path_cache.items():
        if val == path:
            return key
    short_id = str(uuid.uuid4())[:8]
    path_cache[short_id] = path
    return short_id

def get_keyboard(current_path, root_path):
    keyboard = []
    
    try:
        # Get list and sort (folders first, then files)
        items = sorted(os.listdir(current_path), key=lambda x: (not os.path.isdir(os.path.join(current_path, x)), x.lower()))
    except FileNotFoundError:
        return None

    for item in items:
        if item.lower() == 'desktop.ini' or item.startswith('.'):
            continue

        full_path = os.path.join(current_path, item)
        rel_path = os.path.relpath(full_path, root_path)
        
        # We use a short ID to keep callback_data under 64 bytes
        short_id = get_short_path(rel_path)
        
        if os.path.isdir(full_path):
            text = f"📂 {item}"
            callback_data = f"d:{short_id}"
        else:
            size_mb = os.path.getsize(full_path) / (1024 * 1024)
            text = f"📄 {item} ({size_mb:.1f}MB)"
            callback_data = f"f:{short_id}"

        keyboard.append([InlineKeyboardButton(text, callback_data=callback_data)])

    # Back Button logic
    if current_path != root_path:
        parent_path = os.path.relpath(os.path.dirname(current_path), root_path)
        if parent_path == ".":
            keyboard.append([InlineKeyboardButton("⬅️ Back to Home", callback_data="root")])
        else:
            short_parent = get_short_path(parent_path)
            keyboard.append([InlineKeyboardButton("⬅️ Back", callback_data=f"d:{short_parent}")])

    return InlineKeyboardMarkup(keyboard)

# ---------------------------------------------------------
# HANDLERS
# ---------------------------------------------------------

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not os.path.exists(ROOT_FOLDER):
        os.makedirs(ROOT_FOLDER)
        await update.message.reply_text(f"Created '{ROOT_FOLDER}' directory. Please add files to it.")
        return

    keyboard = get_keyboard(ROOT_FOLDER, ROOT_FOLDER)
    await update.message.reply_text("📚 **Student Drive**\nSelect a folder or file:", 
                                   reply_markup=keyboard, parse_mode="Markdown")

async def button_click(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    data = query.data

    if data == "root":
        keyboard = get_keyboard(ROOT_FOLDER, ROOT_FOLDER)
        await query.edit_message_text("📚 Root Directory:", reply_markup=keyboard)
        return

    type_prefix, short_id = data.split(':', 1)
    rel_path = path_cache.get(short_id)
    
    if not rel_path:
        await query.answer("Session expired. Please use /start again.", show_alert=True)
        return

    full_path = os.path.join(ROOT_FOLDER, rel_path)

    if type_prefix == 'd':
        if not os.path.exists(full_path):
            await query.answer("Folder not found.", show_alert=True)
            return
            
        keyboard = get_keyboard(full_path, ROOT_FOLDER)
        await query.edit_message_text(text=f"📂 Location: {rel_path}", reply_markup=keyboard)
        await query.answer()

    elif type_prefix == 'f':
        if not os.path.exists(full_path):
            await query.answer("File not found.", show_alert=True)
            return

        # Check file size (Telegram Bot API limit is 50MB for uploading)
        file_size = os.path.getsize(full_path)
        if file_size > 49 * 1024 * 1024:
            await query.answer("File is too large (>50MB). Telegram bots cannot send it.", show_alert=True)
            return

        await query.answer("Sending file...")
        try:
            with open(full_path, 'rb') as file:
                await context.bot.send_document(
                    chat_id=query.message.chat_id,
                    document=file,
                    filename=os.path.basename(full_path),
                    caption=f"✅ {os.path.basename(full_path)}"
                )
        except Exception as e:
            logging.error(f"Error sending file: {e}")
            await query.message.reply_text("❌ Error sending file.")

# ---------------------------------------------------------
# MAIN
# ---------------------------------------------------------

if __name__ == '__main__':
    application = ApplicationBuilder().token(TOKEN).build()
    application.add_handler(CommandHandler('start', start))
    application.add_handler(CallbackQueryHandler(button_click))
    
    print("Bot is running...")
    application.run_polling()
