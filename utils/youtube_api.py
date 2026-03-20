def test_youtube_api_connection(youtube_client):
    if not youtube_client:
        return False
    try:
        request = youtube_client.channels().list(
            part="id",
            mine=True,
            maxResults=1
        )
        response = request.execute()
        return bool(response.get('items'))
    except Exception:
        return False
