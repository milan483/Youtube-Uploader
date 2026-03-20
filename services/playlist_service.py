import config
from utils.logging import LoggerMixin
from googleapiclient.errors import HttpError


class PlaylistService(LoggerMixin):
    def __init__(self, youtube_client, state_manager, logger=None, quota_recorder=None, upload_error_cls=None):
        self.youtube = youtube_client
        self.state_manager = state_manager
        self.logger = logger
        self.quota_recorder = quota_recorder
        self.upload_error_cls = upload_error_cls

    def set_youtube_client(self, youtube_client):
        self.youtube = youtube_client

    def set_logger(self, logger):
        self.logger = logger

    def _raise_upload_error(self, message):
        if self.upload_error_cls:
            raise self.upload_error_cls(message)
        raise Exception(message)

    def add_video_to_playlist(self, video_id, playlist_id):
        try:
            playlist_check = self.youtube.playlists().list(
                part="snippet",
                id=playlist_id
            ).execute()

            if not playlist_check.get('items'):
                error_msg = (f"ERROR: Cannot add video to playlist - "
                           f"playlist {playlist_id} no longer exists or is inaccessible. "
                           f"Please select a different playlist or re-authenticate.")
                self._log(error_msg)
                self._raise_upload_error(error_msg)

            body = {
                "snippet": {
                    "playlistId": playlist_id,
                    "resourceId": {
                        "kind": "youtube#video",
                        "videoId": video_id
                    }
                }
            }

            request = self.youtube.playlistItems().insert(
                part="snippet",
                body=body
            )

            response = request.execute()

            success_msg = config.SUCCESS_PLAYLIST_ADD.format(
                video_id=video_id,
                playlist_id=playlist_id
            )
            self._log(success_msg)

            return True

        except Exception as e:
            if self.upload_error_cls and isinstance(e, self.upload_error_cls):
                raise
            if isinstance(e, HttpError):
                error_content = str(e.content) if hasattr(e, 'content') else str(e)
                if 'not found' in error_content.lower() or 'playlistNotFound' in error_content:
                    error_msg = (f"ERROR: Cannot add video to playlist - "
                               f"playlist {playlist_id} no longer exists or is inaccessible. "
                               f"Please select a different playlist.")
                    self._log(error_msg)
                    self._raise_upload_error(error_msg)
                self._log(f"Error adding video {video_id} to playlist: {str(e)}")
                return False
            self._log(f"Unexpected error adding to playlist: {str(e)}")
            return False

    def get_playlist_item_count(self, playlist_id):
        try:
            request = self.youtube.playlists().list(
                part="contentDetails",
                id=playlist_id
            )
            response = request.execute()
            if response.get('items'):
                return response['items'][0]['contentDetails']['itemCount']
            return 0
        except Exception as e:
            self._log(f"Error getting playlist item count: {str(e)}")
            return 0

    def estimate_sort_quota_cost(self, num_videos):
        fetch_pages = (num_videos + 49) // 50
        fetch_cost = fetch_pages * config.QUOTA_COST_PLAYLIST_LIST
        update_cost = num_videos * config.QUOTA_COST_PLAYLIST_UPDATE
        return fetch_cost + update_cost

    def sort_playlist_alphabetically(self, playlist_id, progress_callback=None):
        try:
            saved_state = self.state_manager.get_playlist_sort_state(playlist_id)

            if saved_state:
                self._log(f"Found saved sort state - resuming from position {saved_state['last_position'] + 1}")
                sorted_items = saved_state['sorted_items']
                start_position = saved_state['last_position'] + 1
            else:
                self._log(f"Fetching playlist items for sorting...")
                playlist_items = []
                next_page_token = None
                page_count = 0

                while True:
                    request = self.youtube.playlistItems().list(
                        part="snippet,contentDetails",
                        playlistId=playlist_id,
                        maxResults=50,
                        pageToken=next_page_token
                    )

                    response = request.execute()
                    page_count += 1

                    items = response.get('items', [])
                    playlist_items.extend(items)

                    if progress_callback:
                        progress_callback(
                            len(playlist_items),
                            len(playlist_items),
                            f"Fetching playlist items (page {page_count})..."
                        )

                    next_page_token = response.get('nextPageToken')
                    if not next_page_token:
                        break

                if not playlist_items:
                    msg = "Playlist is empty, nothing to sort"
                    self._log(msg)
                    return False, msg, 0

                self._log(f"Found {len(playlist_items)} video(s) in playlist")

                estimated_cost = self.estimate_sort_quota_cost(len(playlist_items))
                self._log(f"Estimated quota cost: {estimated_cost:,} units "
                         f"(Daily limit: {config.DEFAULT_DAILY_QUOTA_LIMIT:,} units)")

                if estimated_cost > config.DEFAULT_DAILY_QUOTA_LIMIT:
                    self._log(f"WARNING: Estimated cost ({estimated_cost:,}) exceeds daily quota limit "
                             f"({config.DEFAULT_DAILY_QUOTA_LIMIT:,}). This operation will likely fail partway through.")

                sorted_items = []
                for item in playlist_items:
                    video_title = item['snippet'].get('title', '')
                    sorted_items.append({
                        'id': item['id'],
                        'video_id': item['contentDetails']['videoId'],
                        'title': video_title,
                        'snippet': item['snippet']
                    })

                sorted_items.sort(key=lambda x: x['title'].lower())
                self._log("Sorted playlist items alphabetically")
                start_position = 0

            updated_count = start_position
            failed_count = 0
            quota_exceeded = False
            last_successful_position = start_position - 1

            for new_position in range(start_position, len(sorted_items)):
                item = sorted_items[new_position]
                if progress_callback:
                    progress_callback(
                        new_position + 1,
                        len(sorted_items),
                        f"Updating position: {item['title'][:50]}..."
                    )

                try:
                    update_body = {
                        'id': item['id'],
                        'snippet': {
                            'playlistId': playlist_id,
                            'resourceId': {
                                'kind': 'youtube#video',
                                'videoId': item['video_id']
                            },
                            'position': new_position
                        }
                    }

                    request = self.youtube.playlistItems().update(
                        part='snippet',
                        body=update_body
                    )

                    response = request.execute()
                    updated_count += 1
                    last_successful_position = new_position

                except HttpError as e:
                    error_content = str(e.content) if hasattr(e, 'content') else str(e)

                    if 'quotaExceeded' in error_content or 'uploadLimitExceeded' in error_content:
                        self._log(f"Quota exceeded while updating position for '{item['title']}'")

                        if self.quota_recorder:
                            self.quota_recorder()

                        self.state_manager.save_playlist_sort_state(
                            playlist_id,
                            sorted_items,
                            last_successful_position
                        )

                        quota_exceeded = True
                        failed_count = len(sorted_items) - updated_count
                        break
                    else:
                        self._log(f"Error updating position for '{item['title']}': {str(e)}")
                        failed_count += 1
                        continue

            if quota_exceeded:
                error_msg = (f"Quota exceeded after sorting {updated_count} of {len(sorted_items)} video(s). "
                            f"{failed_count} video(s) were not sorted. "
                            f"Wait 24 hours for quota to reset, then run sort again to continue.")
                self._log(error_msg)
                return False, error_msg, updated_count
            if failed_count > 0:
                partial_msg = (f"Partially sorted playlist: {updated_count} succeeded, {failed_count} failed. "
                              f"Check logs for error details.")
                self._log(partial_msg)
                return False, partial_msg, updated_count

            self.state_manager.clear_playlist_sort_state()
            success_msg = f"Successfully sorted {updated_count} video(s) in playlist alphabetically"
            self._log(success_msg)
            return True, success_msg, updated_count

        except HttpError as e:
            error_msg = f"YouTube API error during playlist sort: {str(e)}"
            self._log(error_msg)
            return False, error_msg, 0
        except Exception as e:
            error_msg = f"Unexpected error sorting playlist: {str(e)}"
            self._log(error_msg)
            return False, error_msg, 0
