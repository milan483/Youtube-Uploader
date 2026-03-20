import os
import pickle
import time
import config
from utils.logging import LoggerMixin

try:
    import win32security
    import ntsecuritycon as con
    WINDOWS_SECURITY_AVAILABLE = True
except ImportError:
    WINDOWS_SECURITY_AVAILABLE = False


class TokenStoreError(Exception):
    pass


class TokenStore(LoggerMixin):
    def __init__(self, token_file=None, logger=None):
        self.token_file = token_file or config.TOKEN_FILE
        self.logger = logger

    def _secure_token_file(self, filepath):
        if not WINDOWS_SECURITY_AVAILABLE:
            self._log("Warning: Windows security modules not available")
            return

        try:
            user, domain, type = win32security.LookupAccountName("", os.getlogin())
            sd = win32security.SECURITY_DESCRIPTOR()
            dacl = win32security.ACL()
            dacl.AddAccessAllowedAce(
                win32security.ACL_REVISION,
                con.FILE_ALL_ACCESS,
                user
            )
            sd.SetSecurityDescriptorDacl(1, dacl, 0)
            win32security.SetFileSecurity(
                filepath,
                win32security.DACL_SECURITY_INFORMATION,
                sd
            )
            self._log(f"Set restrictive permissions on {filepath}")

        except Exception as e:
            self._log(f"Warning: Could not set restrictive permissions: {e}")

    def load_credentials(self):
        if not os.path.exists(self.token_file):
            self._log("No existing token file found")
            return None

        try:
            with open(self.token_file, 'rb') as token:
                creds = pickle.load(token)
            self._log("Loaded credentials from token.pickle")
            return creds

        except Exception as e:
            backup_name = f"token_corrupt_{int(time.time())}.pickle"
            self._log(f"Token file corrupted, backing up to {backup_name}")
            try:
                os.rename(self.token_file, backup_name)
            except Exception as rename_error:
                self._log(f"Could not backup corrupted token: {rename_error}")
            raise TokenStoreError(f"Token file corrupted: {str(e)}")

    def save_credentials(self, creds):
        try:
            with open(self.token_file, 'wb') as token:
                pickle.dump(creds, token)
            self._secure_token_file(self.token_file)
            self._log("Saved credentials to token.pickle")

        except Exception as e:
            self._log(f"Error saving credentials: {str(e)}")
            raise TokenStoreError(f"Failed to save credentials: {str(e)}")
