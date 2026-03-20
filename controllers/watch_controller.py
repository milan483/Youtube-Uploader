import os
import threading
import time
from datetime import datetime

import config
from utils.logging import LoggerMixin
from utils.upload_utils import is_skip_message


class WatchController(LoggerMixin):
    def __init__(self, upload_manager, auth_manager, batch_uploader, logger=None, callbacks=None):
        self.upload_manager = upload_manager
        self.auth_manager = auth_manager
        self.batch_uploader = batch_uploader
        self.logger = logger
        self.callbacks = callbacks or {}
        self.should_stop = False
        self.worker_thread = None
        self.watch_folder = ""
        self._check_lock = threading.Lock()

    def set_callbacks(self, callbacks):
        self.callbacks = callbacks or {}

    def set_logger(self, logger):
        self.logger = logger

    def start(self, watch_folder):
        self.watch_folder = watch_folder
        if self.worker_thread and self.worker_thread.is_alive():
            self.should_stop = False
            return
        self.should_stop = False
        self.worker_thread = threading.Thread(
            target=self._watch_folder_worker,
            daemon=True
        )
        self.worker_thread.start()

    def stop(self):
        self.should_stop = True

    def force_check(self):
        check_thread = threading.Thread(
            target=self._perform_folder_check,
            kwargs={'log_skip': True},
            daemon=True
        )
        check_thread.start()

    def is_running(self):
        return self.worker_thread is not None and self.worker_thread.is_alive()

    def _emit(self, name, *args, **kwargs):
        callback = self.callbacks.get(name)
        if callback:
            callback(*args, **kwargs)

    def _set_status(self, message):
        self._emit('set_status', message)

    def _set_progress(self, percent):
        self._emit('set_progress', percent)

    def _set_next_check(self, message):
        self._emit('set_next_check', message)

    def _watch_folder_worker(self):
        while not self.should_stop:
            if self.upload_manager.is_in_cooldown():
                cooldown_end = self.upload_manager.get_cooldown_end_time()

                if cooldown_end:
                    now = datetime.now()
                    if cooldown_end.date() != now.date():
                        next_check_str = cooldown_end.strftime('%Y-%m-%d %H:%M:%S')
                    else:
                        next_check_str = cooldown_end.strftime('%H:%M:%S')

                    self._set_next_check(f"Next check: {next_check_str}")
                    self._log(f"In 24-hour cooldown. Next check at {next_check_str}")

                    seconds_until_end = (cooldown_end - datetime.now()).total_seconds()
                    self._sleep_interruptible(seconds_until_end)

                    continue

            self._perform_folder_check()

            self._set_next_check("Next check: Waiting for user action...")
            self._sleep_interruptible(config.WATCH_FOLDER_POLL_INTERVAL)

    def _perform_folder_check(self, log_skip=False):
        if not self._check_lock.acquire(blocking=False):
            if log_skip:
                self._log("Folder check already in progress; skipping this request.")
            return

        try:
            batch_counts = {'success': 0, 'fail': 0, 'skip': 0, 'size': 0}
            flags = {'cancelled': False, 'empty': False}

            def refresh_client():
                self._log("Refreshing YouTube API client...")
                try:
                    if self.auth_manager.refresh_youtube_client():
                        self.upload_manager.set_youtube_client(self.auth_manager.youtube)
                        self._log("YouTube API client refreshed successfully")
                    else:
                        self._log("Warning: YouTube API client refresh failed")
                        self._log("Continuing with existing connection...")
                except Exception as e:
                    self._log(f"Warning: Could not refresh YouTube API client: {str(e)}")
                    self._log("Continuing with existing connection...")

            def on_no_files():
                flags['empty'] = True
                self._log("No new videos found in watch folder")
                self._emit('notify_empty')

            def on_batch_found(total_files):
                batch_counts['size'] = total_files
                self._log(f"Found {total_files} video(s) to upload")

            def on_batch_cancelled():
                flags['cancelled'] = True
                self._log("Stop requested - cancelling upload batch")

            def on_batch_stopped(success_count, total_files):
                self._log(f"Stop requested - stopped after {success_count} of {total_files} video(s)")

            def on_file_start(filepath, index, total_files):
                filename = os.path.basename(filepath)
                percent = (index / total_files) * 100
                self._set_progress(percent)
                self._set_status(f"Uploading {index + 1} of {total_files}: {filename}")
                self._log(f"Starting upload {index + 1}/{total_files}: {filename}")

            def on_progress(current_index, total_files, percent):
                self._set_progress(percent)

            def on_file_result(success, message, filepath, video_id):
                filename = os.path.basename(filepath)
                is_skip = is_skip_message(message)

                if success:
                    self._log(message)
                    batch_counts['success'] += 1
                    self._emit('notify_upload_success', filename)
                else:
                    if is_skip:
                        self._log(f"Skipped: {message}")
                        batch_counts['skip'] += 1
                    else:
                        self._log(f"Failed: {message}")
                        batch_counts['fail'] += 1
                        self._emit('notify_upload_failed', filename, message)

            def on_file_error(filepath, error):
                filename = os.path.basename(filepath)
                self._log(f"Error uploading {filename}: {str(error)}")
                batch_counts['fail'] += 1
                self._emit('notify_upload_error', filename, str(error))

            def on_quota_exceeded():
                self._log("Quota exceeded, stopping upload cycle")
                self._emit('notify_quota_exceeded')

            callbacks = {
                'refresh_client': refresh_client,
                'on_no_files': on_no_files,
                'on_batch_found': on_batch_found,
                'on_batch_cancelled': on_batch_cancelled,
                'on_batch_stopped': on_batch_stopped,
                'on_file_start': on_file_start,
                'on_progress': on_progress,
                'on_file_result': on_file_result,
                'on_file_error': on_file_error,
                'on_quota_exceeded': on_quota_exceeded
            }

            self.batch_uploader.upload_folder(
                self.watch_folder,
                callbacks=callbacks,
                should_stop=lambda: self.should_stop
            )

            if flags['cancelled'] or flags['empty']:
                return

            self._set_progress(0)
            self._set_status("Upload cycle complete")

            if batch_counts['success'] > 0:
                summary = f"Uploaded {batch_counts['success']} of {batch_counts['size']} video(s)"
                if batch_counts['skip'] > 0 and batch_counts['fail'] > 0:
                    summary += f" ({batch_counts['skip']} skipped, {batch_counts['fail']} failed)"
                elif batch_counts['skip'] > 0:
                    summary += f" ({batch_counts['skip']} skipped)"
                elif batch_counts['fail'] > 0:
                    summary += f" ({batch_counts['fail']} failed)"
                self._emit('notify_batch_complete', summary)

        except Exception as e:
            self._log(f"Error in folder check: {str(e)}")
        finally:
            self._check_lock.release()

    def _sleep_interruptible(self, seconds):
        end_time = time.time() + seconds

        while time.time() < end_time:
            if self.should_stop:
                break
            time.sleep(config.SLEEP_INCREMENT_SECONDS)
