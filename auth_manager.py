from google.auth.transport.requests import Request
import config
from auth.oauth_flow import run_oauth_flow, OAuthFlowError
from auth.playlist_repository import PlaylistRepository
from auth.token_store import TokenStore, TokenStoreError
from auth.youtube_client_factory import (
    build_youtube_client,
    rebuild_youtube_client,
    YoutubeClientFactoryError
)
from network.connectivity import wait_for_internet as wait_for_internet_network
from utils.logging import LoggerMixin
from utils.youtube_api import test_youtube_api_connection


class AuthenticationError(Exception):
    pass


class AuthManager(LoggerMixin):
    def __init__(self, logger=None):
        self.logger = logger
        self.youtube = None
        self.playlists = {"No Playlist": None}
        self.token_store = TokenStore(token_file=config.TOKEN_FILE, logger=self._log)
        self.playlist_repository = PlaylistRepository(logger=self._log)

    def wait_for_internet(self, max_wait=None, interval=None):
        max_wait = max_wait or config.MAX_INTERNET_WAIT_SECONDS
        interval = interval or config.INTERNET_CHECK_INTERVAL_SECONDS
        return wait_for_internet_network(
            urls=config.CONNECTIVITY_CHECK_URLS,
            timeout=config.CONNECTIVITY_CHECK_TIMEOUT,
            interval=interval,
            max_wait=max_wait,
            logger=self._log
        )

    def _load_credentials(self):
        try:
            return self.token_store.load_credentials()
        except TokenStoreError as e:
            raise AuthenticationError(str(e))

    def _save_credentials(self, creds):
        try:
            self.token_store.save_credentials(creds)
        except TokenStoreError as e:
            raise AuthenticationError(str(e))

    def _refresh_credentials(self, creds):
        try:
            self._log("Refreshing expired credentials...")
            creds.refresh(Request())
            self._log("Credentials refreshed successfully")
            return creds
        except Exception as e:
            self._log(f"Failed to refresh credentials: {str(e)}")
            raise AuthenticationError("Token refresh failed, re-authentication required")

    def _run_oauth_flow(self):
        try:
            return run_oauth_flow(
                client_secrets_file=config.CLIENT_SECRETS_FILE,
                scopes=config.YOUTUBE_API_SCOPES,
                logger=self._log
            )
        except OAuthFlowError as e:
            raise AuthenticationError(str(e))

    def _test_client_connection(self):
        self._log("Testing YouTube API connection...")
        if test_youtube_api_connection(self.youtube):
            self._log("YouTube API connection test successful")
            return True
        else:
            self._log("YouTube API connection test failed")
            return False

    def initialize_youtube_client(self, force_reauth=False):
        """Initializes YouTube API client with authentication."""
        if not self.wait_for_internet():
            raise AuthenticationError("No internet connection available")

        creds = None
        if not force_reauth:
            try:
                creds = self._load_credentials()
            except AuthenticationError:
                creds = None

        if creds:
            if creds.expired and creds.refresh_token:
                try:
                    creds = self._refresh_credentials(creds)
                except AuthenticationError:
                    creds = None
            elif not creds.valid:
                creds = None

        if not creds:
            creds = self._run_oauth_flow()

        self._save_credentials(creds)

        try:
            self.youtube = build_youtube_client(creds)
            self._log(config.SUCCESS_AUTH)
        except YoutubeClientFactoryError as e:
            raise AuthenticationError(str(e))

        if not self._test_client_connection():
            raise AuthenticationError("Failed to establish connection to YouTube API")

        self.fetch_playlists()

    def refresh_youtube_client(self):
        try:
            creds = self._load_credentials()
            if not creds:
                self._log("Warning: No credentials available for refresh")
                return False

            try:
                self.youtube = rebuild_youtube_client(creds)
            except YoutubeClientFactoryError as e:
                raise AuthenticationError(str(e))

            if not self._test_client_connection():
                raise AuthenticationError("New client connection test failed")

            self.fetch_playlists()
            self._log("YouTube API client refresh completed successfully")
            return True

        except AuthenticationError as e:
            self._log(f"Failed to refresh YouTube client: {str(e)}")
            return False
        except Exception as e:
            self._log(f"Unexpected error refreshing YouTube client: {str(e)}")
            return False

    def fetch_playlists(self):
        if not self.youtube:
            self._log("Cannot fetch playlists: YouTube client not initialized")
            return
        new_playlists = self.playlist_repository.fetch_playlists(self.youtube)
        if new_playlists is not None:
            self.playlists = new_playlists

    def get_playlist_titles(self):
        return list(self.playlists.keys())

    def get_playlist_id(self, title):
        return self.playlists.get(title)

    def is_client_ready(self):
        return self.youtube is not None

    def get_client(self):
        if not self.youtube:
            raise AuthenticationError("YouTube client not initialized")
        return self.youtube
