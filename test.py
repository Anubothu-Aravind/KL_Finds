from dotenv import load_dotenv
import os

# Load the .env file
load_dotenv()

# Access the token
token = os.getenv("BOT_TOKEN")

print(token)  # Just to check it's working (remove in production)