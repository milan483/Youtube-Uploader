import os
import config


def get_uploaded_folder_path(watch_folder):
    return os.path.join(watch_folder, config.UPLOADED_FOLDER_NAME)


def is_supported_video_file(filename):
    return filename.lower().endswith(config.SUPPORTED_VIDEO_EXTENSIONS)


def format_file_size(size_bytes):
    if size_bytes < 1024:
        return f"{size_bytes} B"
    elif size_bytes < 1024 ** 2:
        return f"{size_bytes / 1024:.2f} KB"
    elif size_bytes < 1024 ** 3:
        return f"{size_bytes / (1024 ** 2):.2f} MB"
    else:
        return f"{size_bytes / (1024 ** 3):.2f} GB"
