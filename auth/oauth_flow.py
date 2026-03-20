from google_auth_oauthlib.flow import InstalledAppFlow


class OAuthFlowError(Exception):
    pass


def run_oauth_flow(client_secrets_file, scopes, logger=None):
    log = logger or (lambda message: None)

    try:
        log("Starting OAuth authorization flow...")
        flow = InstalledAppFlow.from_client_secrets_file(
            client_secrets_file,
            scopes
        )
        creds = flow.run_local_server(port=0)
        log("OAuth authorization successful")
        return creds

    except Exception as e:
        log(f"OAuth authorization failed: {str(e)}")
        raise OAuthFlowError(f"Authorization failed: {str(e)}")
