import os
import sys
from pathlib import Path

# App
APP_NAME = "YouTube Uploader"
APP_VERSION = "2.0.1"
APP_AUTHOR = "GRard"

# Paths
PROJECT_DIR = Path(__file__).resolve().parent
IS_LINUX = sys.platform.startswith('linux')
if IS_LINUX:
    CONFIG_DIR = Path(os.environ.get('XDG_CONFIG_HOME') or (Path.home() / '.config')) / 'youtube-uploader'
    DATA_DIR = Path(os.environ.get('XDG_DATA_HOME') or (Path.home() / '.local/share')) / 'youtube-uploader'
    STATE_DIR = Path(os.environ.get('XDG_STATE_HOME') or (Path.home() / '.local/state')) / 'youtube-uploader'
    # Keep compatibility with a credentials file already placed in the project,
    # while preferring the XDG config directory for new Linux installations.
    _project_credentials = PROJECT_DIR / 'client_secrets.json'
    _config_credentials = CONFIG_DIR / 'client_secrets.json'
    CLIENT_SECRETS_FILE = os.environ.get(
        'YOUTUBE_UPLOADER_CLIENT_SECRETS',
        str(_config_credentials if _config_credentials.exists() or not _project_credentials.exists()
            else _project_credentials)
    )
    TOKEN_FILE = str(CONFIG_DIR / 'token.pickle')
    UPLOAD_HISTORY_FILE = str(STATE_DIR / 'upload_history.json')
    UPLOAD_STATE_FILE = str(STATE_DIR / 'upload_state.json')
    QUOTA_STATE_FILE = str(STATE_DIR / 'quota_state.json')
    PLAYLIST_SORT_STATE_FILE = str(STATE_DIR / 'playlist_sort_state.json')
    USER_PREFERENCES_FILE = str(CONFIG_DIR / 'user_preferences.json')
else:
    CLIENT_SECRETS_FILE = 'client_secrets.json'
    TOKEN_FILE = 'token.pickle'
    UPLOAD_HISTORY_FILE = 'upload_history.json'
    UPLOAD_STATE_FILE = 'upload_state.json'
    QUOTA_STATE_FILE = 'quota_state.json'
    PLAYLIST_SORT_STATE_FILE = 'playlist_sort_state.json'
    USER_PREFERENCES_FILE = 'user_preferences.json'

# YouTube API
YOUTUBE_API_SCOPES = [
    'https://www.googleapis.com/auth/youtube.upload',
    'https://www.googleapis.com/auth/youtube'
]
YOUTUBE_API_SERVICE_NAME = 'youtube'
YOUTUBE_API_VERSION = 'v3'
MAX_PLAYLISTS_TO_FETCH = 50

VIDEO_CATEGORIES = {
    'Film & Animation': '1',
    'Autos & Vehicles': '2',
    'Music': '10',
    'Pets & Animals': '15',
    'Sports': '17',
    'Travel & Events': '19',
    'Gaming': '20',
    'People & Blogs': '22',
    'Comedy': '23',
    'Entertainment': '24',
    'News & Politics': '25',
    'Howto & Style': '26',
    'Education': '27',
    'Science & Technology': '28',
    'Nonprofits & Activism': '29'
}
DEFAULT_VIDEO_CATEGORY = 'People & Blogs'

# Quota
QUOTA_COOLDOWN_BUFFER_MINUTES = 5  # safety buffer
QUOTA_COOLDOWN_HOURS = 24
QUOTA_COST_PLAYLIST_LIST = 1
QUOTA_COST_PLAYLIST_UPDATE = 50
QUOTA_COST_VIDEO_UPLOAD = 1600
QUOTA_COST_PLAYLIST_INSERT = 50
DEFAULT_DAILY_QUOTA_LIMIT = 10000

# Retry
MAX_UPLOAD_RETRY_ATTEMPTS = 3
INITIAL_RETRY_DELAY_SECONDS = 60
MAX_RETRY_DELAY_SECONDS = 3600
MAX_FILE_OPERATION_RETRIES = 5
INITIAL_FILE_OPERATION_DELAY = 0.5
MAX_FILE_OPERATION_DELAY = 10

# Automation
DEFAULT_AUTONOMOUS_MODE = False
DEFAULT_AUTO_START_WATCHING = False
DEFAULT_START_MINIMIZED = False
DEFAULT_NOTIFY_WHEN_EMPTY = True
DEFAULT_AUTO_CLOSE_WHEN_EMPTY = False
WINDOWS_STARTUP_SHORTCUT_NAME = 'YouTube Uploader.lnk'

# Notifications
DEFAULT_NOTIFY_UPLOAD_SUCCESS = False
DEFAULT_NOTIFY_UPLOAD_FAILED = True
DEFAULT_NOTIFY_QUOTA_EXCEEDED = True
DEFAULT_NOTIFY_BATCH_COMPLETE = False

# UI
ICON_PATH = str(PROJECT_DIR / 'assets' / 'icon.png')
FALLBACK_TRAY_ICON_COLOR = 'red'
GUI_WINDOW_WIDTH = 800
GUI_WINDOW_HEIGHT = 600
GUI_LOG_HEIGHT = 10
TRAY_ICON_SIZE = 64
LOG_TIMESTAMP_FORMAT = '%H:%M:%S'
STATE_TIMESTAMP_FORMAT = '%Y-%m-%dT%H:%M:%S'

# Files
SUPPORTED_VIDEO_EXTENSIONS = ('.mp4', '.mov', '.avi')
UPLOADED_FOLDER_NAME = 'Uploaded'
MD5_CHUNK_SIZE = 65536
COPY_CHUNK_SIZE = 4 * 1024 * 1024  # 4MB
MAX_FILE_SIZE_BYTES = 256 * 1024 * 1024 * 1024  # 256GB
UPLOAD_CHUNK_SIZE = 10 * 1024 * 1024  # 10MB

# Network
MAX_INTERNET_WAIT_SECONDS = 300
INTERNET_CHECK_INTERVAL_SECONDS = 10
CONNECTIVITY_CHECK_URLS = [
    "https://1.1.1.1",
    "https://8.8.8.8",
    "https://api.github.com",
    "https://cloudflare.com",
    "https://amazon.com"
]
CONNECTIVITY_CHECK_TIMEOUT = 5
CLIENT_REFRESH_INTERVAL_SECONDS = 1800  # 30 min
CLIENT_REFRESH_UPLOAD_INTERVAL = 50
TRANSIENT_NETWORK_ERROR_RETRY_DELAY_SECONDS = 5
YOUTUBE_API_TEST_TIMEOUT = 10

# Timing
SLEEP_INCREMENT_SECONDS = 5
WATCH_FOLDER_POLL_INTERVAL = 30
CLEANUP_TIMEOUT_SECONDS = 5

# Privacy
PRIVACY_SETTINGS = ['private', 'unlisted', 'public']
DEFAULT_PRIVACY_SETTING = 'private'

# Messages
ERROR_NO_CLIENT_SECRETS = (
    "client_secrets.json not found!\n\n"
    "Please download your OAuth credentials from Google Cloud Console "
    "and place them in the same directory as this script."
)
ERROR_NO_WATCH_FOLDER = "Please select a watch folder before starting."
ERROR_YOUTUBE_CLIENT_INIT = "Failed to initialize YouTube client. Check logs for details."
ERROR_AUTHENTICATION_FAILED = "Authentication failed. Please check your credentials."

SUCCESS_AUTH = "YouTube client initialized successfully"
SUCCESS_UPLOAD = "Successfully uploaded {filename} (Total uploads this session: {count})"
SUCCESS_PLAYLIST_ADD = "Successfully added video {video_id} to playlist {playlist_id}"

INFO_NO_VIDEOS_FOUND = "No new videos found in the watch folder."
INFO_ALREADY_UPLOADED = "File already uploaded: {filename}"
INFO_QUOTA_EXCEEDED = "Quota or upload limit exceeded. Recording last quota hit and stopping uploads."
INFO_IN_COOLDOWN = "In a 24-hour cooldown. Will re-check at {cooldown_end}."
INFO_COOLDOWN_EXPIRED = "Cooldown appears to have expired, proceeding with normal check."


def validate_config():
    if not os.path.exists(CLIENT_SECRETS_FILE):
        raise FileNotFoundError(ERROR_NO_CLIENT_SECRETS)
    if MD5_CHUNK_SIZE <= 0:
        raise ValueError("MD5_CHUNK_SIZE must be positive")
    if QUOTA_COOLDOWN_HOURS <= 0:
        raise ValueError("QUOTA_COOLDOWN_HOURS must be positive")
    if QUOTA_COOLDOWN_BUFFER_MINUTES < 0:
        raise ValueError("QUOTA_COOLDOWN_BUFFER_MINUTES cannot be negative")
    if DEFAULT_PRIVACY_SETTING not in PRIVACY_SETTINGS:
        raise ValueError(f"DEFAULT_PRIVACY_SETTING must be one of {PRIVACY_SETTINGS}")
    for ext in SUPPORTED_VIDEO_EXTENSIONS:
        if not ext.startswith('.'):
            raise ValueError(f"Video extension '{ext}' must start with a dot")
        if ext != ext.lower():
            raise ValueError(f"Video extension '{ext}' must be lowercase")
    return True
