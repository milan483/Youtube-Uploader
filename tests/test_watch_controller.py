from collections import defaultdict
from datetime import datetime, timedelta
import threading

from controllers.watch_controller import WatchController
from file_handler import FileHandler
from services.batch_uploader import BatchUploader


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
        self.recursive_options = []

    def upload_folder(self, folder_path, callbacks=None, should_stop=None, recursive=False):
        self.calls += 1
        self.recursive_options.append(recursive)
        if self.script:
            self.script(callbacks or {}, should_stop)
        return {}


class OutcomeBatchUploader:
    """Replay scan outcomes through the same callbacks as BatchUploader."""

    def __init__(self, outcomes):
        self.outcomes = iter(outcomes)
        self.paths = []
        self.recursive_options = []

    def upload_folder(self, folder_path, callbacks=None, should_stop=None, recursive=False):
        self.paths.append(folder_path)
        self.recursive_options.append(recursive)
        outcome = next(self.outcomes)
        if outcome:
            callbacks["on_batch_found"](outcome)
        else:
            callbacks["on_no_files"]()
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


def make_watch_controller(outcomes, events=None):
    events = events if events is not None else defaultdict(list)
    controller = WatchController(
        upload_manager=FakeUploadManager(),
        auth_manager=FakeAuthManager(),
        batch_uploader=OutcomeBatchUploader(outcomes),
        callbacks=make_callbacks(events),
    )
    controller.watch_folder = "/watch"
    return controller, events


def test_empty_scans_at_startup_do_not_notify_until_content_seen():
    controller, events = make_watch_controller([0, 0, 0])

    controller._perform_folder_check()
    controller._perform_folder_check()
    controller._perform_folder_check()

    assert events["notify_empty"] == []


def test_empty_transition_notifies_once_and_content_rearms_notification():
    controller, events = make_watch_controller([2, 0, 0, 1, 0])

    expected_notification_counts = [0, 1, 1, 1, 2]
    for expected_count in expected_notification_counts:
        controller._perform_folder_check()
        assert len(events["notify_empty"]) == expected_count

    assert events["notify_empty"] == [True, True]


def test_normalized_same_folder_keeps_state():
    controller, events = make_watch_controller([1, 0])

    controller._perform_folder_check()
    controller.watch_folder = "/watch/./"
    controller._perform_folder_check()
    assert events["notify_empty"] == [True]

def test_folder_change_does_not_inherit_armed_state():
    controller, events = make_watch_controller([1, 0])

    controller._perform_folder_check()
    controller.watch_folder = "/other"
    controller._perform_folder_check()

    assert events["notify_empty"] == []


def test_stale_callbacks_after_folder_change_and_return_to_same_path_are_ignored():
    events = defaultdict(list)

    class DeferredBatchUploader:
        callbacks = None

        def upload_folder(self, folder_path, callbacks=None, should_stop=None, recursive=False):
            self.callbacks = callbacks

    batch_uploader = DeferredBatchUploader()
    controller = WatchController(
        upload_manager=FakeUploadManager(),
        auth_manager=FakeAuthManager(),
        batch_uploader=batch_uploader,
        callbacks=make_callbacks(events),
    )
    controller.watch_folder = "/watch"

    controller._perform_folder_check()
    stale_callbacks = batch_uploader.callbacks
    controller.watch_folder = "/other"
    controller.watch_folder = "/watch"
    stale_callbacks["on_batch_found"](1)
    stale_callbacks["on_no_files"]()

    assert events["notify_empty"] == []


def test_notify_empty_callback_can_change_folder_without_lock_inversion():
    events = defaultdict(list)
    folder_change_completed = threading.Event()
    callback_observations = []
    folder_change_threads = []

    def notify_empty():
        events["notify_empty"].append(True)
        worker = threading.Thread(
            target=lambda: (setattr(controller, "watch_folder", "/other"), folder_change_completed.set()),
            daemon=True,
        )
        folder_change_threads.append(worker)
        worker.start()
        callback_observations.append(folder_change_completed.wait(timeout=1))

    callbacks = make_callbacks(events)
    callbacks["notify_empty"] = notify_empty
    controller = WatchController(
        upload_manager=FakeUploadManager(),
        auth_manager=FakeAuthManager(),
        batch_uploader=OutcomeBatchUploader([1, 0, 0]),
        callbacks=callbacks,
    )
    controller.watch_folder = "/watch"

    controller._perform_folder_check()
    controller._perform_folder_check()
    for worker in folder_change_threads:
        worker.join(timeout=1)
    controller._perform_folder_check()

    assert callback_observations == [True], "notify_empty ran while folder state remained locked"
    assert all(not worker.is_alive() for worker in folder_change_threads), "folder-change worker did not terminate"
    assert events["notify_empty"] == [True], "new folder inherited the prior folder's notification state"


def test_periodic_and_manual_checks_share_empty_notification_state(monkeypatch):
    controller, events = make_watch_controller([1, 0, 0, 0])
    controller.should_stop = False
    sleep_calls = {"count": 0}

    class ImmediateThread:
        def __init__(self, target, kwargs=None, daemon=None):
            self.target = target
            self.kwargs = kwargs or {}

        def start(self):
            self.target(**self.kwargs)

    monkeypatch.setattr("controllers.watch_controller.threading.Thread", ImmediateThread)

    def stop_after_one_poll(seconds):
        sleep_calls["count"] += 1
        if sleep_calls["count"] == 1:
            controller.should_stop = True

    controller._sleep_interruptible = stop_after_one_poll
    controller._watch_folder_worker()
    controller.should_stop = False
    controller.force_check()
    controller.force_check()

    assert events["notify_empty"] == [True]


def test_recursive_option_is_snapshotted_for_periodic_and_manual_checks(monkeypatch):
    events = defaultdict(list)

    class RecursiveOutcomeUploader:
        def __init__(self):
            self.recursive_options = []
            self.outcomes = iter([1, 0])

        def upload_folder(self, folder_path, callbacks=None, should_stop=None, recursive=False):
            self.recursive_options.append(recursive)
            if next(self.outcomes):
                callbacks["on_batch_found"](1)
            else:
                callbacks["on_no_files"]()

    uploader = RecursiveOutcomeUploader()
    controller = WatchController(
        upload_manager=FakeUploadManager(),
        auth_manager=FakeAuthManager(),
        batch_uploader=uploader,
        callbacks=make_callbacks(events),
    )
    controller.watch_folder = "/watch"
    controller.set_scan_subdirectories(True)
    controller.should_stop = False

    class ImmediateThread:
        def __init__(self, target, kwargs=None, daemon=None):
            self.target = target
            self.kwargs = kwargs or {}

        def start(self):
            self.target(**self.kwargs)

    monkeypatch.setattr("controllers.watch_controller.threading.Thread", ImmediateThread)
    sleep_calls = {"count": 0}

    def stop_after_one_poll(seconds):
        sleep_calls["count"] += 1
        if sleep_calls["count"] == 1:
            controller.should_stop = True

    controller._sleep_interruptible = stop_after_one_poll
    controller._watch_folder_worker()
    controller.should_stop = False
    controller.force_check()

    assert uploader.recursive_options == [True, True]
    assert events["notify_empty"] == [True]


def test_recursive_nested_content_rearms_empty_notification_with_real_scanner(tmp_path):
    events = defaultdict(list)
    nested_folder = tmp_path / "nested"
    nested_folder.mkdir()
    nested_video = nested_folder / "clip.mp4"
    nested_video.write_bytes(b"video")

    class UploadingManager:
        state_manager = None

        def needs_client_refresh(self):
            return False

        def upload_video(self, filepath, progress_callback=None, watch_root=None):
            assert filepath == str(nested_video)
            assert watch_root == str(tmp_path)
            return True, "Uploaded", "video-id"

    controller = WatchController(
        upload_manager=UploadingManager(),
        auth_manager=FakeAuthManager(),
        batch_uploader=BatchUploader(UploadingManager(), FileHandler()),
        callbacks=make_callbacks(events),
    )
    controller.watch_folder = str(tmp_path)
    controller.set_scan_subdirectories(True)

    controller._perform_folder_check()
    nested_video.unlink()
    controller._perform_folder_check()

    assert events["notify_upload_success"] == ["clip.mp4"]
    assert events["notify_empty"] == [True]


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
