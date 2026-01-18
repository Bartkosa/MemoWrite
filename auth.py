"""Authentication module for Google OAuth integration."""
import streamlit as st
from google_auth_oauthlib.flow import Flow
from google.auth.transport.requests import Request
import os
import json
from typing import Optional, Dict
import pickle


SCOPES = ["openid", "https://www.googleapis.com/auth/userinfo.email", "https://www.googleapis.com/auth/userinfo.profile"]


def get_client_config() -> dict:
    """Get OAuth client configuration from secrets or environment variables."""
    client_id = ""
    client_secret = ""
    
    # Try to get from Streamlit secrets first
    try:
        if hasattr(st, 'secrets') and st.secrets:
            client_id = st.secrets.get("GOOGLE_CLIENT_ID", "")
            client_secret = st.secrets.get("GOOGLE_CLIENT_SECRET", "")
    except (AttributeError, KeyError, TypeError):
        pass
    
    # Fallback to environment variables
    if not client_id:
        client_id = os.getenv("GOOGLE_CLIENT_ID", "")
    if not client_secret:
        client_secret = os.getenv("GOOGLE_CLIENT_SECRET", "")
    
    # Validate that we have credentials
    if not client_id or not client_secret:
        raise ValueError(
            "Missing OAuth credentials. Please set GOOGLE_CLIENT_ID and GOOGLE_CLIENT_SECRET "
            "in Streamlit secrets or environment variables."
        )
    
    return {
        "web": {
            "client_id": client_id,
            "client_secret": client_secret,
            "auth_uri": "https://accounts.google.com/o/oauth2/auth",
            "token_uri": "https://oauth2.googleapis.com/token",
            "redirect_uris": [
                "http://localhost:8501/",
            ]
        }
    }


def get_redirect_uri() -> str:
    """Get the redirect URI based on the current environment."""
    # First, try to get from Streamlit secrets (most reliable - user can set it explicitly)
    try:
        if hasattr(st, 'secrets') and st.secrets:
            redirect_uri = st.secrets.get("REDIRECT_URI", "")
            if redirect_uri:
                return redirect_uri
    except (AttributeError, KeyError, TypeError):
        pass
    
    # Check environment variable (set by Streamlit Cloud)
    base_url = os.getenv("STREAMLIT_SERVER_BASE_URL", "")
    if base_url:
        # Ensure proper format
        if not base_url.startswith('http'):
            base_url = f"https://{base_url}"
        # Ensure trailing slash
        return f"{base_url.rstrip('/')}/"
    
    # Check if we're on Streamlit Cloud by looking for the domain pattern
    # This is a fallback detection method
    try:
        # Check for Streamlit Cloud indicators
        if os.getenv("STREAMLIT_SHARING", "").lower() == "true":
            # We're on Streamlit Cloud, but need the actual URL
            # Try to construct from app name if available
            app_name = os.getenv("STREAMLIT_APP_NAME", "")
            if app_name:
                return f"https://{app_name}.streamlit.app/"
    except:
        pass
    
    # Default: localhost for local development
    return "http://localhost:8501/"


def get_flow() -> Flow:
    """Create and return OAuth flow."""
    redirect_uri = get_redirect_uri()
    client_config = get_client_config()
    flow = Flow.from_client_config(
        client_config,
        scopes=SCOPES,
        redirect_uri=redirect_uri
    )
    return flow


def get_user_info(credentials) -> Dict:
    """Get user information from Google API using credentials."""
    import requests
    
    user_info_url = "https://www.googleapis.com/oauth2/v2/userinfo"
    headers = {"Authorization": f"Bearer {credentials.token}"}
    response = requests.get(user_info_url, headers=headers)
    
    if response.status_code == 200:
        return response.json()
    else:
        raise Exception(f"Failed to fetch user info: {response.status_code}")


def init_session_state():
    """Initialize authentication-related session state variables."""
    if 'authenticated' not in st.session_state:
        st.session_state.authenticated = False
    if 'user_info' not in st.session_state:
        st.session_state.user_info = None
    if 'user_id' not in st.session_state:
        st.session_state.user_id = None


def check_authentication() -> bool:
    """Check if user is authenticated. Returns True if authenticated."""
    init_session_state()
    
    # Check if we have valid credentials in session state
    if st.session_state.get('authenticated') and st.session_state.get('user_info'):
        return True
    
    # Check for authorization code in URL (after OAuth redirect)
    query_params = st.query_params
    
    if 'code' in query_params:
        # Handle OAuth callback
        try:
            flow = get_flow()
            flow.fetch_token(code=query_params['code'])
            
            credentials = flow.credentials
            user_info = get_user_info(credentials)
            
            # Store in session state
            st.session_state.authenticated = True
            st.session_state.user_info = user_info
            st.session_state.credentials = credentials
            
            # Clear the code from URL
            st.query_params.clear()
            st.rerun()
            
        except Exception as e:
            st.error(f"Authentication error: {str(e)}")
            return False
    
    return st.session_state.get('authenticated', False)


def get_login_url() -> str:
    """Generate Google OAuth login URL."""
    try:
        flow = get_flow()
        authorization_url, state = flow.authorization_url(
            access_type='offline',
            include_granted_scopes='true',
            prompt='consent'
        )
        st.session_state.oauth_state = state
        return authorization_url
    except Exception as e:
        st.error(f"Error generating login URL: {str(e)}")
        return ""


def login():
    """Initiate Google OAuth login flow."""
    login_url = get_login_url()
    if login_url:
        st.markdown(f"[Click here to login with Google]({login_url})")
    else:
        st.error("Failed to generate login URL. Please check your OAuth configuration.")


def logout():
    """Log out the current user."""
    # Clear all authentication-related session state
    for key in ['authenticated', 'user_info', 'user_id', 'credentials', 'oauth_state']:
        if key in st.session_state:
            del st.session_state[key]
    st.rerun()


def require_auth():
    """Decorator/function to require authentication before accessing app features."""
    if not check_authentication():
        st.title("🔐 Authentication Required")
        st.info("Please log in with Google to access MemoWrite.")
        login()
        st.stop()


def get_user_email() -> Optional[str]:
    """Get the email of the currently authenticated user."""
    if st.session_state.get('authenticated') and st.session_state.get('user_info'):
        return st.session_state.user_info.get('email')
    return None


def get_user_name() -> Optional[str]:
    """Get the name of the currently authenticated user."""
    if st.session_state.get('authenticated') and st.session_state.get('user_info'):
        return st.session_state.user_info.get('name', 'User')
    return None


def get_user_picture() -> Optional[str]:
    """Get the profile picture URL of the currently authenticated user."""
    if st.session_state.get('authenticated') and st.session_state.get('user_info'):
        return st.session_state.user_info.get('picture')
    return None

