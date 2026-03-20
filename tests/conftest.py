import sys
import types

import pytest


def _install_googleapiclient_stubs():
    googleapiclient_module = types.ModuleType("googleapiclient")
    http_module = types.ModuleType("googleapiclient.http")
    errors_module = types.ModuleType("googleapiclient.errors")

    class StubHttpError(Exception):
        def __init__(self, content=""):
            super().__init__(str(content))
            self.content = content

    class StubMediaFileUpload:
        def __init__(self, *args, **kwargs):
            self._fd = types.SimpleNamespace(close=lambda: None)

    http_module.MediaFileUpload = StubMediaFileUpload
    errors_module.HttpError = StubHttpError
    googleapiclient_module.http = http_module
    googleapiclient_module.errors = errors_module

    sys.modules["googleapiclient"] = googleapiclient_module
    sys.modules["googleapiclient.http"] = http_module
    sys.modules["googleapiclient.errors"] = errors_module


try:
    import googleapiclient  # noqa: F401
except Exception:
    _install_googleapiclient_stubs()


@pytest.fixture
def log_messages():
    return []


@pytest.fixture
def logger(log_messages):
    return log_messages.append
