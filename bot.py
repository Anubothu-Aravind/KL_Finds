import telebot
from supabase import create_client
import re
import uuid
import pandas as pd
import io
from dotenv import load_dotenv
import os
import logging

load_dotenv()
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

BOT_TOKEN = os.environ.get("BOT_TOKEN")
SUPABASE_URL = os.environ.get("SUPABASE_URL", "https://dwkmgssfaggkfkqannxv.supabase.co")
SUPABASE_KEY = os.environ.get("SUPABASE_KEY", "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJpc3MiOiJzdXBhYmFzZSIsInJlZiI6ImR3a21nc3NmYWdna2ZrcWFubnh2Iiwicm9sZSI6ImFub24iLCJpYXQiOjE3NDM0MzQ2MDMsImV4cCI6MjA1OTAxMDYwM30.6I1QXPuGhLhaI6yjVxnZG2ypyBto0hOyy8pI7aZUTsw")

bot = telebot.TeleBot(BOT_TOKEN)
supabase = create_client(SUPABASE_URL, SUPABASE_KEY)

user_data = {}
admin_credentials = {"username": "Admin@2022", "password": "ADJ@123"}
admin_logged_in = {}

def check_and_create_tables():
    """Checks for the existence of necessary Supabase tables."""
    try:
        supabase.table("users").select("id").limit(1).execute()
        print("✅ Users table check passed.")
    except:
        print("❌ Users table check failed. Ensure 'users' table exists.")
    try:
        supabase.table("faculty").select("id").limit(1).execute()
        print("✅ Faculty table check passed.")
    except:
        print("❌ Faculty table check failed. Ensure 'faculty' table exists.")
    try:
        supabase.table("contributions").select("id").limit(1).execute()
        print("✅ Contributions table check passed.")
    except:
        print("❌ Contributions table check failed. Ensure 'contributions' table exists.")

def is_user_registered(telegram_id):
    """Checks if a user is registered in the database."""
    res = supabase.table("users").select("*").eq("telegram_id", str(telegram_id)).execute()
    return len(res.data) > 0

def register_user(telegram_id):
    """Registers a new user in the database."""
    try:
        res = supabase.table("users").insert({
            "telegram_id": str(telegram_id),
            "email": f"{telegram_id}@klu.in"
        }).execute()
        return bool(res.data)
    except Exception as e:
        print(f"❌ Registration error: {e}")
        return False

def parse_cabin_info(cabin_input):
    """Parses cabin input to extract block, floor, and room information."""
    match = re.match(r"([lrmLRM])(\d{3})", cabin_input.strip())
    if match:
        return match.group(1).upper(), match.group(2)[0], match.group(2)
    return "-", 0, cabin_input

def insert_faculty_data(faculty_name, block, floor, room, cabin, telegram_id):
    """Inserts new faculty data into the database."""
    emp_id = f"placeholder-{str(uuid.uuid4())[:8]}" # Placeholder for emp_id
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
    """Handles the /start command, registers the user if necessary, and shows the main menu."""
    telegram_id = message.from_user.id
    if not is_user_registered(telegram_id):
        if register_user(telegram_id):
            bot.send_message(message.chat.id, "👋 Welcome! You've been registered.")
        else:
            bot.send_message(message.chat.id, "⚠️ Registration failed.")
    else:
        bot.send_message(message.chat.id, "👋 Welcome!")
    show_menu(message)

def show_menu(message):
    """Displays the main menu options to the user."""
    markup = telebot.types.ReplyKeyboardMarkup(resize_keyboard=True)
    markup.add("1.Contribute", "2.Find", "3.Admin Login")
    bot.send_message(message.chat.id, "Choose an option:", reply_markup=markup)

@bot.message_handler(func=lambda m: m.text == "1.Contribute")
def contribute(message):
    """Initiates the faculty contribution process."""
    bot.send_message(message.chat.id,
                     f"Your Telegram ID: {message.from_user.id}\n"
                     "We are securely storing your contributions to help the KLU community.",
                     reply_markup=telebot.types.ReplyKeyboardRemove())
    bot.send_message(message.chat.id, "Please enter the full faculty name with title (e.g., Dr.Ramesh, Mr.Suresh, Ms.Priya, Mrs.Lakshmi):\n\n"
                                      "👉 Type 'exit' to cancel anytime.")
    bot.register_next_step_handler(message, contrib_name)

def contrib_name(message):
    """Processes the faculty name input for contribution."""
    if message.text.lower() == "exit":
        return cancel_flow(message)

    name = message.text.strip()
    if not re.match(r"^(dr|mr|ms|mrs)\.\s*[a-zA-Z]", name, re.IGNORECASE):
        bot.send_message(message.chat.id, "⚠️ Invalid format. Please include a title (e.g., Dr.Ramesh).\n\n"
                                          "👉 Type 'exit' to cancel anytime.")
        return bot.register_next_step_handler(message, contrib_name)

    user_data[message.chat.id] = {"faculty_name": name}

    # Check for existing faculty with similar names
    results = supabase.table("faculty").select("faculty_name, block, cabin").ilike("faculty_name", f"%{name}%").execute()
    if results.data:
        reply_text = "It seems there are existing faculty entries with similar names:\n\n"
        for i, f in enumerate(results.data):
            reply_text += f"{i+1}. 👤 {f['faculty_name']} | 🏢 Block: {f['block']} | 🏠 Cabin: {f['cabin']}\n"
        reply_text += "\nIs the faculty you are trying to add a *new* entry, or is it already listed above?"

        markup = telebot.types.ReplyKeyboardMarkup(resize_keyboard=True, one_time_keyboard=True)
        markup.add("Yes, it's new", "No, it exists")
        bot.send_message(message.chat.id, reply_text, reply_markup=markup, parse_mode="Markdown")
        bot.register_next_step_handler(message, handle_existing_faculty_check)
    else:
        bot.send_message(message.chat.id, "Please enter the block name:\n\n👉 Type 'exit' to cancel anytime.")
        bot.register_next_step_handler(message, contrib_block)

def handle_existing_faculty_check(message):
    """Handles the user's response regarding existing faculty entries."""
    choice = message.text.strip().lower()
    if "yes, it's new" in choice:
        bot.send_message(message.chat.id, "Great! Please enter the block name:\n\n👉 Type 'exit' to cancel anytime.",
                         reply_markup=telebot.types.ReplyKeyboardRemove())
        bot.register_next_step_handler(message, contrib_block)
    elif "no, it exists" in choice:
        bot.send_message(message.chat.id, "Okay, contribution cancelled as the faculty might already exist.",
                         reply_markup=telebot.types.ReplyKeyboardRemove())
        user_data.pop(message.chat.id, None)
        show_menu(message)
    else:
        bot.send_message(message.chat.id, "Invalid choice. Please choose 'Yes, it's new' or 'No, it exists'.")
        # Re-register the handler to ensure a valid choice is made
        bot.register_next_step_handler(message, handle_existing_faculty_check)


def contrib_block(message):
    """Processes the block name input for contribution."""
    if message.text.lower() == "exit":
        return cancel_flow(message)
    user_data[message.chat.id]["block"] = message.text.strip()
    bot.send_message(message.chat.id, "Please enter the cabin number (e.g., L404, M201, R102):\n\n👉 Type 'exit' to cancel anytime.")
    bot.register_next_step_handler(message, contrib_cabin)

def contrib_cabin(message):
    """Processes the cabin number input for contribution."""
    if message.text.lower() == "exit":
        return cancel_flow(message)
    cabin_input = message.text.strip()
    block_code, floor, room = parse_cabin_info(cabin_input)
    data = user_data[message.chat.id]
    data.update({"cabin": cabin_input, "floor": floor, "room": room, "block_code": block_code})
    reply = f"📝 Please confirm the details:\n\n👤 Name: {data['faculty_name']}\n🏢 Block: {data['block']}\n🏠 Cabin: {cabin_input}"
    markup = telebot.types.ReplyKeyboardMarkup(resize_keyboard=True, one_time_keyboard=True)
    markup.add("✅ Confirm", "❌ Cancel")
    bot.send_message(message.chat.id, reply, reply_markup=markup)
    bot.register_next_step_handler(message, finalize_contribution)

def finalize_contribution(message):
    """Finalizes the faculty contribution based on user confirmation."""
    choice = message.text.strip().lower()
    data = user_data.get(message.chat.id)
    if "confirm" in choice and data: # Check if data exists
        insert_faculty_data(data["faculty_name"], data["block"], data["floor"],
                            data["room"], data["cabin"], message.from_user.id)
        bot.send_message(message.chat.id, "✅ Faculty details added successfully!", reply_markup=telebot.types.ReplyKeyboardRemove())
    else:
        bot.send_message(message.chat.id, "❌ Contribution cancelled.", reply_markup=telebot.types.ReplyKeyboardRemove())
    user_data.pop(message.chat.id, None)
    show_menu(message) # Return to main menu

def cancel_flow(message):
    """Cancels the current contribution flow and returns to the main menu."""
    bot.send_message(message.chat.id, "❌ Contribution cancelled.", reply_markup=telebot.types.ReplyKeyboardRemove())
    user_data.pop(message.chat.id, None)
    show_menu(message) # Return to main menu

@bot.message_handler(func=lambda m: m.text == "2.Find")
def find_faculty(message):
    """Initiates the faculty search process."""
    bot.send_message(message.chat.id, "Please enter the faculty name to search:")
    bot.register_next_step_handler(message, process_find_faculty)

def process_find_faculty(message):
    """Processes the faculty name search query and displays results."""
    term = message.text.strip()
    results = supabase.table("faculty").select("*").ilike("faculty_name", f"%{term}%").execute()
    if not results.data:
        bot.send_message(message.chat.id, "❌ No matches found for your search term.")
    else:
        reply = "Here are the faculty members found:\n\n" + "\n".join([f"👤 {f['faculty_name']}\n🏢 Block: {f['block']}\n🏠 Cabin: {f['cabin']}\n" for f in results.data])
        bot.send_message(message.chat.id, reply)
    show_menu(message) # Return to main menu

@bot.message_handler(func=lambda m: m.text == "3.Admin Login")
def admin_login(message):
    """Initiates the admin login process."""
    bot.send_message(message.chat.id, "Please enter the admin username:")
    bot.register_next_step_handler(message, get_admin_user)

def get_admin_user(message):
    """Gets the admin username and prompts for password."""
    if message.text.strip() == admin_credentials["username"]:
        user_data[message.chat.id] = {"admin_try": True}
        bot.send_message(message.chat.id, "Please enter the password:")
        bot.register_next_step_handler(message, get_admin_pass)
    else:
        bot.send_message(message.chat.id, "❌ Wrong username. Please try again.")
        show_menu(message) # Return to main menu

def get_admin_pass(message):
    """Gets the admin password and grants access if correct."""
    if message.text.strip() == admin_credentials["password"]:
        admin_logged_in[message.chat.id] = True
        markup = telebot.types.ReplyKeyboardMarkup(resize_keyboard=True)
        markup.add("View Faculty List", "Download CSV")
        markup.add("/edit_faculty", "/delete_faculty")
        markup.add("Detect Fake")
        bot.send_message(message.chat.id, "✅ Admin logged in successfully!", reply_markup=markup)
    else:
        bot.send_message(message.chat.id, "❌ Wrong password. Please try again.")
        show_menu(message) # Return to main menu

@bot.message_handler(func=lambda m: m.text == "View Faculty List")
def admin_view_faculty(message):
    """Allows admin to view the list of faculty."""
    if not admin_logged_in.get(message.chat.id):
        return bot.send_message(message.chat.id, "❌ You need to be logged in as admin to perform this action.")
    results = supabase.table("faculty").select("*").execute()
    if not results.data:
        bot.send_message(message.chat.id, "❌ No faculty data found.")
    else:
        reply = "Here is the current Faculty List:\n\n" + "\n".join([f"{i+1}. {f['faculty_name']} | Block: {f['block']} | Cabin: {f['cabin']}" for i, f in enumerate(results.data)])
        bot.send_message(message.chat.id, reply)

@bot.message_handler(func=lambda m: m.text == "Download CSV")
def admin_download_csv(message):
    """Allows admin to download faculty data as a CSV file."""
    if not admin_logged_in.get(message.chat.id):
        return bot.send_message(message.chat.id, "❌ You need to be logged in as admin to perform this action.")
    results = supabase.table("faculty").select("*").execute()
    if not results.data:
        return bot.send_message(message.chat.id, "❌ No data to download.")
    df = pd.DataFrame(results.data)
    output = io.BytesIO()
    df.to_csv(output, index=False)
    output.seek(0)
    bot.send_document(message.chat.id, output, visible_file_name="faculty_data.csv")

@bot.message_handler(commands=['edit_faculty'])
def edit_faculty(message):
    """Initiates the process to edit faculty details."""
    if not admin_logged_in.get(message.chat.id):
        return bot.send_message(message.chat.id, "❌ You need to be logged in as admin to perform this action.")
    results = supabase.table("faculty").select("*").execute()
    if not results.data:
        return bot.send_message(message.chat.id, "❌ No faculty records to edit.")
    user_data[message.chat.id] = {'edit_list': results.data}
    reply = "Please select the S.No of the faculty you wish to edit:\n\n" + "\n".join([f"{i+1}. {f['faculty_name']} | Block: {f['block']} | Cabin: {f['cabin']}" for i, f in enumerate(results.data)])
    bot.send_message(message.chat.id, reply)
    bot.register_next_step_handler(message, get_faculty_to_edit)

def get_faculty_to_edit(message):
    """Gets the S.No of the faculty to be edited and prompts for field to edit."""
    try:
        index = int(message.text.strip()) - 1
        if 0 <= index < len(user_data[message.chat.id]['edit_list']):
            user_data[message.chat.id]['edit_id'] = user_data[message.chat.id]['edit_list'][index]['id']
            markup = telebot.types.ReplyKeyboardMarkup(resize_keyboard=True, one_time_keyboard=True)
            markup.add("Edit Name", "Edit Cabin", "Edit Block")
            bot.send_message(message.chat.id, "What would you like to edit for this faculty member?", reply_markup=markup)
            bot.register_next_step_handler(message, edit_field_choice)
        else:
            bot.send_message(message.chat.id, "❌ Invalid selection. Please enter a valid S.No.")
            bot.register_next_step_handler(message, get_faculty_to_edit) # Re-prompt
    except ValueError:
        bot.send_message(message.chat.id, "❌ Invalid input. Please enter a number corresponding to the S.No.")
        bot.register_next_step_handler(message, get_faculty_to_edit) # Re-prompt
    except KeyError:
        bot.send_message(message.chat.id, "An error occurred. Please try /edit_faculty again.")
        show_menu(message) # Return to main menu

def edit_field_choice(message):
    """Allows admin to choose which field to edit for a faculty."""
    choice = message.text.strip().lower()
    if "name" in choice:
        bot.send_message(message.chat.id, "Please enter the new full faculty name with title (e.g., Dr.Ramesh):",
                         reply_markup=telebot.types.ReplyKeyboardRemove())
        bot.register_next_step_handler(message, lambda m: apply_edit_field(m, 'faculty_name'))
    elif "cabin" in choice:
        bot.send_message(message.chat.id, "Please enter the new cabin number (e.g., L404):",
                         reply_markup=telebot.types.ReplyKeyboardRemove())
        bot.register_next_step_handler(message, lambda m: apply_edit_field(m, 'cabin'))
    elif "block" in choice:
        bot.send_message(message.chat.id, "Please enter the new block name:",
                         reply_markup=telebot.types.ReplyKeyboardRemove())
        bot.register_next_step_handler(message, lambda m: apply_edit_field(m, 'block'))
    else:
        bot.send_message(message.chat.id, "❌ Invalid choice. Please select 'Edit Name', 'Edit Cabin', or 'Edit Block'.")
        bot.register_next_step_handler(message, edit_field_choice) # Re-prompt

def apply_edit_field(message, field):
    """Applies the edit to the selected faculty field."""
    new_val = message.text.strip()
    fid = user_data[message.chat.id].get('edit_id')
    if fid:
        if field == 'faculty_name' and not re.match(r"^(dr|mr|ms|mrs)\.\s*[a-zA-Z]", new_val, re.IGNORECASE):
            bot.send_message(message.chat.id, "⚠️ Invalid name format. Please include a title (e.g., Dr.Ramesh).")
            bot.register_next_step_handler(message, lambda m: apply_edit_field(m, field)) # Re-prompt
            return
        elif field == 'cabin' and not re.match(r"^[lrmLRM]\d{3}$", new_val):
            bot.send_message(message.chat.id, "⚠️ Invalid cabin format. Please use (e.g., L404).")
            bot.register_next_step_handler(message, lambda m: apply_edit_field(m, field)) # Re-prompt
            return

        supabase.table("faculty").update({field: new_val}).eq("id", fid).execute()
        bot.send_message(message.chat.id, f"✅ Successfully updated {field} to '{new_val}'.", reply_markup=telebot.types.ReplyKeyboardRemove())
    else:
        bot.send_message(message.chat.id, "❌ An error occurred while applying the edit. Please try again.")
    user_data.pop(message.chat.id, None)
    show_menu(message) # Return to main menu

@bot.message_handler(commands=['delete_faculty'])
def delete_faculty(message):
    """Initiates the process to delete faculty details."""
    if not admin_logged_in.get(message.chat.id):
        return bot.send_message(message.chat.id, "❌ You need to be logged in as admin to perform this action.")
    results = supabase.table("faculty").select("*").execute()
    if not results.data:
        return bot.send_message(message.chat.id, "❌ No faculty records to delete.")
    user_data[message.chat.id] = {'delete_list': results.data}
    reply = "Please select the S.No of the faculty you wish to delete:\n\n" + "\n".join([f"{i+1}. {f['faculty_name']} | Block: {f['block']} | Cabin: {f['cabin']}" for i, f in enumerate(results.data)])
    bot.send_message(message.chat.id, reply + "\n\n👉 Enter S.No to delete, or type 'exit' to cancel.")
    bot.register_next_step_handler(message, confirm_delete_index)

def confirm_delete_index(message):
    """Confirms the deletion of a faculty record."""
    if message.text.strip().lower() == "exit":
        bot.send_message(message.chat.id, "❌ Delete operation cancelled.")
        user_data.pop(message.chat.id, None)
        show_menu(message) # Return to main menu
        return

    try:
        index = int(message.text.strip()) - 1
        delete_list = user_data[message.chat.id].get('delete_list')
        if delete_list and 0 <= index < len(delete_list):
            faculty = delete_list[index]
            fid = faculty['id']
            # Delete associated contributions first to maintain referential integrity
            supabase.table("contributions").delete().eq("faculty_id", fid).execute()
            supabase.table("faculty").delete().eq("id", fid).execute()
            bot.send_message(message.chat.id, f"🗑️ Successfully deleted {faculty['faculty_name']}.", reply_markup=telebot.types.ReplyKeyboardRemove())
        else:
            bot.send_message(message.chat.id, "❌ Invalid selection. Please enter a valid S.No.")
            bot.register_next_step_handler(message, confirm_delete_index) # Re-prompt
    except ValueError:
        bot.send_message(message.chat.id, "❌ Invalid input. Please enter a number corresponding to the S.No.")
        bot.register_next_step_handler(message, confirm_delete_index) # Re-prompt
    except Exception as e:
        logger.error(f"Error during faculty deletion: {e}")
        bot.send_message(message.chat.id, f"❌ An error occurred during deletion: {str(e)}")
    user_data.pop(message.chat.id, None)
    show_menu(message) # Return to main menu

@bot.message_handler(func=lambda m: m.text == "Detect Fake")
def detect_fake_entries(message):
    """Detects and lists potentially fake or malformed faculty entries for admin review."""
    if not admin_logged_in.get(message.chat.id):
        return bot.send_message(message.chat.id, "❌ This action requires admin privileges.")

    results = supabase.table("faculty").select("*").execute()
    if not results.data:
        return bot.send_message(message.chat.id, "❌ No faculty records found to check for fake entries.")

    fake_list = []
    for i, entry in enumerate(results.data):
        name = entry.get('faculty_name', '').lower()
        cabin = entry.get('cabin', '').lower()

        # Rule 1: Name does not start with a title
        if not re.match(r"^(dr|mr|ms|mrs)\.", name):
            fake_list.append((i + 1, entry))
        # Rule 2: Name contains common search terms (indicating potential placeholder/test data)
        elif name in ["find", "name", "search", "test", "demo", "null", "none"]:
            fake_list.append((i + 1, entry))
        # Rule 3: Cabin number format is incorrect
        elif not re.match(r"^[lrmLRM]\d{3}$", cabin):
            fake_list.append((i + 1, entry))

    if not fake_list:
        return bot.send_message(message.chat.id, "✅ No suspicious entries detected. Your data looks clean!")

    user_data[message.chat.id] = {"fake_list": fake_list}
    reply = "🚨 *Detected potentially fake or malformed entries:*\n\n"
    for sno, f in fake_list:
        reply += f"{sno}. 👤 {f.get('faculty_name', 'N/A')} | 🏢 Block: {f.get('block', 'N/A')} | 🏠 Cabin: {f.get('cabin', 'N/A')}\n"
    reply += "\n💬 *To delete, send the S.No(s) separated by commas (e.g., 1,3,5). Type 'exit' to cancel:*"
    bot.send_message(message.chat.id, reply, parse_mode="Markdown")
    bot.register_next_step_handler(message, delete_fake_snos)

def delete_fake_snos(message):
    """Deletes selected fake entries based on admin input."""
    if message.text.strip().lower() == "exit":
        bot.send_message(message.chat.id, "❌ Operation cancelled.", reply_markup=telebot.types.ReplyKeyboardRemove())
        user_data.pop(message.chat.id, None)
        show_menu(message) # Return to main menu
        return

    try:
        snos_input = message.text.split(",")
        snos_to_delete = []
        for s in snos_input:
            s_stripped = s.strip()
            if s_stripped.isdigit():
                snos_to_delete.append(int(s_stripped))
            else:
                raise ValueError("Non-numeric S.No found.")

        fake_entries_list = user_data[message.chat.id].get("fake_list")
        if not fake_entries_list:
            bot.send_message(message.chat.id, "❌ No fake entries were found or the list has expired.")
            user_data.pop(message.chat.id, None)
            show_menu(message)
            return

        deleted_count = 0
        for sno in snos_to_delete:
            if 1 <= sno <= len(fake_entries_list):
                faculty = fake_entries_list[sno - 1][1] # Get the faculty dictionary
                fid = faculty['id']
                # Delete associated contributions first
                supabase.table("contributions").delete().eq("faculty_id", fid).execute()
                supabase.table("faculty").delete().eq("id", fid).execute()
                deleted_count += 1
            else:
                bot.send_message(message.chat.id, f"⚠️ S.No {sno} is out of range and was skipped.")

        if deleted_count > 0:
            bot.send_message(message.chat.id, f"🗑️ Successfully deleted {deleted_count} selected fake entr(y/ies).",
                             reply_markup=telebot.types.ReplyKeyboardRemove())
        else:
            bot.send_message(message.chat.id, "No entries were deleted. Please check your S.No input.",
                             reply_markup=telebot.types.ReplyKeyboardRemove())
    except ValueError:
        bot.send_message(message.chat.id, "❌ Invalid input format. Please send S.No(s) separated by commas (e.g., 1,3,5).")
        bot.register_next_step_handler(message, delete_fake_snos) # Re-prompt
    except Exception as e:
        logger.error(f"Error deleting fake entries: {e}")
        bot.send_message(message.chat.id, f"❌ An unexpected error occurred: {str(e)}")
    user_data.pop(message.chat.id, None)
    show_menu(message) # Return to main menu


def start_bot():
    """Starts the Telegram bot and performs initial table checks."""
    print("🤖 KL Finds Bot is now running...")
    check_and_create_tables()
    bot.infinity_polling()

if __name__ == "__main__":
    start_bot()
