"""Authentication module for Google OAuth integration."""
import streamlit as st
from google_auth_oauthlib.flow import Flow
from google.auth.transport.requests import Request
import os
import json
from typing import Optional, Dict
import pickle
from pathlib import Path


SCOPES = ["openid", "https://www.googleapis.com/auth/userinfo.email", "https://www.googleapis.com/auth/userinfo.profile"]

# Directory to store credentials files
CREDENTIALS_DIR = Path("data/credentials")
CREDENTIALS_DIR.mkdir(parents=True, exist_ok=True)


def get_client_config() -> dict:
    """Get OAuth client configuration from secrets or environment variables."""
    client_id = ""
    client_secret = ""
    
    # Try to get from Streamlit secrets first
    try:
        if hasattr(st, 'secrets'):
            try:
                client_id = st.secrets.get("GOOGLE_CLIENT_ID", "")
                client_secret = st.secrets.get("GOOGLE_CLIENT_SECRET", "")
            except (AttributeError, KeyError, TypeError, Exception):
                # Streamlit not initialized or secrets not available
                pass
    except (AttributeError, Exception):
        # Streamlit not available at all
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
        if hasattr(st, 'secrets'):
            try:
                redirect_uri = st.secrets.get("REDIRECT_URI", "")
                if redirect_uri:
                    return redirect_uri
            except (AttributeError, KeyError, TypeError, Exception):
                # Streamlit not initialized or secrets not available
                pass
    except (AttributeError, Exception):
        # Streamlit not available at all
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


def get_credentials_file_path(email: str) -> Path:
    """Get the file path for storing credentials for a given email."""
    # Sanitize email to use as filename
    safe_email = email.replace("@", "_at_").replace(".", "_")
    return CREDENTIALS_DIR / f"{safe_email}.pickle"


def save_credentials(email: str, credentials, user_info: Dict):
    """Save credentials and user info to a file for persistence across sessions."""
    try:
        credentials_file = get_credentials_file_path(email)
        with open(credentials_file, 'wb') as f:
            pickle.dump({
                'credentials': credentials,
                'user_info': user_info
            }, f)
    except Exception as e:
        # Log error but don't fail authentication if file save fails
        print(f"Warning: Failed to save credentials to file: {str(e)}")


def load_credentials(email: str) -> Optional[Dict]:
    """Load credentials and user info from file."""
    try:
        credentials_file = get_credentials_file_path(email)
        if credentials_file.exists():
            with open(credentials_file, 'rb') as f:
                return pickle.load(f)
    except Exception as e:
        print(f"Warning: Failed to load credentials from file: {str(e)}")
    return None


def delete_credentials_file(email: str):
    """Delete the credentials file for a given email."""
    try:
        credentials_file = get_credentials_file_path(email)
        if credentials_file.exists():
            credentials_file.unlink()
    except Exception as e:
        print(f"Warning: Failed to delete credentials file: {str(e)}")


def refresh_credentials_if_needed(credentials):
    """Refresh OAuth credentials if they are expired or about to expire."""
    if credentials.expired and credentials.refresh_token:
        try:
            credentials.refresh(Request())
            return True
        except Exception as e:
            print(f"Warning: Failed to refresh credentials: {str(e)}")
            return False
    return True


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
        # Verify credentials are still valid
        credentials = st.session_state.get('credentials')
        if credentials:
            if refresh_credentials_if_needed(credentials):
                return True
    
    # Try to load credentials from file (for persistence across page refreshes)
    # SECURITY: Only load credentials if we know which user's credentials to load
    # We check for stored email in session state to identify the user
    stored_email = st.session_state.get('last_authenticated_email')
    
    # Check for authorization code in URL (after OAuth redirect)
    query_params = st.query_params
    
    if 'code' in query_params:
        # Handle OAuth callback
        try:
            flow = get_flow()
            flow.fetch_token(code=query_params['code'])
            
            credentials = flow.credentials
            user_info = get_user_info(credentials)
            user_email = user_info.get('email')
            
            # Refresh credentials if needed
            refresh_credentials_if_needed(credentials)
            
            # Store in session state
            st.session_state.authenticated = True
            st.session_state.user_info = user_info
            st.session_state.credentials = credentials
            st.session_state.last_authenticated_email = user_email
            
            # Save to file for persistence
            save_credentials(user_email, credentials, user_info)
            
            # Clear the code from URL
            st.query_params.clear()
            st.rerun()
            
        except Exception as e:
            st.error(f"Authentication error: {str(e)}")
            return False
    
    # If not authenticated in session state, try loading from file
    # SECURITY: Only load credentials if we know which user's credentials to load
    # Never automatically load the most recent file as it could belong to a different user
    if not st.session_state.get('authenticated'):
        # Only try to load credentials if we have a stored email for this session
        # This ensures we only load credentials for the user who started this session
        stored_email = st.session_state.get('last_authenticated_email')
        if stored_email:
            # We know which user's credentials to load
            saved_data = load_credentials(stored_email)
            if saved_data:
                credentials = saved_data.get('credentials')
                user_info = saved_data.get('user_info')
                
                if credentials and user_info:
                    # Verify the email matches (security check)
                    if user_info.get('email') == stored_email:
                        # Refresh credentials if needed
                        if refresh_credentials_if_needed(credentials):
                            try:
                                # Store in session state
                                st.session_state.authenticated = True
                                st.session_state.user_info = user_info
                                st.session_state.credentials = credentials
                                st.session_state.last_authenticated_email = stored_email
                                
                                # Save updated credentials back to file
                                save_credentials(stored_email, credentials, user_info)
                                
                                return True
                            except Exception as e:
                                # Credentials are invalid, remove the file
                                print(f"Credentials invalid, removing file: {str(e)}")
                                delete_credentials_file(stored_email)
                    else:
                        # Email mismatch - security issue, clear the stored email
                        print(f"Security: Email mismatch. Expected {stored_email}, got {user_info.get('email')}")
                        if 'last_authenticated_email' in st.session_state:
                            del st.session_state['last_authenticated_email']
    
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
    # Delete credentials file if email is known
    email = st.session_state.get('last_authenticated_email') or (st.session_state.get('user_info') or {}).get('email')
    if email:
        delete_credentials_file(email)
    
    # Clear all authentication-related session state
    for key in ['authenticated', 'user_info', 'user_id', 'credentials', 'oauth_state', 'last_authenticated_email']:
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

