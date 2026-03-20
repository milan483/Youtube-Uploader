from collections import defaultdict
from datetime import datetime, timedelta

from controllers.watch_controller import WatchController


class FakeUploadManager:
    def __init__(self, in_cooldown=False, cooldown_end=None):
        self._in_cooldown = in_cooldown
        self._cooldown_end = cooldown_end
        self.youtube_updates = []

    def is_in_cooldown(self):
        return self._in_cooldown

    def get_cooldown_end_time(self):
        return self._cooldown_end

    def set_youtube_client(self, youtube_client):
        self.youtube_updates.append(youtube_client)


class FakeAuthManager:
    def __init__(self, refresh_result=True):
        self.youtube = object()
        self.refresh_result = refresh_result

    def refresh_youtube_client(self):
        return self.refresh_result


class ScriptedBatchUploader:
    def __init__(self, script=None):
        self.script = script
        self.calls = 0

    def upload_folder(self, folder_path, callbacks=None, should_stop=None):
        self.calls += 1
        if self.script:
            self.script(callbacks or {}, should_stop)
        return {}


def make_callbacks(events):
    return {
        "set_progress": lambda value: events["set_progress"].append(value),
        "set_status": lambda value: events["set_status"].append(value),
        "set_next_check": lambda value: events["set_next_check"].append(value),
        "notify_empty": lambda: events["notify_empty"].append(True),
        "notify_upload_success": lambda filename: events["notify_upload_success"].append(filename),
        "notify_upload_failed": lambda filename, message: events["notify_upload_failed"].append((filename, message)),
        "notify_upload_error": lambda filename, message: events["notify_upload_error"].append((filename, message)),
        "notify_quota_exceeded": lambda: events["notify_quota_exceeded"].append(True),
        "notify_batch_complete": lambda summary: events["notify_batch_complete"].append(summary),
    }


def test_perform_folder_check_emits_success_and_skip_summary():
    events = defaultdict(list)

    def run_batch(callbacks, should_stop):
        callbacks["on_batch_found"](2)
        callbacks["on_file_start"]("/watch/a.mp4", 0, 2)
        callbacks["on_file_result"](True, "Uploaded", "/watch/a.mp4", "vid-1")
        callbacks["on_file_result"](
            False,
            "Retry scheduled after 2099-01-01 12:00:00; skipping for now.",
            "/watch/b.mp4",
            None,
        )

    controller = WatchController(
        upload_manager=FakeUploadManager(),
        auth_manager=FakeAuthManager(),
        batch_uploader=ScriptedBatchUploader(script=run_batch),
        callbacks=make_callbacks(events),
    )
    controller.watch_folder = "/watch"

    controller._perform_folder_check()

    assert events["notify_upload_success"] == ["a.mp4"]
    assert events["notify_batch_complete"] == ["Uploaded 1 of 2 video(s) (1 skipped)"]
    assert events["set_status"][-1] == "Upload cycle complete"
    assert events["set_progress"][-1] == 0


def test_perform_folder_check_skips_if_check_already_in_progress(log_messages):
    events = defaultdict(list)
    batch_uploader = ScriptedBatchUploader()
    controller = WatchController(
        upload_manager=FakeUploadManager(),
        auth_manager=FakeAuthManager(),
        batch_uploader=batch_uploader,
        logger=log_messages.append,
        callbacks=make_callbacks(events),
    )
    controller.watch_folder = "/watch"
    acquired = controller._check_lock.acquire(blocking=False)

    try:
        controller._perform_folder_check(log_skip=True)
    finally:
        if acquired:
            controller._check_lock.release()

    assert batch_uploader.calls == 0
    assert any("already in progress" in message for message in log_messages)


def test_watch_folder_worker_honors_cooldown_and_does_not_run_batch():
    events = defaultdict(list)
    cooldown_end = datetime.now() + timedelta(minutes=5)
    controller = WatchController(
        upload_manager=FakeUploadManager(in_cooldown=True, cooldown_end=cooldown_end),
        auth_manager=FakeAuthManager(),
        batch_uploader=ScriptedBatchUploader(),
        callbacks=make_callbacks(events),
    )
    perform_calls = {"count": 0}
    slept = {"seconds": None}

    def fake_sleep(seconds):
        slept["seconds"] = seconds
        controller.should_stop = True

    def fake_perform():
        perform_calls["count"] += 1

    controller._sleep_interruptible = fake_sleep
    controller._perform_folder_check = fake_perform
    controller.should_stop = False

    controller._watch_folder_worker()

    assert perform_calls["count"] == 0
    assert slept["seconds"] is not None
    assert slept["seconds"] > 0
    assert events["set_next_check"]
    assert events["set_next_check"][-1].startswith("Next check:")
