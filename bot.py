import os
import logging
import uuid
import json
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ApplicationBuilder, ContextTypes, CommandHandler, CallbackQueryHandler

# ---------------------------------------------------------
# CONFIGURATION
# ---------------------------------------------------------
TOKEN = os.environ.get('BOT_TOKEN')
ROOT_FOLDER = 'drive'

# 🔐 PUT YOUR TELEGRAM ID HERE (get it using /id)
ADMIN_ID = 6644608765  

USERS_FILE = "users.json"

path_cache = {}

logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)

# ---------------------------------------------------------
# USER STORAGE (PERMANENT)
# ---------------------------------------------------------

def load_users():
    if not os.path.exists(USERS_FILE):
        return set()
    with open(USERS_FILE, "r") as f:
        return set(json.load(f))

def save_users(users):
    with open(USERS_FILE, "w") as f:
        json.dump(list(users), f)

users = load_users()

# ---------------------------------------------------------
# HELPER FUNCTIONS
# ---------------------------------------------------------

def get_short_path(path):
    for key, val in path_cache.items():
        if val == path:
            return key
    short_id = str(uuid.uuid4())[:8]
    path_cache[short_id] = path
    return short_id

def get_keyboard(current_path, root_path):
    keyboard = []
    
    try:
        items = sorted(os.listdir(current_path), key=lambda x: (not os.path.isdir(os.path.join(current_path, x)), x.lower()))
    except FileNotFoundError:
        return None

    for item in items:
        if item.lower() == 'desktop.ini' or item.startswith('.'):
            continue

        full_path = os.path.join(current_path, item)
        rel_path = os.path.relpath(full_path, root_path)
        
        short_id = get_short_path(rel_path)
        
        if os.path.isdir(full_path):
            text = f"📂 {item}"
            callback_data = f"d:{short_id}"
        else:
            size_mb = os.path.getsize(full_path) / (1024 * 1024)
            text = f"📄 {item} ({size_mb:.1f}MB)"
            callback_data = f"f:{short_id}"

        keyboard.append([InlineKeyboardButton(text, callback_data=callback_data)])

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
    user_id = update.message.chat_id

    # Save user permanently
    if user_id not in users:
        users.add(user_id)
        save_users(users)

    if not os.path.exists(ROOT_FOLDER):
        os.makedirs(ROOT_FOLDER)
        await update.message.reply_text(f"Created '{ROOT_FOLDER}' directory. Please add files to it.")
        return

    keyboard = get_keyboard(ROOT_FOLDER, ROOT_FOLDER)
    await update.message.reply_text(
        "📚 **Student Drive**\nSelect a folder or file:",
        reply_markup=keyboard,
        parse_mode="Markdown"
    )

# Get user ID
async def myid(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(f"Your ID: {update.message.chat_id}")

# Broadcast message
async def broadcast(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.message.chat_id != ADMIN_ID:
        await update.message.reply_text("❌ You are not allowed to use this command.")
        return

    message = " ".join(context.args)

    if not message:
        await update.message.reply_text("⚠️ Usage: /broadcast your message")
        return

    success = 0
    failed = 0

    for user in users:
        try:
            await context.bot.send_message(chat_id=user, text=f"📢 {message}")
            success += 1
        except:
            failed += 1

    await update.message.reply_text(f"✅ Sent to {success} users\n❌ Failed: {failed}")

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

        file_size = os.path.getsize(full_path)
        if file_size > 49 * 1024 * 1024:
            await query.answer("File is too large (>50MB).", show_alert=True)
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
    application.add_handler(CommandHandler('id', myid))
    application.add_handler(CommandHandler('broadcast', broadcast))
    application.add_handler(CallbackQueryHandler(button_click))
    
    print("Bot is running...")
    application.run_polling()
