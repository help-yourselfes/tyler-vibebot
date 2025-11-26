import os
from dotenv import load_dotenv

load_dotenv()

BOT_TOKEN = os.getenv("BOT_TOKEN")
ADMIN_IDS = [int(x.strip()) for x in os.getenv("ADMIN_IDS", "").split(",") if x.strip()]

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DATA_DIR = os.path.join(BASE_DIR, "data")
TASKS_DIR = os.path.join(BASE_DIR, "tasks")

USERS_FILE = os.path.join(DATA_DIR, "users.json")
TASKS_FILE = os.path.join(TASKS_DIR, "daily_tasks.json")
