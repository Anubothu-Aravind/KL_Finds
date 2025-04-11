import telebot
from supabase import create_client
import re
import uuid
import pandas as pd
import io
import os
import logging

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Bot configuration from environment variables or fallback to hardcoded values
BOT_TOKEN = os.environ.get("BOT_TOKEN", "7514287995:AAHRO3a3FjI-6Tt6OQL1NlNh_1UkKAmzlOY")
SUPABASE_URL = os.environ.get("SUPABASE_URL", "https://dwkmgssfaggkfkqannxv.supabase.co")
SUPABASE_KEY = os.environ.get("SUPABASE_KEY", "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJpc3MiOiJzdXBhYmFzZSIsInJlZiI6ImR3a21nc3NmYWdna2ZrcWFubnh2Iiwicm9sZSI6ImFub24iLCJpYXQiOjE3NDM0MzQ2MDMsImV4cCI6MjA1OTAxMDYwM30.6I1QXPuGhLhaI6yjVxnZG2ypyBto0hOyy8pI7aZUTsw")

bot = telebot.TeleBot(BOT_TOKEN)
supabase = create_client(SUPABASE_URL, SUPABASE_KEY)

user_data = {}
admin_credentials = {"username": "1", "password": "1"}
admin_logged_in = {}

def check_and_create_tables():
    try:
        supabase.table("users").select("id").limit(1).execute()
        print("✅ Users table check passed.")
    except:
        print("❌ Users table check failed.")
    try:
        supabase.table("faculty").select("id").limit(1).execute()
        print("✅ Faculty table check passed.")
    except:
        print("❌ Faculty table check failed.")
    try:
        supabase.table("contributions").select("id").limit(1).execute()
        print("✅ Contributions table check passed.")
    except:
        print("❌ Contributions table check failed.")

def is_user_registered(telegram_id):
    res = supabase.table("users").select("*").eq("telegram_id", str(telegram_id)).execute()
    return len(res.data) > 0

def register_user(telegram_id):
    try:
        res = supabase.table("users").insert({
            "telegram_id": str(telegram_id),
            "email": f"{telegram_id}@klu.in"
        }).execute()
        if res.data:
            print(f"✅ New user {telegram_id} registered.")
            return True
        else:
            print(f"❌ Failed to register user {telegram_id}: No data returned.")
            return False
    except Exception as e:
        print(f"❌ Exception during user registration for {telegram_id}: {e}")
        return False

def parse_cabin_info(cabin_input):
    match = re.match(r"([lrmLRM])(\d{3})", cabin_input.strip())
    if match:
        return match.group(1).upper(), match.group(2)[0], match.group(2)
    return "-", 0, cabin_input

def insert_faculty_data(faculty_name, block, floor, room, cabin, telegram_id):
    emp_id = f"placeholder-{str(uuid.uuid4())[:8]}"
    res = supabase.table("faculty").insert({
        "faculty_name": faculty_name,
        "emp_id": emp_id,
        "block": block,
        "floor": int(floor),
        "room": room,
        "cabin": cabin,
        "added_by": str(telegram_id)
    }).execute()
    fid = res.data[0]['id']
    supabase.table("contributions").insert({"user_id": str(telegram_id), "faculty_id": fid}).execute()
    return fid

@bot.message_handler(commands=['start'])
def start(message):
    telegram_id = message.from_user.id
    if not is_user_registered(telegram_id):
        success = register_user(telegram_id)
        if success:
            bot.send_message(message.chat.id, "👋 Welcome! You've been registered.")
        else:
            bot.send_message(message.chat.id, "⚠️ Registration failed. Try again later.")
    else:
        bot.send_message(message.chat.id, "👋 Welcome back!")
    show_menu(message)

def show_menu(message):
    markup = telebot.types.ReplyKeyboardMarkup(resize_keyboard=True)
    markup.add("1.Contribute", "2.Find", "3.Admin Login")
    bot.send_message(message.chat.id, "Choose an option:", reply_markup=markup)

@bot.message_handler(func=lambda m: m.text == "1.Contribute")
def contribute(message):
    bot.send_message(message.chat.id, f"Your Telegram ID: {message.from_user.id}\nWe are storing your contributions.")
    bot.send_message(message.chat.id, "Enter full faculty name with title (Dr./Mr./Ms./Mrs.): or type 'exit' to cancel")
    bot.register_next_step_handler(message, contrib_name)

def contrib_name(message):
    if message.text.lower() == "exit": return cancel_flow(message)
    user_data[message.chat.id] = {"faculty_name": message.text}
    bot.send_message(message.chat.id, "Enter block name:")
    bot.register_next_step_handler(message, contrib_block)

def contrib_block(message):
    if message.text.lower() == "exit": return cancel_flow(message)
    user_data[message.chat.id]["block"] = message.text
    bot.send_message(message.chat.id, "Enter cabin number (e.g., L404, M201):")
    bot.register_next_step_handler(message, contrib_cabin)

def contrib_cabin(message):
    if message.text.lower() == "exit": return cancel_flow(message)
    data = user_data[message.chat.id]
    block_code, floor, room = parse_cabin_info(message.text)
    insert_faculty_data(data["faculty_name"], data["block"], floor, room, message.text, message.from_user.id)
    bot.send_message(message.chat.id, "✅ Faculty added successfully.", reply_markup=telebot.types.ReplyKeyboardRemove())
    user_data.pop(message.chat.id, None)

def cancel_flow(message):
    bot.send_message(message.chat.id, "❌ Contribution cancelled.", reply_markup=telebot.types.ReplyKeyboardRemove())
    user_data.pop(message.chat.id, None)

@bot.message_handler(func=lambda m: m.text == "2.Find")
def find_faculty(message):
    bot.send_message(message.chat.id, "Enter faculty name to search:")
    bot.register_next_step_handler(message, process_find_faculty)

def process_find_faculty(message):
    term = message.text.strip()
    results = supabase.table("faculty").select("*").ilike("faculty_name", f"%{term}%").execute()
    if not results.data:
        bot.send_message(message.chat.id, "❌ No faculty members found matching your search.")
        return
    reply = "\n".join([f"👤 {f['faculty_name']}\n🏢 Block: {f['block']}\n🏠 Cabin: {f['cabin']}\n" for f in results.data])
    bot.send_message(message.chat.id, reply)

@bot.message_handler(func=lambda m: m.text == "3.Admin Login")
def admin_login(message):
    bot.send_message(message.chat.id, "Enter admin username:")
    bot.register_next_step_handler(message, get_admin_user)

def get_admin_user(message):
    if message.text.strip() == admin_credentials["username"]:
        user_data[message.chat.id] = {"admin_try": True}
        bot.send_message(message.chat.id, "Enter password:")
        bot.register_next_step_handler(message, get_admin_pass)
    else:
        bot.send_message(message.chat.id, "❌ Wrong username.")

def get_admin_pass(message):
    if message.text.strip() == admin_credentials["password"]:
        admin_logged_in[message.chat.id] = True
        markup = telebot.types.ReplyKeyboardMarkup(resize_keyboard=True)
        markup.add("View Faculty List", "Download CSV", "/edit_faculty", "/delete_faculty")
        bot.send_message(message.chat.id, "✅ Admin logged in. Choose an option:", reply_markup=markup)
    else:
        bot.send_message(message.chat.id, "❌ Wrong password.")

@bot.message_handler(func=lambda m: m.text == "View Faculty List")
def admin_view_faculty(message):
    if not admin_logged_in.get(message.chat.id):
        return bot.send_message(message.chat.id, "❌ Admin only.")
    results = supabase.table("faculty").select("*").execute()
    if not results.data:
        return bot.send_message(message.chat.id, "❌ No faculty data available.")
    reply = "📋 Faculty List:\n\n"
    for i, f in enumerate(results.data):
        reply += f"{i+1}. {f['faculty_name']} | Block: {f['block']} | Cabin: {f['cabin']}\n"
    bot.send_message(message.chat.id, reply)

@bot.message_handler(func=lambda m: m.text == "Download CSV")
def admin_download_csv(message):
    if not admin_logged_in.get(message.chat.id):
        return bot.send_message(message.chat.id, "❌ Admin only")
    results = supabase.table("faculty").select("*").execute()
    if not results.data:
        return bot.send_message(message.chat.id, "❌ No data")
    df = pd.DataFrame(results.data)
    output = io.BytesIO()
    df.to_csv(output, index=False)
    output.seek(0)
    bot.send_document(message.chat.id, output, visible_file_name="faculty_data.csv")

@bot.message_handler(commands=['edit_faculty'])
def edit_faculty(message):
    if not admin_logged_in.get(message.chat.id):
        return bot.send_message(message.chat.id, "❌ Admin only.")
    results = supabase.table("faculty").select("*").execute()
    if not results.data:
        return bot.send_message(message.chat.id, "❌ No faculty found.")
    user_data[message.chat.id] = {'edit_list': results.data}
    reply = "Select a faculty to edit by S.No:\n"
    for i, f in enumerate(results.data):
        reply += f"{i+1}. {f['faculty_name']} | Block: {f['block']} | Cabin: {f['cabin']}\n"
    bot.send_message(message.chat.id, reply)
    bot.register_next_step_handler(message, get_faculty_to_edit)

def get_faculty_to_edit(message):
    try:
        index = int(message.text.strip()) - 1
        user_data[message.chat.id]['edit_id'] = user_data[message.chat.id]['edit_list'][index]['id']
        markup = telebot.types.ReplyKeyboardMarkup(resize_keyboard=True)
        markup.add("Edit Name", "Edit Cabin", "Edit Block")
        bot.send_message(message.chat.id, "Choose what to edit:", reply_markup=markup)
        bot.register_next_step_handler(message, edit_field_choice)
    except:
        bot.send_message(message.chat.id, "❌ Invalid selection.")

def edit_field_choice(message):
    choice = message.text.strip().lower()
    if "name" in choice:
        bot.send_message(message.chat.id, "Enter new faculty name:")
        bot.register_next_step_handler(message, lambda m: apply_edit_field(m, 'faculty_name'))
    elif "cabin" in choice:
        bot.send_message(message.chat.id, "Enter new cabin number:")
        bot.register_next_step_handler(message, lambda m: apply_edit_field(m, 'cabin'))
    elif "block" in choice:
        bot.send_message(message.chat.id, "Enter new block name:")
        bot.register_next_step_handler(message, lambda m: apply_edit_field(m, 'block'))
    else:
        bot.send_message(message.chat.id, "❌ Invalid option.")

def apply_edit_field(message, field):
    new_val = message.text.strip()
    fid = user_data[message.chat.id]['edit_id']
    supabase.table("faculty").update({field: new_val}).eq("id", fid).execute()
    bot.send_message(message.chat.id, f"✅ Faculty {field.replace('_', ' ')} updated successfully. Use /edit_faculty, /delete_faculty, /download_excel")

@bot.message_handler(commands=['delete_faculty'])
def delete_faculty(message):
    if not admin_logged_in.get(message.chat.id):
        return bot.send_message(message.chat.id, "❌ Admin only.")
    results = supabase.table("faculty").select("*").execute()
    if not results.data:
        return bot.send_message(message.chat.id, "❌ No faculty to delete.")
    user_data[message.chat.id] = {'delete_list': results.data}
    reply = "🗑️ Faculty List:\n\n"
    for i, f in enumerate(results.data):
        reply += f"{i+1}. {f['faculty_name']} | Block: {f['block']} | Cabin: {f['cabin']}\n"
    bot.send_message(message.chat.id, reply + "\nEnter the S.No of the faculty to delete:")
    bot.register_next_step_handler(message, confirm_delete_index)

def confirm_delete_index(message):
    try:
        index = int(message.text.strip()) - 1
        faculty = user_data[message.chat.id]['delete_list'][index]
        faculty_id = faculty['id']
        supabase.table("contributions").delete().eq("faculty_id", faculty_id).execute()
        supabase.table("faculty").delete().eq("id", faculty_id).execute()
        bot.send_message(message.chat.id, f"🗑️ Faculty '{faculty['faculty_name']}' deleted successfully. Use /edit_faculty, /delete_faculty, /download_excel")
        del user_data[message.chat.id]['delete_list']
    except:
        bot.send_message(message.chat.id, "❌ Invalid input or error deleting.")

def start_bot():
    print("🤖 Bot is now running...")
    check_and_create_tables()
    bot.infinity_polling()

# This allows the script to run standalone
if __name__ == "__main__":
    start_bot()
