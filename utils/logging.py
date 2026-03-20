class LoggerMixin:
    def _log(self, message):
        logger = getattr(self, "logger", None)
        if logger:
            logger(message)
