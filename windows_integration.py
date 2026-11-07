import sys
import os
import ctypes
import config

try:
    import winreg
except ImportError:
    winreg = None

try:
    import winshell
    from win32com.client import Dispatch
    WINDOWS_STARTUP_AVAILABLE = True
except ImportError:
    WINDOWS_STARTUP_AVAILABLE = False


class WindowsIntegration:
    def __init__(self, log_callback=None):
        self.log_callback = log_callback
        self.startup_available = WINDOWS_STARTUP_AVAILABLE

    def log(self, message):
        if self.log_callback:
            self.log_callback(message)

    def is_startup_available(self):
        return self.startup_available

    def setup_shutdown_handler(self):
        try:
            ctypes.windll.kernel32.SetProcessShutdownParameters(0x4FF, 0)
            self.log("Shutdown handler configured")
        except Exception as e:
            self.log(f"Warning: Could not set shutdown handler: {str(e)}")

    def add_to_startup(self):
        if not self.startup_available:
            raise RuntimeError("Windows startup integration not available")

        startup_folder = winshell.startup()
        shortcut_path = os.path.join(startup_folder, config.WINDOWS_STARTUP_SHORTCUT_NAME)

        script_dir = os.path.dirname(os.path.abspath(__file__))
        if getattr(sys, 'frozen', False):
            startup_target = sys.executable
            script_dir = os.path.dirname(startup_target)
        else:
            startup_target = os.path.join(script_dir, 'main.pyw')

        shell = Dispatch('WScript.Shell')
        shortcut = shell.CreateShortCut(shortcut_path)
        shortcut.TargetPath = startup_target
        shortcut.WorkingDirectory = script_dir
        shortcut.WindowStyle = 1
        shortcut.Description = f"{config.APP_NAME} - Automatic YouTube Uploader"
        shortcut.save()

        try:
            zone_identifier = shortcut_path + ':Zone.Identifier'
            if os.path.exists(zone_identifier):
                os.remove(zone_identifier)
        except Exception as e:
            self.log(f"Warning: Could not remove Zone.Identifier: {str(e)}")

        self._register_startup_approved(config.WINDOWS_STARTUP_SHORTCUT_NAME)

    def remove_from_startup(self):
        if not self.startup_available:
            raise RuntimeError("Windows startup integration not available")

        startup_folder = winshell.startup()
        shortcut_path = os.path.join(startup_folder, config.WINDOWS_STARTUP_SHORTCUT_NAME)

        if os.path.exists(shortcut_path):
            os.remove(shortcut_path)

        self._unregister_startup_approved(config.WINDOWS_STARTUP_SHORTCUT_NAME)

    def _register_startup_approved(self, shortcut_name):
        if not winreg:
            self.log("Warning: winreg not available")
            return

        try:
            key_path = r"Software\Microsoft\Windows\CurrentVersion\Explorer\StartupApproved\StartupFolder"
            key = winreg.CreateKey(winreg.HKEY_CURRENT_USER, key_path)
            enabled_value = bytes([0x02, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00])
            winreg.SetValueEx(key, shortcut_name, 0, winreg.REG_BINARY, enabled_value)
            winreg.CloseKey(key)
            self.log(f"Registered '{shortcut_name}' in StartupApproved registry")
        except Exception as e:
            self.log(f"Warning: Could not register StartupApproved: {str(e)}")

    def _unregister_startup_approved(self, shortcut_name):
        if not winreg:
            return

        try:
            key_path = r"Software\Microsoft\Windows\CurrentVersion\Explorer\StartupApproved\StartupFolder"
            key = winreg.OpenKey(winreg.HKEY_CURRENT_USER, key_path, 0, winreg.KEY_SET_VALUE)
            winreg.DeleteValue(key, shortcut_name)
            winreg.CloseKey(key)
            self.log(f"Unregistered '{shortcut_name}' from StartupApproved registry")
        except FileNotFoundError:
            pass
        except Exception as e:
            self.log(f"Warning: Could not unregister StartupApproved: {str(e)}")
