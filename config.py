"""Configuration settings for MemoWrite."""
import os
from dotenv import load_dotenv

load_dotenv()

# Gemini API Configuration
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY", "")
GEMINI_MODEL = "gemini-2.0-flash-exp"  # Using Gemini 2.0 Flash as specified

# Database Configuration
DATABASE_PATH = os.getenv("DATABASE_PATH", "data/course_notes.db")
UPLOADS_DIR = "data/uploads"

# Application Settings
MAX_ANSWER_LENGTH = int(os.getenv("MAX_ANSWER_LENGTH", "5000"))
GRADING_STRICTNESS = float(os.getenv("GRADING_STRICTNESS", "0.7"))

# Spaced Repetition Settings
SR_INITIAL_EASE = 2.5
SR_MIN_EASE = 1.3
SR_EASY_BONUS = 1.3

# Google OAuth Configuration (can be overridden by Streamlit secrets)
GOOGLE_CLIENT_ID = os.getenv("GOOGLE_CLIENT_ID", "")
GOOGLE_CLIENT_SECRET = os.getenv("GOOGLE_CLIENT_SECRET", "")

# Ensure directories exist
os.makedirs(os.path.dirname(DATABASE_PATH), exist_ok=True)
os.makedirs(UPLOADS_DIR, exist_ok=True)

