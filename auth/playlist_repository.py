from googleapiclient.errors import HttpError
import config
from utils.logging import LoggerMixin


class PlaylistRepository(LoggerMixin):
    def __init__(self, logger=None):
        self.logger = logger

    def fetch_playlists(self, youtube_client):
        new_playlists = {"No Playlist": None}

        try:
            next_page_token = None
            page_count = 0

            while True:
                request = youtube_client.playlists().list(
                    part="snippet",
                    mine=True,
                    maxResults=config.MAX_PLAYLISTS_TO_FETCH,
                    pageToken=next_page_token
                )

                response = request.execute()
                page_count += 1

                for item in response.get("items", []):
                    playlist_title = item["snippet"]["title"]
                    playlist_id = item["id"]
                    new_playlists[playlist_title] = playlist_id

                next_page_token = response.get('nextPageToken')
                if not next_page_token:
                    break

                self._log(f"Fetching playlists page {page_count + 1}...")

            playlist_count = len(new_playlists) - 1
            self._log(f"Fetched {playlist_count} playlist(s) from YouTube ({page_count} page(s))")

        except HttpError as e:
            self._log(f"HTTP error fetching playlists: {str(e)}")
            return None
        except Exception as e:
            self._log(f"Unexpected error fetching playlists: {str(e)}")
            return None

        return new_playlists
