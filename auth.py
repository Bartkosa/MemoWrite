"""Authentication module for Google OAuth integration."""
import streamlit as st
from google_auth_oauthlib.flow import Flow
from google.auth.transport.requests import Request
import os
import json
from typing import Optional, Dict
import pickle
from pathlib import Path
import uuid


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


def get_last_user_file() -> Path:
    """Get the file path for storing the last authenticated user's email."""
    return CREDENTIALS_DIR / ".last_user.txt"


def save_last_user_email(email: str):
    """Save the last authenticated user's email for persistence across page refreshes."""
    try:
        last_user_file = get_last_user_file()
        with open(last_user_file, 'w') as f:
            f.write(email)
    except Exception as e:
        print(f"Warning: Failed to save last user email: {str(e)}")


def load_last_user_email() -> Optional[str]:
    """Load the last authenticated user's email."""
    try:
        last_user_file = get_last_user_file()
        if last_user_file.exists():
            with open(last_user_file, 'r') as f:
                email = f.read().strip()
                if email:
                    return email
    except Exception as e:
        print(f"Warning: Failed to load last user email: {str(e)}")
    return None


def clear_last_user_email():
    """Clear the last authenticated user's email (e.g., on logout)."""
    try:
        last_user_file = get_last_user_file()
        if last_user_file.exists():
            last_user_file.unlink()
    except Exception as e:
        print(f"Warning: Failed to clear last user email: {str(e)}")


def get_or_create_device_id() -> str:
    """Get or create a device ID from query parameters.
    
    If device_id exists in query params, return it.
    If not, generate a new UUID and add it to query params.
    
    Returns:
        Device ID string
    """
    query_params = st.query_params
    device_id = query_params.get('device_id', '')
    
    if not device_id:
        # Generate a new device ID
        device_id = str(uuid.uuid4())
        # Add to query parameters
        query_params['device_id'] = device_id
        st.query_params = query_params
    
    return device_id


def get_device_auth_file(device_id: str) -> Path:
    """Get the file path for storing device-specific authentication.
    
    Args:
        device_id: Unique device identifier
        
    Returns:
        Path to device-specific auth file
    """
    return CREDENTIALS_DIR / f".device_{device_id}.txt"


def save_device_auth(device_id: str, email: str):
    """Save the authenticated user's email for a specific device.
    
    Args:
        device_id: Unique device identifier
        email: User's email address
    """
    try:
        device_auth_file = get_device_auth_file(device_id)
        with open(device_auth_file, 'w') as f:
            f.write(email)
    except Exception as e:
        print(f"Warning: Failed to save device auth: {str(e)}")


def load_device_auth(device_id: str) -> Optional[str]:
    """Load the authenticated user's email for a specific device.
    
    Args:
        device_id: Unique device identifier
        
    Returns:
        User's email if found, None otherwise
    """
    try:
        device_auth_file = get_device_auth_file(device_id)
        if device_auth_file.exists():
            with open(device_auth_file, 'r') as f:
                email = f.read().strip()
                if email:
                    return email
    except Exception as e:
        print(f"Warning: Failed to load device auth: {str(e)}")
    return None


def clear_device_auth(device_id: str):
    """Clear the device-specific authentication file.
    
    Args:
        device_id: Unique device identifier
    """
    try:
        device_auth_file = get_device_auth_file(device_id)
        if device_auth_file.exists():
            device_auth_file.unlink()
    except Exception as e:
        print(f"Warning: Failed to clear device auth: {str(e)}")


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
    if 'device_id' not in st.session_state:
        st.session_state.device_id = None


def check_authentication() -> bool:
    """Check if user is authenticated. Returns True if authenticated."""
    init_session_state()
    
    # Get or create device ID (ensures it's in query params for persistence)
    device_id = get_or_create_device_id()
    st.session_state.device_id = device_id
    
    # Check if we have valid credentials in session state
    if st.session_state.get('authenticated') and st.session_state.get('user_info'):
        # Verify credentials are still valid
        credentials = st.session_state.get('credentials')
        if credentials:
            if refresh_credentials_if_needed(credentials):
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
            # Save device-specific authentication (persists across page refreshes)
            save_device_auth(device_id, user_email)
            
            # Clear the code from URL (but keep device_id)
            query_params.pop('code', None)
            st.query_params = query_params
            st.rerun()
            
        except Exception as e:
            st.error(f"Authentication error: {str(e)}")
            return False
    
    # If not authenticated in session state, try loading from device-specific file
    # This allows persistence across page refreshes while maintaining device independence
    if not st.session_state.get('authenticated'):
        # First try session state (for same browser session)
        stored_email = st.session_state.get('last_authenticated_email')
        
        # If not in session state, try loading from device-specific file
        if not stored_email:
            stored_email = load_device_auth(device_id)
            if stored_email:
                # Restore to session state for this session
                st.session_state.last_authenticated_email = stored_email
        
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
                                # Clear device auth if credentials are invalid
                                clear_device_auth(device_id)
                                # Clear session state
                                if 'last_authenticated_email' in st.session_state:
                                    del st.session_state['last_authenticated_email']
                    else:
                        # Email mismatch - security issue, clear the stored email
                        print(f"Security: Email mismatch. Expected {stored_email}, got {user_info.get('email')}")
                        clear_device_auth(device_id)
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
    # Get device ID from query params or session state
    device_id = st.query_params.get('device_id') or st.session_state.get('device_id')
    
    # Clear device-specific authentication file
    if device_id:
        clear_device_auth(device_id)
    
    # Delete credentials file if email is known (optional - for full logout)
    # Note: This deletes credentials for all devices. If you want device-specific logout only,
    # comment out the delete_credentials_file call
    email = st.session_state.get('last_authenticated_email') or (st.session_state.get('user_info') or {}).get('email')
    if email:
        delete_credentials_file(email)
    
    # Clear all authentication-related session state
    # Session state is device/browser-specific, so this only affects the current device
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

