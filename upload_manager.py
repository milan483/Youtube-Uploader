import os
import time
from datetime import datetime, timedelta
from googleapiclient.http import MediaFileUpload
from googleapiclient.errors import HttpError
import config
from utils.youtube_api import test_youtube_api_connection
from utils.logging import LoggerMixin
from utils.config_utils import format_file_size, get_uploaded_folder_path
from services.batch_uploader import BatchUploader
from services.playlist_service import PlaylistService


class UploadError(Exception):
    pass


class QuotaExceededError(Exception):
    pass


class UploadManager(LoggerMixin):
    def __init__(self, youtube_client, file_handler, state_manager, logger=None):
        self.youtube = youtube_client
        self.file_handler = file_handler
        self.state_manager = state_manager
        self.logger = logger
        self.batch_uploader = BatchUploader(self, self.file_handler, logger=self._log)
        self.playlist_service = PlaylistService(
            self.youtube,
            self.state_manager,
            logger=self._log,
            quota_recorder=self.record_quota_exceeded,
            upload_error_cls=UploadError
        )
        self.privacy_status = config.DEFAULT_PRIVACY_SETTING
        self.selected_playlist_id = None
        self.selected_category = config.DEFAULT_VIDEO_CATEGORY
        self.session_upload_count = 0
        self.client_created_time = datetime.now()
        self.uploads_since_refresh = 0

    def set_logger(self, logger):
        self.logger = logger
        self.playlist_service.set_logger(self._log)

    def _is_transient_network_error(self, error):
        error_str = str(error).lower()
        error_repr = repr(error).lower()
        transient_indicators = [
            'winerror 10053',
            'connection reset',
            'broken pipe',
            'connection aborted',
            'connection refused',
            'econnreset',
            'econnaborted',
            'epipe',
            'timeout',
            'temporarily unavailable',
            'network unreachable',
        ]
        for indicator in transient_indicators:
            if indicator in error_str or indicator in error_repr:
                return True
        return False

    def _client_needs_refresh(self):
        client_age = (datetime.now() - self.client_created_time).total_seconds()
        if client_age > config.CLIENT_REFRESH_INTERVAL_SECONDS:
            return True
        if self.uploads_since_refresh >= config.CLIENT_REFRESH_UPLOAD_INTERVAL:
            return True
        return False

    def needs_client_refresh(self):
        return self._client_needs_refresh()

    def set_youtube_client(self, youtube_client):
        self.youtube = youtube_client
        self.playlist_service.set_youtube_client(youtube_client)
        self.client_created_time = datetime.now()
        self.uploads_since_refresh = 0
        self._log("YouTube API client refreshed")

    def set_privacy(self, privacy_status):
        if privacy_status not in config.PRIVACY_SETTINGS:
            raise ValueError(f"Invalid privacy status: {privacy_status}")
        self.privacy_status = privacy_status
        self._log(f"Privacy setting changed to: {privacy_status}")

    def set_playlist(self, playlist_id):
        self.selected_playlist_id = playlist_id
        if playlist_id:
            self._log(f"Playlist set to ID: {playlist_id}")
        else:
            self._log("Playlist set to: No Playlist")

    def set_category(self, category_name):
        if category_name not in config.VIDEO_CATEGORIES:
            raise ValueError(f"Invalid video category: {category_name}")
        self.selected_category = category_name
        self._log(f"Video category set to: {category_name}")

    def is_in_cooldown(self):
        last_quota_hit = self.state_manager.get_last_quota_hit()
        if not last_quota_hit:
            return False
        try:
            last_hit_dt = datetime.fromisoformat(last_quota_hit)
            cooldown_end = last_hit_dt + timedelta(
                hours=config.QUOTA_COOLDOWN_HOURS,
                minutes=config.QUOTA_COOLDOWN_BUFFER_MINUTES
            )
            return datetime.now() < cooldown_end
        except Exception as e:
            self._log(f"Error checking cooldown: {str(e)}")
            return False

    def get_cooldown_end_time(self):
        last_quota_hit = self.state_manager.get_last_quota_hit()
        if not last_quota_hit:
            return None
        try:
            last_hit_dt = datetime.fromisoformat(last_quota_hit)
            cooldown_end = last_hit_dt + timedelta(
                hours=config.QUOTA_COOLDOWN_HOURS,
                minutes=config.QUOTA_COOLDOWN_BUFFER_MINUTES
            )
            return cooldown_end
        except Exception:
            return None

    def record_quota_exceeded(self):
        self.state_manager.record_quota_hit()
        self._log(config.INFO_QUOTA_EXCEEDED)

    def upload_video(self, filepath, progress_callback=None):
        """Uploads a video file to YouTube. Returns (success, message, video_id)."""
        filename = os.path.basename(filepath)

        if not os.path.isfile(filepath):
            return False, f"File not found: {filename}", None

        file_size = os.path.getsize(filepath)
        if file_size > config.MAX_FILE_SIZE_BYTES:
            size_formatted = format_file_size(file_size)
            max_size_formatted = format_file_size(config.MAX_FILE_SIZE_BYTES)
            error_msg = f"File too large: {filename} ({size_formatted}) exceeds YouTube's {max_size_formatted} limit"
            self._log(error_msg)
            return False, error_msg, None

        self._log(f"File size: {format_file_size(file_size)}")

        self._log(f"Computing hash for {filename}...")
        file_hash = self.file_handler.compute_file_hash(filepath)
        if file_hash is None:
            return False, f"Failed to compute hash for {filename}", None

        if self.state_manager.is_file_uploaded(file_hash):
            msg = config.INFO_ALREADY_UPLOADED.format(filename=filename)
            self._log(msg)
            return False, msg, None

        self.state_manager.set_upload_state(filepath, 'uploading')

        video_title = os.path.splitext(filename)[0]
        category_id = config.VIDEO_CATEGORIES.get(self.selected_category, '22')
        body = {
            'snippet': {
                'title': video_title,
                'description': '',
                'tags': [],
                'categoryId': category_id
            },
            'status': {
                'privacyStatus': self.privacy_status
            }
        }

        transient_retry_count = 0
        chunk_size = config.UPLOAD_CHUNK_SIZE if file_size > 100 * 1024 * 1024 else -1

        try:
            test_youtube_api_connection(self.youtube)
        except Exception:
            pass

        while True:
            media = None
            try:
                media = MediaFileUpload(
                    filepath,
                    chunksize=chunk_size,
                    resumable=True
                )

                self._log(f"Uploading {filename} to YouTube...")

                try:
                    request = self.youtube.videos().insert(
                        part=','.join(body.keys()),
                        body=body,
                        media_body=media
                    )

                    if chunk_size == -1:
                        response = request.execute()
                        video_id = response['id']
                    else:
                        response = None
                        while response is None:
                            status, response = request.next_chunk()
                            if status:
                                progress = int(status.progress() * 100)
                                self._log(f"Upload progress: {progress}%")
                                if progress_callback:
                                    progress_callback(progress)
                        video_id = response['id']

                except HttpError as e:
                    error_content = str(e.content) if hasattr(e, 'content') else str(e)
                    if 'quotaExceeded' in error_content or 'uploadLimitExceeded' in error_content:
                        self.record_quota_exceeded()
                        raise QuotaExceededError("YouTube upload quota exceeded")
                    raise

                finally:
                    if media and hasattr(media, '_fd') and media._fd:
                        media._fd.close()
                        time.sleep(config.INITIAL_FILE_OPERATION_DELAY)

                break

            except QuotaExceededError:
                self.state_manager.set_upload_state(filepath, 'failed')
                raise

            except Exception as e:
                if media and hasattr(media, '_fd') and media._fd:
                    try:
                        media._fd.close()
                    except:
                        pass

                is_transient = self._is_transient_network_error(e)

                if is_transient and transient_retry_count < config.MAX_UPLOAD_RETRY_ATTEMPTS:
                    transient_retry_count += 1
                    delay = config.TRANSIENT_NETWORK_ERROR_RETRY_DELAY_SECONDS
                    self._log(f"Transient network error: {str(e)}")
                    self._log(f"Waiting {delay} seconds before retry "
                              f"(attempt {transient_retry_count + 1}/{config.MAX_UPLOAD_RETRY_ATTEMPTS + 1})...")
                    time.sleep(delay)
                    continue

                retry_count = self.state_manager.get_retry_count(filepath)
                retry_count += 1

                if is_transient:
                    error_type = "transient network error (retries exhausted)"
                    delay = config.INITIAL_RETRY_DELAY_SECONDS
                    delay_msg = f"{delay // 60} minute(s)"
                else:
                    error_type = "error"
                    delay = min(
                        config.INITIAL_RETRY_DELAY_SECONDS * (2 ** (retry_count - 1)),
                        config.MAX_RETRY_DELAY_SECONDS
                    )
                    delay_msg = f"{delay // 60} minute(s)"

                if retry_count < config.MAX_UPLOAD_RETRY_ATTEMPTS:
                    next_retry = datetime.now() + timedelta(seconds=delay)
                    self.state_manager.set_upload_state(
                        filepath,
                        'failed',
                        retry_count=retry_count,
                        next_retry_time=next_retry.isoformat()
                    )
                    error_msg = (f"Upload failed for {filename}: {str(e)} ({error_type}). "
                               f"Will retry (attempt {retry_count + 1}/{config.MAX_UPLOAD_RETRY_ATTEMPTS}) "
                               f"in {delay_msg}.")
                    self._log(error_msg)
                else:
                    self.state_manager.set_upload_state(
                        filepath,
                        'failed',
                        retry_count=retry_count
                    )
                    error_msg = (f"Upload failed for {filename} after {config.MAX_UPLOAD_RETRY_ATTEMPTS} attempts: {str(e)}. "
                               f"Manual intervention required.")
                    self._log(error_msg)

                return False, error_msg, None

        playlist_warning = None
        if self.selected_playlist_id:
            try:
                self.playlist_service.add_video_to_playlist(video_id, self.selected_playlist_id)
            except UploadError as e:
                playlist_warning = f"Playlist add failed: {str(e)}"
                self._log(playlist_warning)

        watch_folder = os.path.dirname(filepath)
        uploaded_folder = get_uploaded_folder_path(watch_folder)

        if not self.file_handler.ensure_directory_exists(uploaded_folder):
            self._log(f"Warning: Could not create Uploaded folder: {uploaded_folder}")

        destination = os.path.join(uploaded_folder, filename)
        move_success, move_msg = self.file_handler.safe_move(filepath, destination, file_hash)

        if not move_success:
            self._log(f"Warning: {move_msg}")
            self._log("File was uploaded but could not be moved. Original file remains.")

        self.state_manager.add_upload_to_history(file_hash, filename, video_id)
        self.state_manager.set_upload_state(filepath, 'completed')
        self.session_upload_count += 1
        self.uploads_since_refresh += 1

        if self._client_needs_refresh():
            self._log("YouTube API client refresh needed (age or usage limit reached)")

        success_msg = config.SUCCESS_UPLOAD.format(
            filename=filename,
            count=self.session_upload_count
        )
        if playlist_warning:
            success_msg = f"{success_msg} (Warning: {playlist_warning})"
        self._log(success_msg)

        return True, success_msg, video_id

    def get_playlist_item_count(self, playlist_id):
        return self.playlist_service.get_playlist_item_count(playlist_id)

    def estimate_sort_quota_cost(self, num_videos):
        return self.playlist_service.estimate_sort_quota_cost(num_videos)

    def sort_playlist_alphabetically(self, playlist_id, progress_callback=None):
        return self.playlist_service.sort_playlist_alphabetically(
            playlist_id,
            progress_callback=progress_callback
        )

    def warmup_connection(self):
        self._log("Testing YouTube API connection before batch upload...")
        if test_youtube_api_connection(self.youtube):
            self._log("YouTube API connection healthy")
            return True
        else:
            self._log("YouTube API connection test failed - uploads will retry on first failure")
            return False

    def upload_files_from_folder(self, folder_path, progress_callback=None, should_stop_callback=None):
        results = {
            'success_count': 0,
            'fail_count': 0,
            'skip_count': 0,
            'total_files': 0,
            'quota_exceeded': False
        }

        try:
            def on_no_files():
                self._log(config.INFO_NO_VIDEOS_FOUND)

            def on_batch_found(total_files):
                self._log(f"Found {total_files} video(s) to upload")

            def on_batch_stopped(success_count, total_files):
                self._log("Upload batch stopped by user")

            def on_file_start(filepath, index, total_files):
                if progress_callback:
                    percent = (index / total_files) * 100
                    progress_callback(index, total_files, percent)

            def on_quota_exceeded():
                self._log("Quota exceeded, stopping batch upload")

            def on_warmup_failed():
                self._log("Warning: YouTube API connection test failed. First upload may fail, but will retry automatically.")

            callbacks = {
                'on_no_files': on_no_files,
                'on_batch_found': on_batch_found,
                'on_batch_stopped': on_batch_stopped,
                'on_file_start': on_file_start,
                'on_quota_exceeded': on_quota_exceeded,
                'warmup_connection': self.warmup_connection,
                'on_warmup_failed': on_warmup_failed
            }

            results = self.batch_uploader.upload_folder(
                folder_path,
                callbacks=callbacks,
                should_stop=should_stop_callback
            )

            if results['total_files'] == 0:
                return results

            if progress_callback:
                progress_callback(results['total_files'], results['total_files'], 100)

            self._log(f"Batch upload complete: {results['success_count']} succeeded, "
                     f"{results['skip_count']} skipped, {results['fail_count']} failed")

            return results

        except Exception as e:
            self._log(f"Error in batch upload: {str(e)}")
            return results

    def get_session_stats(self):
        return {
            'uploads_this_session': self.session_upload_count,
            'total_uploads_all_time': self.state_manager.get_upload_count(),
            'privacy_setting': self.privacy_status,
            'playlist_selected': bool(self.selected_playlist_id),
            'in_cooldown': self.is_in_cooldown()
        }
