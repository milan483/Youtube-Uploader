from googleapiclient.discovery import build
import config


class YoutubeClientFactoryError(Exception):
    pass


def build_youtube_client(credentials):
    try:
        return build(
            config.YOUTUBE_API_SERVICE_NAME,
            config.YOUTUBE_API_VERSION,
            credentials=credentials
        )
    except Exception as e:
        raise YoutubeClientFactoryError(f"Failed to build YouTube client: {str(e)}")


def rebuild_youtube_client(credentials):
    try:
        return build(
            config.YOUTUBE_API_SERVICE_NAME,
            config.YOUTUBE_API_VERSION,
            credentials=credentials
        )
    except Exception as e:
        raise YoutubeClientFactoryError(f"Failed to rebuild YouTube client: {str(e)}")
