import retry_settings_dialog
from retry_settings_dialog import RetrySettingsDialog
from utils.retry_settings import DEFAULT_RETRY_SETTINGS


class FakeVar:
    def __init__(self, value):
        self.value = str(value)

    def get(self):
        return self.value

    def set(self, value):
        self.value = value


class FakeWindow:
    def __init__(self):
        self.closed = False

    def destroy(self):
        self.closed = True


def make_dialog(settings=None, save_error=None):
    class Manager:
        def __init__(self):
            self.saved = []

        def set_retry_settings(self, values):
            if save_error:
                raise save_error
            self.saved.append(values)

    dialog = RetrySettingsDialog.__new__(RetrySettingsDialog)
    dialog.vars = {
        key: FakeVar(value)
        for key, value in (settings or DEFAULT_RETRY_SETTINGS).items()
    }
    dialog.window = FakeWindow()
    dialog.state_manager = Manager()
    dialog.on_saved = None
    return dialog


def test_validation_failure_does_not_save_or_close(monkeypatch):
    errors = []
    monkeypatch.setattr(
        retry_settings_dialog.messagebox, 'showerror',
        lambda *args, **kwargs: errors.append(args)
    )
    dialog = make_dialog({**DEFAULT_RETRY_SETTINGS, 'max_upload_retry_attempts': '1.5'})
    dialog._save()
    assert errors and dialog.state_manager.saved == []
    assert not dialog.window.closed


def test_persistence_failure_is_visible_and_preserves_dialog(monkeypatch):
    errors = []
    monkeypatch.setattr(
        retry_settings_dialog.messagebox, 'showerror',
        lambda *args, **kwargs: errors.append(args)
    )
    dialog = make_dialog(save_error=OSError('disk full'))
    dialog._save()
    assert errors and 'disk full' in errors[0][1]
    assert not dialog.window.closed


def test_defaults_only_fill_fields_until_save():
    dialog = make_dialog({**DEFAULT_RETRY_SETTINGS, 'max_upload_retry_attempts': 8})
    dialog._restore_defaults()
    assert dialog.state_manager.saved == []
    assert dialog.vars['max_upload_retry_attempts'].get() == '3'
    dialog._save()
    assert dialog.state_manager.saved == [DEFAULT_RETRY_SETTINGS]
    assert dialog.window.closed
