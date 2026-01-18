"""Configuration settings for MemoWrite."""
import os
import streamlit as st
from dotenv import load_dotenv

load_dotenv()

# Gemini API Configuration
# Try Streamlit secrets first, then environment variables
def get_gemini_api_key() -> str:
    """Get Gemini API key from Streamlit secrets or environment variables."""
    # Try Streamlit secrets first (for Streamlit Cloud)
    try:
        if hasattr(st, 'secrets') and st.secrets:
            api_key = st.secrets.get("GEMINI_API_KEY", "")
            if api_key:
                return api_key
    except (AttributeError, KeyError, TypeError):
        pass
    
    # Fallback to environment variables (for local development)
    return os.getenv("GEMINI_API_KEY", "")

GEMINI_API_KEY = get_gemini_api_key()
GEMINI_MODEL = "gemini-2.0-flash-exp"  # Using Gemini 2.0 Flash as specified

# Database Configuration
# Try Streamlit secrets first, then environment variables
def get_database_url() -> str:
    """Get database URL from Streamlit secrets or environment variables."""
    # Try Streamlit secrets first (for Streamlit Cloud)
    try:
        if hasattr(st, 'secrets') and st.secrets:
            db_url = st.secrets.get("DATABASE_URL", "")
            if db_url:
                return db_url
    except (AttributeError, KeyError, TypeError):
        pass
    
    # Fallback to environment variables (for local development)
    return os.getenv("DATABASE_URL", "")

# PostgreSQL connection string format: postgresql://user:password@host:port/database
# Example: postgresql://postgres:password@localhost:5432/memowrite
# For cloud deployments: Use your cloud provider's PostgreSQL connection string
# (e.g., Heroku Postgres, AWS RDS, Supabase, Neon, etc.)
DATABASE_URL = get_database_url()
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
os.makedirs(UPLOADS_DIR, exist_ok=True)

