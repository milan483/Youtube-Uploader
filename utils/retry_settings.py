import config


RETRY_FIELDS = (
    ('max_upload_retry_attempts', 1, 100),
    ('initial_retry_delay_seconds', 1, 86400),
    ('max_retry_delay_seconds', 1, 86400),
)
RETRY_SETTING_KEYS = tuple(field[0] for field in RETRY_FIELDS)
RETRY_SETTING_LABELS = {
    'max_upload_retry_attempts': 'Maximum upload attempts',
    'initial_retry_delay_seconds': 'Initial retry delay',
    'max_retry_delay_seconds': 'Maximum retry delay',
}
DEFAULT_RETRY_SETTINGS = {
    'max_upload_retry_attempts': config.MAX_UPLOAD_RETRY_ATTEMPTS,
    'initial_retry_delay_seconds': config.INITIAL_RETRY_DELAY_SECONDS,
    'max_retry_delay_seconds': config.MAX_RETRY_DELAY_SECONDS,
}


def validate_retry_settings(settings):
    if not isinstance(settings, dict):
        raise ValueError('Retry settings must be a dictionary')
    valid = {}
    for key, minimum, maximum in RETRY_FIELDS:
        value = settings.get(key)
        if type(value) is not int or not minimum <= value <= maximum:
            raise ValueError(
                f'{RETRY_SETTING_LABELS[key]} must be a whole number from {minimum} to {maximum}'
            )
        valid[key] = value
    if valid['max_retry_delay_seconds'] < valid['initial_retry_delay_seconds']:
        raise ValueError('Maximum retry delay must be at least the initial retry delay')
    return valid


def effective_retry_settings(saved):
    effective = DEFAULT_RETRY_SETTINGS.copy()
    if not isinstance(saved, dict):
        return effective
    for key, minimum, maximum in RETRY_FIELDS:
        value = saved.get(key)
        if type(value) is int and minimum <= value <= maximum:
            effective[key] = value
    if effective['max_retry_delay_seconds'] < effective['initial_retry_delay_seconds']:
        effective['initial_retry_delay_seconds'] = DEFAULT_RETRY_SETTINGS['initial_retry_delay_seconds']
        effective['max_retry_delay_seconds'] = DEFAULT_RETRY_SETTINGS['max_retry_delay_seconds']
    return effective
