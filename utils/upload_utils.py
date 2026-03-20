def is_skip_message(message):
    if not message:
        return False
    message_lower = message.lower()
    return "already uploaded" in message_lower or "retry scheduled" in message_lower


def is_retry_scheduled_message(message):
    if not message:
        return False
    return "retry scheduled" in message.lower()
