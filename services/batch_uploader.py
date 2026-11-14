import os
import ntpath
from datetime import datetime
from file_handler import FileHandler
from utils.logging import LoggerMixin
from utils.upload_utils import is_skip_message


class BatchUploader(LoggerMixin):
    def __init__(self, upload_manager, file_handler, logger=None):
        self.upload_manager = upload_manager
        self.file_handler = file_handler
        self.logger = logger

    def upload_folder(self, folder_path, callbacks=None, should_stop=None, recursive=False):
        from upload_manager import QuotaExceededError

        callbacks = callbacks or {}
        results = {
            'success_count': 0,
            'fail_count': 0,
            'skip_count': 0,
            'total_files': 0,
            'quota_exceeded': False
        }

        refresh_client = callbacks.get('refresh_client')
        if refresh_client and self.upload_manager.needs_client_refresh():
            refresh_client()

        discovered_files = self.file_handler.get_video_files(folder_path, recursive=recursive)
        video_files = []
        for relative_path in discovered_files:
            # Treat discovery output as untrusted, including foreign-platform paths.
            if (os.path.isabs(relative_path) or ntpath.isabs(relative_path)
                    or ntpath.splitdrive(relative_path)[0]
                    or '..' in relative_path.replace('\\', '/').split('/')):
                self._log(f"Ignoring unsafe watch-folder entry: {relative_path}")
                continue
            filepath = os.path.join(folder_path, relative_path)
            if not FileHandler.is_safe_watch_file(filepath, folder_path):
                self._log(f"Ignoring unsafe watch-folder entry: {relative_path}")
                continue
            video_files.append(relative_path)
        results['total_files'] = len(video_files)

        if not video_files:
            on_no_files = callbacks.get('on_no_files')
            if on_no_files:
                on_no_files()
            return results

        warmup_connection = callbacks.get('warmup_connection')
        if warmup_connection:
            if not warmup_connection():
                on_warmup_failed = callbacks.get('on_warmup_failed')
                if on_warmup_failed:
                    on_warmup_failed()

        on_batch_cancelled = callbacks.get('on_batch_cancelled')
        on_batch_found = callbacks.get('on_batch_found')
        if on_batch_cancelled and should_stop and should_stop():
            on_batch_cancelled()
            return results

        filepaths = [os.path.join(folder_path, filename) for filename in video_files]
        state_manager = getattr(self.upload_manager, "state_manager", None)
        files_to_upload = []
        deferred_files = []
        exhausted_files = []
        if state_manager:
            retry_settings = state_manager.get_retry_settings()
            retry_limit = retry_settings['max_upload_retry_attempts']
            for filepath in filepaths:
                state = state_manager.get_upload_state(filepath)
                if state == 'failed' and not state_manager.is_ready_for_retry(filepath, retry_settings):
                    retry_info = state_manager.get_retry_info(filepath)
                    retry_count = retry_info.get('retry_count', 0)
                    if retry_count >= retry_limit:
                        exhausted_files.append((filepath, retry_count))
                    else:
                        deferred_files.append(filepath)
                else:
                    files_to_upload.append(filepath)
        else:
            files_to_upload = filepaths

        total_files = len(files_to_upload)
        total_batch = total_files + len(deferred_files) + len(exhausted_files)

        if on_batch_found:
            on_batch_found(total_batch)

        for filepath, retry_count in exhausted_files:
            results['fail_count'] += 1
            message = (f"Upload failed after {retry_count} attempt(s); "
                       "manual intervention required.")
            on_file_result = callbacks.get('on_file_result')
            if on_file_result:
                on_file_result(False, message, filepath, None)

        for filepath in deferred_files:
            results['skip_count'] += 1
            retry_info = state_manager.get_retry_info(filepath) if state_manager else {}
            next_retry_time = retry_info.get('next_retry_time')
            if next_retry_time:
                try:
                    retry_dt = datetime.fromisoformat(next_retry_time)
                    retry_display = retry_dt.strftime('%Y-%m-%d %H:%M:%S')
                except Exception:
                    retry_display = next_retry_time
                message = f"Retry scheduled after {retry_display}; skipping for now."
            else:
                message = "Retry scheduled; skipping for now."
            on_file_result = callbacks.get('on_file_result')
            if on_file_result:
                on_file_result(False, message, filepath, None)

        if total_files == 0:
            on_batch_complete = callbacks.get('on_batch_complete')
            if on_batch_complete:
                on_batch_complete(results)
            return results

        for index, filepath in enumerate(files_to_upload):
            if should_stop and should_stop():
                on_batch_stopped = callbacks.get('on_batch_stopped')
                if on_batch_stopped:
                    on_batch_stopped(results['success_count'], total_files)
                break

            if not FileHandler.is_safe_watch_file(filepath, folder_path):
                results['fail_count'] += 1
                on_file_error = callbacks.get('on_file_error')
                if on_file_error:
                    on_file_error(filepath, ValueError("Unsafe watch-folder path"))
                continue

            on_file_start = callbacks.get('on_file_start')
            if on_file_start:
                on_file_start(filepath, index, total_files)

            on_progress = callbacks.get('on_progress')

            def upload_progress_callback(percent):
                if on_progress:
                    on_progress(index, total_files, percent)

            try:
                success, message, video_id = self.upload_manager.upload_video(
                    filepath,
                    progress_callback=upload_progress_callback,
                    watch_root=folder_path
                )

                if success:
                    results['success_count'] += 1
                else:
                    if is_skip_message(message):
                        results['skip_count'] += 1
                    else:
                        results['fail_count'] += 1

                on_file_result = callbacks.get('on_file_result')
                if on_file_result:
                    on_file_result(success, message, filepath, video_id)

            except QuotaExceededError:
                results['quota_exceeded'] = True
                on_quota_exceeded = callbacks.get('on_quota_exceeded')
                if on_quota_exceeded:
                    on_quota_exceeded()
                break

            except Exception as e:
                results['fail_count'] += 1
                on_file_error = callbacks.get('on_file_error')
                if on_file_error:
                    on_file_error(filepath, e)

        on_batch_complete = callbacks.get('on_batch_complete')
        if on_batch_complete:
            on_batch_complete(results)

        return results
