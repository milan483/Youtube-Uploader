import tkinter as tk
from tkinter import ttk
import threading
import time
import sys
import os
from datetime import datetime

import config
from notification_manager import NotificationManager
from dialog_manager import DialogManager
from window_manager import WindowManager
from system_tray_manager import SystemTrayManager
from windows_integration import WindowsIntegration
from linux_integration import LinuxIntegration
from gui_components import TooltipHelper
from controllers.watch_controller import WatchController
from services.uploaded_clips_manager import UploadedClipsManager
from uploaded_clips_dialog import UploadedClipsDialog
from retry_settings_dialog import RetrySettingsDialog


class YouTubeUploaderGUI:
    """Main GUI application for YouTube Uploader."""
    
    def __init__(self, auth_manager, file_handler, state_manager, upload_manager):
        self.auth_manager = auth_manager
        self.file_handler = file_handler
        self.state_manager = state_manager
        self.upload_manager = upload_manager

        self.file_handler.set_logger(self.log)
        self.upload_manager.set_logger(self.log)
        self.watch_controller = None

        self.root = tk.Tk()
        self.root.title(f"{config.APP_NAME} v{config.APP_VERSION}")
        self.root.geometry(f"{config.GUI_WINDOW_WIDTH}x{config.GUI_WINDOW_HEIGHT}")

        self._set_window_icon()

        self.notification_manager = NotificationManager(log_callback=self.log)
        self.dialog_manager = DialogManager()
        self.uploaded_clips_manager = UploadedClipsManager(self.file_handler)
        self.startup_preference_key = (
            'start_on_login' if sys.platform.startswith('linux') else 'start_with_windows'
        )
        integration = LinuxIntegration if sys.platform.startswith('linux') else WindowsIntegration
        self.windows_integration = integration(log_callback=self.log)

        self.system_tray_manager = SystemTrayManager(
            on_show_callback=self._on_show_window,
            on_quit_callback=self._on_quit_app,
            log_callback=self.log
        )

        self.window_manager = WindowManager(
            root=self.root,
            tray_manager=self.system_tray_manager,
            log_callback=self.log
        )

        self.root.protocol("WM_DELETE_WINDOW", self.window_manager.minimize_to_tray)

        self._setup_gui_components()

        self.watch_controller = WatchController(
            upload_manager=self.upload_manager,
            auth_manager=self.auth_manager,
            batch_uploader=self.upload_manager.batch_uploader,
            logger=self.log,
            callbacks=self._build_watch_callbacks()
        )

        self.system_tray_manager.setup()
        self.windows_integration.setup_shutdown_handler()

        self._check_incomplete_uploads()
        self._populate_playlist_dropdown()
        self._load_preferences()
        self._apply_automation_preferences()
    
    def _set_window_icon(self):
        """Sets the window icon if available."""
        try:
            icon_path = config.ICON_PATH
            if os.path.exists(icon_path):
                # Load icon as PhotoImage for tkinter
                icon_image = tk.PhotoImage(file=icon_path)
                self.root.iconphoto(True, icon_image)
                # Keep a reference to prevent garbage collection
                self.root.icon_image = icon_image
                self.log(f"Loaded window icon from {icon_path}")
            else:
                self.log(f"Icon file not found at {icon_path}, using default")
        except Exception as e:
            self.log(f"Could not load window icon: {str(e)}")

    def _setup_gui_components(self):
        """Creates all GUI widgets and layouts."""
        create_tooltip = TooltipHelper.create_tooltip

        folder_frame = ttk.Frame(self.root)
        folder_frame.pack(fill=tk.X, padx=5, pady=5)

        folder_label = ttk.Label(folder_frame, text="Watch Folder:")
        folder_label.pack(side=tk.LEFT)
        create_tooltip(folder_label, "The folder to monitor for new videos to upload")

        self.folder_path_var = tk.StringVar()
        folder_entry = ttk.Entry(
            folder_frame,
            textvariable=self.folder_path_var
        )
        folder_entry.pack(side=tk.LEFT, fill=tk.X, expand=True, padx=5)
        create_tooltip(folder_entry, "Path to the folder being monitored\nNew videos added here will be uploaded automatically")

        browse_button = ttk.Button(
            folder_frame,
            text="Browse",
            command=self._on_browse_folder
        )
        browse_button.pack(side=tk.LEFT)
        create_tooltip(browse_button, "Click to select a folder to watch for new videos")

        privacy_frame = ttk.Frame(self.root)
        privacy_frame.pack(fill=tk.X, padx=5, pady=5)

        privacy_label = ttk.Label(privacy_frame, text="Privacy Setting:")
        privacy_label.pack(side=tk.LEFT)
        create_tooltip(privacy_label, "Who can see your uploaded videos")

        self.privacy_var = tk.StringVar(value=config.DEFAULT_PRIVACY_SETTING)
        self.privacy_combo = ttk.Combobox(
            privacy_frame,
            textvariable=self.privacy_var,
            values=config.PRIVACY_SETTINGS,
            state="readonly",
            width=15
        )
        self.privacy_combo.pack(side=tk.LEFT, padx=5)
        create_tooltip(
            self.privacy_combo,
            "Private: Only you can see\n"
            "Unlisted: Anyone with the link can see\n"
            "Public: Anyone can find and watch"
        )

        # Bind to update upload_manager when changed
        self.privacy_combo.bind('<<ComboboxSelected>>', self._on_privacy_changed)

        # ===================
        # Playlist Frame
        # ===================
        playlist_frame = ttk.Frame(self.root)
        playlist_frame.pack(fill=tk.X, padx=5, pady=5)

        playlist_label = ttk.Label(playlist_frame, text="Playlist:")
        playlist_label.pack(side=tk.LEFT)
        create_tooltip(playlist_label, "Automatically add uploaded videos to this playlist")

        self.playlist_var = tk.StringVar(value="No Playlist")
        self.playlist_combo = ttk.Combobox(
            playlist_frame,
            textvariable=self.playlist_var,
            values=["No Playlist"],  # Will be populated after auth
            state="readonly",
            width=25
        )
        self.playlist_combo.pack(side=tk.LEFT, padx=5)
        create_tooltip(
            self.playlist_combo,
            "Select a playlist to automatically add videos after upload\n"
            "Choose 'No Playlist' to skip playlist addition"
        )

        # Bind to update upload_manager when changed
        self.playlist_combo.bind('<<ComboboxSelected>>', self._on_playlist_changed)

        self.sort_playlist_button = ttk.Button(
            playlist_frame,
            text="Sort Playlist",
            command=self._on_sort_playlist
        )
        self.sort_playlist_button.pack(side=tk.LEFT, padx=5)
        create_tooltip(
            self.sort_playlist_button,
            "Sort the selected playlist alphabetically by video title\n"
            "Useful for date-based filenames (e.g., 2025-01-15_clip.mp4)\n"
            "Note: Uses YouTube API quota"
        )

        category_frame = ttk.Frame(self.root)
        category_frame.pack(fill=tk.X, padx=5, pady=5)

        category_label = ttk.Label(category_frame, text="Video Category:")
        category_label.pack(side=tk.LEFT)
        create_tooltip(category_label, "YouTube category for uploaded videos")

        self.category_var = tk.StringVar(value=config.DEFAULT_VIDEO_CATEGORY)
        self.category_combo = ttk.Combobox(
            category_frame,
            textvariable=self.category_var,
            values=list(config.VIDEO_CATEGORIES.keys()),
            state="readonly",
            width=20
        )
        self.category_combo.pack(side=tk.LEFT, padx=5)
        create_tooltip(
            self.category_combo,
            "Choose the YouTube category that best fits your videos\n"
            "This helps YouTube recommend your videos to the right audience"
        )

        # Bind to update upload_manager when changed
        self.category_combo.bind('<<ComboboxSelected>>', self._on_category_changed)

        # =====================================
        # Automation Settings (Collapsible)
        # =====================================
        automation_frame = ttk.LabelFrame(self.root, text="⚙ Automation Settings")
        automation_frame.pack(fill=tk.X, padx=5, pady=5)
        create_tooltip(automation_frame, "Configure automatic behavior and Windows integration")

        self.autonomous_mode_var = tk.BooleanVar(value=config.DEFAULT_AUTONOMOUS_MODE)
        self.autonomous_mode_var = tk.BooleanVar(value=config.DEFAULT_AUTONOMOUS_MODE)
        autonomous_check = ttk.Checkbutton(
            automation_frame,
            text="Autonomous Mode (set and forget)",
            variable=self.autonomous_mode_var,
            command=self._on_autonomous_mode_changed
        )
        autonomous_check.grid(row=0, column=0, sticky=tk.W, padx=5, pady=2)
        create_tooltip(
            autonomous_check,
            "Enable fully autonomous operation:\n"
            "- Auto-start watching on app launch\n"
            "- Start minimized to tray\n"
            "- No manual intervention required"
        )

        # Auto-start watching checkbox
        self.auto_start_watching_var = tk.BooleanVar(value=config.DEFAULT_AUTO_START_WATCHING)
        auto_start_check = ttk.Checkbutton(
            automation_frame,
            text="Auto-start watching on launch",
            variable=self.auto_start_watching_var,
            command=self._on_auto_start_watching_changed
        )
        auto_start_check.grid(row=1, column=0, sticky=tk.W, padx=5, pady=2)
        create_tooltip(
            auto_start_check,
            "Automatically begin monitoring the watch folder when app starts\n"
            "No need to click 'Start Watching' button manually"
        )

        # Start minimized checkbox
        self.start_minimized_var = tk.BooleanVar(value=config.DEFAULT_START_MINIMIZED)
        start_minimized_check = ttk.Checkbutton(
            automation_frame,
            text="Start minimized to tray",
            variable=self.start_minimized_var,
            command=self._on_start_minimized_changed
        )
        start_minimized_check.grid(row=2, column=0, sticky=tk.W, padx=5, pady=2)
        create_tooltip(
            start_minimized_check,
            "Start the app minimized to system tray instead of showing window\n"
            "Useful for running silently in the background"
        )

        self.scan_subdirectories_var = tk.BooleanVar(value=False)
        scan_subdirectories_check = ttk.Checkbutton(
            automation_frame,
            text="Scan subdirectories",
            variable=self.scan_subdirectories_var,
            command=self._on_scan_subdirectories_changed
        )
        scan_subdirectories_check.grid(row=3, column=0, sticky=tk.W, padx=5, pady=2)
        create_tooltip(
            scan_subdirectories_check,
            "Also scan folders inside the watch folder for videos"
        )

        self.delete_after_upload_var = tk.BooleanVar(value=config.DEFAULT_DELETE_AFTER_UPLOAD)
        delete_after_upload_check = ttk.Checkbutton(
            automation_frame,
            text="Delete local videos after successful upload (move to Trash)",
            variable=self.delete_after_upload_var,
            command=self._on_delete_after_upload_changed
        )
        delete_after_upload_check.grid(row=4, column=0, columnspan=2, sticky=tk.W, padx=5, pady=2)
        create_tooltip(
            delete_after_upload_check,
            "Move successfully uploaded local videos to the OS Trash/Recycle Bin "
            "instead of the Uploaded archive. Restore them from Trash before it is emptied."
        )

        # Notify when empty checkbox
        self.notify_when_empty_var = tk.BooleanVar(value=config.DEFAULT_NOTIFY_WHEN_EMPTY)
        notify_empty_check = ttk.Checkbutton(
            automation_frame,
            text="Notify when folder is empty",
            variable=self.notify_when_empty_var,
            command=self._on_notify_when_empty_changed
        )
        notify_empty_check.grid(row=0, column=1, sticky=tk.W, padx=5, pady=2)
        create_tooltip(
            notify_empty_check,
            "Show Windows notification when all videos have been uploaded\n"
            "Lets you know when you can add more videos"
        )

        # Start with Windows checkbox
        self.start_with_windows_var = tk.BooleanVar(value=False)
        start_with_windows_check = ttk.Checkbutton(
            automation_frame,
            text="Start on login" if sys.platform.startswith('linux') else "Start with Windows",
            variable=self.start_with_windows_var,
            command=self._on_start_with_windows_changed
        )
        start_with_windows_check.grid(row=1, column=1, sticky=tk.W, padx=5, pady=2)
        create_tooltip(
            start_with_windows_check,
            "Launch YouTube Uploader when you log into your desktop session"
            if sys.platform.startswith('linux') else
            "Add YouTube Uploader to the Windows startup folder"
        )

        if not self.windows_integration.is_startup_available():
            start_with_windows_check.config(state=tk.DISABLED)
            create_tooltip(
                start_with_windows_check,
                "Startup integration is unavailable on this platform"
            )

        retry_settings_button = ttk.Button(
            automation_frame, text='Retry Settings...', command=self._on_retry_settings
        )
        retry_settings_button.grid(row=2, column=1, sticky=tk.W, padx=5, pady=2)

        toast_label = ttk.Label(automation_frame, text="📢 Toast Notifications:", font=("Arial", 9, "bold"))
        toast_label.grid(row=0, column=2, sticky=tk.W, padx=(15, 5), pady=(2, 0))
        create_tooltip(toast_label, "Configure which events trigger Windows notifications")

        # Notify upload success
        self.notify_upload_success_var = tk.BooleanVar(value=config.DEFAULT_NOTIFY_UPLOAD_SUCCESS)
        notify_success_check = ttk.Checkbutton(
            automation_frame,
            text="Upload succeeded",
            variable=self.notify_upload_success_var,
            command=self._on_notify_upload_success_changed
        )
        notify_success_check.grid(row=1, column=2, sticky=tk.W, padx=(15, 5), pady=2)
        create_tooltip(
            notify_success_check,
            "Show notification when a video uploads successfully\n"
            "Good for monitoring progress when minimized"
        )

        # Notify upload failed
        self.notify_upload_failed_var = tk.BooleanVar(value=config.DEFAULT_NOTIFY_UPLOAD_FAILED)
        notify_failed_check = ttk.Checkbutton(
            automation_frame,
            text="Upload failed",
            variable=self.notify_upload_failed_var,
            command=self._on_notify_upload_failed_changed
        )
        notify_failed_check.grid(row=2, column=2, sticky=tk.W, padx=(15, 5), pady=2)
        create_tooltip(
            notify_failed_check,
            "Show notification when a video upload fails\n"
            "Alerts you to errors that need attention"
        )

        # Notify quota exceeded
        self.notify_quota_exceeded_var = tk.BooleanVar(value=config.DEFAULT_NOTIFY_QUOTA_EXCEEDED)
        notify_quota_check = ttk.Checkbutton(
            automation_frame,
            text="Quota exceeded",
            variable=self.notify_quota_exceeded_var,
            command=self._on_notify_quota_exceeded_changed
        )
        notify_quota_check.grid(row=3, column=2, sticky=tk.W, padx=(15, 5), pady=2)
        create_tooltip(
            notify_quota_check,
            "Show notification when YouTube API quota is exceeded\n"
            "Lets you know uploads will resume in 24 hours"
        )

        # Notify batch complete
        self.notify_batch_complete_var = tk.BooleanVar(value=config.DEFAULT_NOTIFY_BATCH_COMPLETE)
        notify_batch_check = ttk.Checkbutton(
            automation_frame,
            text="Batch complete",
            variable=self.notify_batch_complete_var,
            command=self._on_notify_batch_complete_changed
        )
        notify_batch_check.grid(row=4, column=2, sticky=tk.W, padx=(15, 5), pady=2)
        create_tooltip(
            notify_batch_check,
            "Show notification when all videos in batch are uploaded\n"
            "Useful for knowing when a large batch finishes"
        )

        # Disable toast checkboxes if win11toast not available
        if not self.notification_manager.is_available():
            for checkbox in [notify_success_check, notify_failed_check, notify_quota_check, notify_batch_check]:
                checkbox.config(state=tk.DISABLED        )

        next_check_frame = ttk.Frame(self.root)
        next_check_frame.pack(fill=tk.X, padx=5, pady=5)

        self.next_check_var = tk.StringVar(value="Next check: Not scheduled")
        next_check_label = ttk.Label(
            next_check_frame,
            textvariable=self.next_check_var
        )
        next_check_label.pack(side=tk.LEFT)
        create_tooltip(next_check_label, "When the app will next check the watch folder for new videos"        )

        progress_frame = ttk.Frame(self.root)
        progress_frame.pack(fill=tk.X, padx=5, pady=5)

        self.progress_var = tk.DoubleVar()
        self.progress_bar = ttk.Progressbar(
            progress_frame,
            variable=self.progress_var,
            maximum=100
        )
        self.progress_bar.pack(fill=tk.X)
        create_tooltip(self.progress_bar, "Upload progress for current video or batch"        )

        button_frame = ttk.Frame(self.root)
        button_frame.pack(fill=tk.X, padx=5, pady=5)

        self.start_button = ttk.Button(
            button_frame,
            text="Start Watching",
            command=self._on_start_watching
        )
        self.start_button.pack(side=tk.LEFT, padx=2)
        create_tooltip(
            self.start_button,
            "Begin monitoring the watch folder for new videos\n"
            "App will automatically upload any videos found"
        )

        self.stop_button = ttk.Button(
            button_frame,
            text="Stop",
            command=self._on_stop_watching,
            state=tk.DISABLED
        )
        self.stop_button.pack(side=tk.LEFT, padx=2)
        create_tooltip(
            self.stop_button,
            "Stop monitoring the watch folder\n"
            "Current upload will finish before stopping"
        )

        self.force_check_button = ttk.Button(
            button_frame,
            text="Force Check Now",
            command=self._on_force_check,
            state=tk.DISABLED
        )
        self.force_check_button.pack(side=tk.LEFT, padx=2)
        create_tooltip(
            self.force_check_button,
            "Immediately check the watch folder for new videos\n"
            "Bypasses the normal polling interval"
        )

        self.upload_file_button = ttk.Button(
            button_frame,
            text="Upload File...",
            command=self._on_upload_single_file
        )
        self.upload_file_button.pack(side=tk.LEFT, padx=2)
        create_tooltip(
            self.upload_file_button,
            "Upload a single video file without watching a folder\n"
            "Useful for one-off uploads"
        )

        self.manage_uploaded_button = ttk.Button(
            button_frame, text="Uploaded Clips...",
            command=self._on_manage_uploaded_clips
        )
        self.manage_uploaded_button.pack(side=tk.LEFT, padx=2)
        create_tooltip(
            self.manage_uploaded_button,
            "Browse and recycle local archived copies, without deleting YouTube videos"
        )

        # Add some spacing before Exit button
        ttk.Frame(button_frame, width=20).pack(side=tk.LEFT)

        self.exit_button = ttk.Button(
            button_frame,
            text="Exit",
            command=self._on_exit_button
        )
        self.exit_button.pack(side=tk.RIGHT, padx=2)
        create_tooltip(
            self.exit_button,
            "Exit the application completely\n"
            "All uploads will stop and app will close"
        )

        # ===================
        # Log Frame
        # ===================
        log_frame = ttk.Frame(self.root)
        log_frame.pack(fill=tk.BOTH, expand=True, padx=5, pady=5)

        # Create scrollbar
        scrollbar = ttk.Scrollbar(log_frame)
        scrollbar.pack(side=tk.RIGHT, fill=tk.Y)

        # Create text widget
        self.log_text = tk.Text(
            log_frame,
            height=config.GUI_LOG_HEIGHT,
            yscrollcommand=scrollbar.set
        )
        self.log_text.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        create_tooltip(self.log_text, "Activity log showing all app operations and status messages")

        scrollbar.config(command=self.log_text.yview)

        # ===================
        # Status Bar
        # ===================
        self.status_var = tk.StringVar(value="Ready")
        self.status_bar = ttk.Label(
            self.root,
            textvariable=self.status_var,
            relief=tk.SUNKEN
        )
        self.status_bar.pack(fill=tk.X, side=tk.BOTTOM)
        create_tooltip(self.status_bar, "Current app status")

        # Initial log message
        self.log("YouTube Uploader initialized successfully")
        self.log(f"Version: {config.APP_VERSION}")
    
    def _populate_playlist_dropdown(self):
        playlist_titles = self.auth_manager.get_playlist_titles()
        self.playlist_combo.configure(values=playlist_titles)
        self.playlist_var.set("No Playlist")

    def _load_preferences(self):
        prefs = self.state_manager.get_all_preferences()

        # Apply UI preferences
        if prefs.get('last_watch_folder'):
            self.folder_path_var.set(prefs['last_watch_folder'])

        if prefs.get('privacy_setting'):
            self.privacy_var.set(prefs['privacy_setting'])
            self.upload_manager.set_privacy(prefs['privacy_setting'])

        if prefs.get('playlist_title'):
            self.playlist_var.set(prefs['playlist_title'])
            playlist_id = self.auth_manager.get_playlist_id(prefs['playlist_title'])
            self.upload_manager.set_playlist(playlist_id)

        if prefs.get('video_category'):
            self.category_var.set(prefs['video_category'])
            self.upload_manager.set_category(prefs['video_category'])

        # Apply automation preferences
        self.autonomous_mode_var.set(prefs.get('autonomous_mode', config.DEFAULT_AUTONOMOUS_MODE))
        self.auto_start_watching_var.set(prefs.get('auto_start_watching', config.DEFAULT_AUTO_START_WATCHING))
        self.start_minimized_var.set(prefs.get('start_minimized', config.DEFAULT_START_MINIMIZED))
        scan_subdirectories = prefs.get('scan_subdirectories', False)
        self.scan_subdirectories_var.set(scan_subdirectories)
        self.watch_controller.set_scan_subdirectories(scan_subdirectories)
        self.delete_after_upload_var.set(
            prefs.get('delete_after_upload', config.DEFAULT_DELETE_AFTER_UPLOAD)
        )
        self.notify_when_empty_var.set(prefs.get('notify_when_empty', config.DEFAULT_NOTIFY_WHEN_EMPTY))
        self.start_with_windows_var.set(prefs.get(self.startup_preference_key, False))

        # Apply toast notification preferences
        self.notify_upload_success_var.set(prefs.get('notify_upload_success', config.DEFAULT_NOTIFY_UPLOAD_SUCCESS))
        self.notify_upload_failed_var.set(prefs.get('notify_upload_failed', config.DEFAULT_NOTIFY_UPLOAD_FAILED))
        self.notify_quota_exceeded_var.set(prefs.get('notify_quota_exceeded', config.DEFAULT_NOTIFY_QUOTA_EXCEEDED))
        self.notify_batch_complete_var.set(prefs.get('notify_batch_complete', config.DEFAULT_NOTIFY_BATCH_COMPLETE))

        self.log("User preferences loaded successfully")

    def _save_preference(self, key, value):
        try:
            self.state_manager.set_preference(key, value)
        except Exception as e:
            self.log(f"Warning: Could not save preference '{key}': {str(e)}")

    def _apply_automation_preferences(self):
        if self.autonomous_mode_var.get():
            self.auto_start_watching_var.set(True)
            self.start_minimized_var.set(True)

        # Auto-start watching if enabled
        if self.auto_start_watching_var.get():
            # Need to wait for GUI to be fully rendered
            self.root.after(100, self._auto_start_watching)

        # Minimize to tray if enabled
        if self.start_minimized_var.get():
            self.root.after(200, self.window_manager.minimize_to_tray)

    def _auto_start_watching(self):
        if self.folder_path_var.get():
            self.log("Auto-starting folder watch (automation preference)")
            self._on_start_watching()
        else:
            self.log("Auto-start disabled: No watch folder configured")

    def _on_autonomous_mode_changed(self):
        autonomous = self.autonomous_mode_var.get()
        self._save_preference('autonomous_mode', autonomous)

        if autonomous:
            # Enable dependent settings
            self.auto_start_watching_var.set(True)
            self.start_minimized_var.set(True)
            self._save_preference('auto_start_watching', True)
            self._save_preference('start_minimized', True)
            self.log("Autonomous mode enabled (auto-start + minimized startup)")
        else:
            self.log("Autonomous mode disabled")

    def _on_auto_start_watching_changed(self):
        auto_start = self.auto_start_watching_var.get()
        self._save_preference('auto_start_watching', auto_start)
        if auto_start:
            self.log("Auto-start watching enabled")
        else:
            self.log("Auto-start watching disabled")
            if self.autonomous_mode_var.get():
                self.autonomous_mode_var.set(False)
                self._save_preference('autonomous_mode', False)

    def _on_start_minimized_changed(self):
        start_minimized = self.start_minimized_var.get()
        self._save_preference('start_minimized', start_minimized)
        if start_minimized:
            self.log("Start minimized enabled")
        else:
            self.log("Start minimized disabled")
            if self.autonomous_mode_var.get():
                self.autonomous_mode_var.set(False)
                self._save_preference('autonomous_mode', False)

    def _on_notify_when_empty_changed(self):
        notify = self.notify_when_empty_var.get()
        self._save_preference('notify_when_empty', notify)

        if notify:
            if self.notification_manager.is_available():
                self.log("Empty folder notifications enabled")
            else:
                self.log("Notifications enabled (but win11toast library not available)")
                self.dialog_manager.show_warning(
                    "Feature Unavailable",
                    "Windows notifications require the 'win11toast' package.\n\n"
                    "Install with: pip install win11toast"
                )
        else:
            self.log("Empty folder notifications disabled")

    def _on_scan_subdirectories_changed(self):
        scan_subdirectories = bool(self.scan_subdirectories_var.get())
        self.watch_controller.set_scan_subdirectories(scan_subdirectories)
        self._save_preference('scan_subdirectories', scan_subdirectories)
        self.log(f"Subdirectory scanning {'enabled' if scan_subdirectories else 'disabled'}")

    def _on_delete_after_upload_changed(self):
        self._save_preference('delete_after_upload', self.delete_after_upload_var.get())

    def _on_start_with_windows_changed(self):
        """Configure Windows Startup or Linux XDG autostart."""
        requested = bool(self.start_with_windows_var.get())
        if not self.windows_integration.is_startup_available():
            self.dialog_manager.show_error(
                "Feature Unavailable", "System startup integration is unavailable."
            )
            self.start_with_windows_var.set(False)
            return

        try:
            if requested:
                self.windows_integration.add_to_startup()
                self.log("Enabled launch on desktop login")
            else:
                self.windows_integration.remove_from_startup()
                self.log("Disabled launch on desktop login")
            self._save_preference(self.startup_preference_key, requested)
        except Exception as error:
            self.log(f"Error configuring startup: {error}")
            self.dialog_manager.show_error(
                "Startup Configuration Failed", f"Could not configure startup:\n\n{error}"
            )
            self.start_with_windows_var.set(not requested)

    def _on_retry_settings(self):
        RetrySettingsDialog(
            self.root, self.state_manager,
            on_saved=lambda _settings: self.log('Retry settings updated')
        )

    def _on_notify_upload_success_changed(self):
        notify = self.notify_upload_success_var.get()
        self._save_preference('notify_upload_success', notify)
        self.log(f"Upload success notifications {'enabled' if notify else 'disabled'}")

    def _on_notify_upload_failed_changed(self):
        notify = self.notify_upload_failed_var.get()
        self._save_preference('notify_upload_failed', notify)
        self.log(f"Upload failed notifications {'enabled' if notify else 'disabled'}")

    def _on_notify_quota_exceeded_changed(self):
        notify = self.notify_quota_exceeded_var.get()
        self._save_preference('notify_quota_exceeded', notify)
        self.log(f"Quota exceeded notifications {'enabled' if notify else 'disabled'}")

    def _on_notify_batch_complete_changed(self):
        notify = self.notify_batch_complete_var.get()
        self._save_preference('notify_batch_complete', notify)
        self.log(f"Batch complete notifications {'enabled' if notify else 'disabled'}")

    def _check_incomplete_uploads(self):
        incomplete_count = self.state_manager.reset_incomplete_uploads_to_pending()
        
        if incomplete_count > 0:
            self.log(f"Found {incomplete_count} incomplete upload(s) from previous session")
            self.log("These will be retried when you start watching")
    
    def _ui_call(self, func, *args, **kwargs):
        try:
            self.root.after(0, lambda: func(*args, **kwargs))
        except Exception as e:
            # If root is destroyed or not ready, ignore UI update
            try:
                if self.root.winfo_exists():
                    print(f"UI update failed: {e}", file=sys.stderr)
            except Exception:
                pass

    def log(self, message):
        timestamp = datetime.now().strftime(config.LOG_TIMESTAMP_FORMAT)
        log_line = f"{timestamp}: {message}\n"
        
        # Schedule GUI update on main thread
        self.root.after(0, self._append_to_log, log_line)
    
    def _append_to_log(self, text):
        try:
            self.log_text.insert(tk.END, text)
            self.log_text.see(tk.END)  # Auto-scroll to bottom
        except Exception as e:
            # If GUI is being destroyed, this might fail - ignore
            print(f"Error appending to log: {e}", file=sys.stderr)
    
    def _on_privacy_changed(self, event=None):
        privacy = self.privacy_var.get()
        self.upload_manager.set_privacy(privacy)
        self._save_preference('privacy_setting', privacy)
        self.log(f"Privacy setting changed to: {privacy}")

    def _on_playlist_changed(self, event=None):
        playlist_title = self.playlist_var.get()
        playlist_id = self.auth_manager.get_playlist_id(playlist_title)

        self.upload_manager.set_playlist(playlist_id)
        self._save_preference('playlist_title', playlist_title)

        if playlist_id:
            self.log(f"Playlist changed to: {playlist_title}")
        else:
            self.log("Playlist changed to: No Playlist")

    def _on_category_changed(self, event=None):
        category = self.category_var.get()
        self.upload_manager.set_category(category)
        self._save_preference('video_category', category)
        self.log(f"Video category changed to: {category}")

    def _on_sort_playlist(self):
        playlist_title = self.playlist_var.get()
        playlist_id = self.auth_manager.get_playlist_id(playlist_title)

        # Validate a playlist is selected
        if not playlist_id:
            self.dialog_manager.show_warning(
                "No Playlist Selected",
                "Please select a playlist to sort.\n\n"
                "(The 'No Playlist' option cannot be sorted)"
            )
            return

        # Get playlist size to estimate quota cost
        self.log(f"Checking playlist size...")
        item_count = self.upload_manager.get_playlist_item_count(playlist_id)

        if item_count == 0:
            self.dialog_manager.show_warning(
                "Empty Playlist",
                "This playlist appears to be empty or could not be accessed.\n\n"
                "Cannot sort an empty playlist."
            )
            return

        # Calculate estimated quota cost
        estimated_cost = self.upload_manager.estimate_sort_quota_cost(item_count)

        # Build confirmation message with quota warning
        confirm_message = (
            f"Sort playlist '{playlist_title}' alphabetically?\n\n"
            f"Playlist contains: {item_count:,} video(s)\n"
            f"Estimated quota cost: {estimated_cost:,} units\n"
            f"Daily quota limit: {config.DEFAULT_DAILY_QUOTA_LIMIT:,} units\n\n"
        )

        if estimated_cost > config.DEFAULT_DAILY_QUOTA_LIMIT:
            confirm_message += (
                "⚠️ WARNING: Estimated cost EXCEEDS daily quota limit!\n\n"
                f"This operation will likely run out of quota after sorting\n"
                f"approximately {config.DEFAULT_DAILY_QUOTA_LIMIT // config.QUOTA_COST_PLAYLIST_UPDATE:,} videos.\n\n"
                "You can run this operation again after 24 hours to continue\n"
                "sorting from where it left off.\n\n"
                "Continue anyway?"
            )
        else:
            confirm_message += (
                "This will reorder all videos in the playlist by title.\n"
                "For date-based filenames, this sorts chronologically.\n\n"
                "Continue?"
            )

        # Confirm with user
        confirm = self.dialog_manager.ask_yes_no(
            "Confirm Playlist Sort",
            confirm_message
        )

        if not confirm:
            self.log("Playlist sort cancelled by user")
            return

        # Disable button during sort
        self.sort_playlist_button.config(state=tk.DISABLED)
        self.log(f"Starting sort for playlist: {playlist_title}")

        # Run sort in background thread to avoid freezing GUI
        def sort_thread():
            try:
                # Progress callback to update GUI
                def progress(current, total, message):
                    self._ui_call(self.status_var.set, f"Sorting: {current}/{total}")
                    if total > 0:
                        percent = (current / total) * 100
                        self._ui_call(self.progress_var.set, percent)
                    self.log(message)

                # Perform the sort
                success, message, count = self.upload_manager.sort_playlist_alphabetically(
                    playlist_id,
                    progress_callback=progress
                )

                # Reset progress
                self._ui_call(self.progress_var.set, 0)

                # Re-enable button
                self._ui_call(self.sort_playlist_button.config, state=tk.NORMAL)

                # Show result to user
                if success:
                    self._ui_call(self.status_var.set, "Playlist sorted successfully")
                    self._ui_call(
                        self.dialog_manager.show_info,
                        "Sort Complete",
                        f"{message}\n\n"
                        f"Playlist '{playlist_title}' has been sorted alphabetically."
                    )
                else:
                    self._ui_call(self.status_var.set, "Playlist sort failed")
                    self._ui_call(
                        self.dialog_manager.show_error,
                        "Sort Failed",
                        f"Failed to sort playlist:\n\n{message}"
                    )

            except Exception as e:
                self.log(f"Error during playlist sort: {str(e)}")
                self._ui_call(self.sort_playlist_button.config, state=tk.NORMAL)
                self._ui_call(self.status_var.set, "Sort error")
                self._ui_call(
                    self.dialog_manager.show_error,
                    "Sort Error",
                    f"An error occurred during sorting:\n\n{str(e)}"
                )

        # Start the sort thread
        thread = threading.Thread(target=sort_thread, daemon=True)
        thread.start()
    
    def _on_manage_uploaded_clips(self):
        folder = self.folder_path_var.get().strip()
        if not folder or not os.path.isdir(folder):
            self.dialog_manager.show_warning(
                "Choose a watch folder",
                "Select an existing watch folder before managing its Uploaded archive."
            )
            return
        UploadedClipsDialog(
            self.root,
            self.uploaded_clips_manager,
            folder,
            self.dialog_manager,
            logger=self.log,
        )

    def _on_browse_folder(self):
        folder = self.dialog_manager.ask_directory(title="Select Watch Folder")
        if folder:
            self.folder_path_var.set(folder)
            self._save_preference('last_watch_folder', folder)
            self.log(f"Watch folder selected: {folder}")

    def _on_upload_single_file(self):
        filepath = self.dialog_manager.ask_video_file(title="Select Video to Upload")

        if not filepath:
            # User cancelled
            return

        self.log(f"Single file upload selected: {os.path.basename(filepath)}")

        # Disable upload button during upload
        self.upload_file_button.config(state=tk.DISABLED)

        # Run upload in background thread to avoid freezing GUI
        def upload_thread():
            try:
                # Update status
                self._ui_call(self.status_var.set, f"Uploading: {os.path.basename(filepath)}")

                # Create progress callback that updates the progress bar
                def upload_progress_callback(percent):
                    self._ui_call(self.progress_var.set, percent)

                # Perform upload
                success, message, video_id = self.upload_manager.upload_video(
                    filepath,
                    progress_callback=upload_progress_callback
                )

                # Reset progress
                self._ui_call(self.progress_var.set, 0)

                # Re-enable button
                self._ui_call(self.upload_file_button.config, state=tk.NORMAL)

                # Show result to user
                if success:
                    self._ui_call(self.status_var.set, "Upload complete")
                    self.log(message)

                    # Notify upload success if enabled
                    if self.notify_upload_success_var.get():
                        self.notification_manager.show_notification(
                            "Upload Succeeded",
                            f"Successfully uploaded: {os.path.basename(filepath)}",
                            duration=3
                        )

                    self._ui_call(
                        self.dialog_manager.show_info,
                        "Upload Successful",
                        f"{message}\n\n"
                        f"File: {os.path.basename(filepath)}\n"
                        f"Video ID: {video_id}"
                    )
                else:
                    self._ui_call(self.status_var.set, "Upload failed")
                    self.log(f"Upload failed: {message}")

                    # Notify upload failed if enabled
                    if self.notify_upload_failed_var.get():
                        self.notification_manager.show_notification(
                            "Upload Failed",
                            f"Failed to upload {os.path.basename(filepath)}: {message}",
                            duration=5
                        )

                    self._ui_call(
                        self.dialog_manager.show_error,
                        "Upload Failed",
                        f"Failed to upload video:\n\n{message}"
                    )

            except Exception as e:
                self.log(f"Error during single file upload: {str(e)}")
                self._ui_call(self.upload_file_button.config, state=tk.NORMAL)
                self._ui_call(self.status_var.set, "Upload error")

                # Check if it was a quota error
                if "QuotaExceededError" in str(type(e)) or "quotaExceeded" in str(e):
                    # Notify quota exceeded if enabled
                    if self.notify_quota_exceeded_var.get():
                        self.notification_manager.show_notification(
                            "Quota Exceeded",
                            "YouTube API quota exceeded. Try again in 24 hours.",
                            duration=8
                        )
                else:
                    # Notify upload failed if enabled
                    if self.notify_upload_failed_var.get():
                        self.notification_manager.show_notification(
                            "Upload Error",
                            f"Error uploading {os.path.basename(filepath)}: {str(e)}",
                            duration=5
                        )

                self.dialog_manager.show_error(
                    "Upload Error",
                    f"An error occurred during upload:\n\n{str(e)}"
                )

        # Start the upload thread
        thread = threading.Thread(target=upload_thread, daemon=True)
        thread.start()
    
    def _on_start_watching(self):
        if not self.folder_path_var.get():
            self.dialog_manager.show_error("Error", config.ERROR_NO_WATCH_FOLDER)
            return

        self.start_button.config(state=tk.DISABLED)
        self.stop_button.config(state=tk.NORMAL)
        self.force_check_button.config(state=tk.NORMAL)

        self.watch_controller.start(self.folder_path_var.get())

        self.log("Started watching folder for new videos")
        self.status_var.set("Watching folder...")

    def _on_stop_watching(self):
        """Stops the worker thread."""
        self.watch_controller.stop()

        self.start_button.config(state=tk.NORMAL)
        self.stop_button.config(state=tk.DISABLED)
        self.force_check_button.config(state=tk.DISABLED)

        self.log("Stopped watching folder")
        self.status_var.set("Stopped")

    def _on_exit_button(self):
        if self.watch_controller and self.watch_controller.is_running():
            confirm = self.dialog_manager.ask_yes_no(
                "Confirm Exit",
                "Folder watching is active.\n\n"
                "Are you sure you want to exit?\n"
                "(Current upload will complete before exit)"
            )
            if not confirm:
                return

        self.log("Exiting application...")
        self._quit_application()
    
    def _on_force_check(self):
        self.log("Force check triggered by user")
        self.watch_controller.force_check()
    
    def _build_watch_callbacks(self):
        def set_progress(percent):
            self._ui_call(self.progress_var.set, percent)

        def set_status(message):
            self._ui_call(self.status_var.set, message)

        def set_next_check(message):
            self._ui_call(self.next_check_var.set, message)

        def notify_empty():
            # `auto_close_when_empty` is currently stored as a preference but
            # no runtime auto-close behavior is enforced yet.
            if self.notify_when_empty_var.get():
                self.notification_manager.show_notification(
                    "YouTube Uploader",
                    "No supported videos found in watch folder.",
                    duration=3
                )

        def notify_upload_success(filename):
            if self.notify_upload_success_var.get():
                self.notification_manager.show_notification(
                    "Upload Succeeded",
                    f"Successfully uploaded: {filename}",
                    duration=3
                )

        def notify_upload_failed(filename, message):
            if self.notify_upload_failed_var.get():
                self.notification_manager.show_notification(
                    "Upload Failed",
                    f"Failed to upload {filename}: {message}",
                    duration=5
                )

        def notify_upload_error(filename, error_message):
            if self.notify_upload_failed_var.get():
                self.notification_manager.show_notification(
                    "Upload Error",
                    f"Error uploading {filename}: {error_message}",
                    duration=5
                )

        def notify_quota_exceeded():
            if self.notify_quota_exceeded_var.get():
                self.notification_manager.show_notification(
                    "Quota Exceeded",
                    "YouTube API quota exceeded. Uploads will resume in 24 hours.",
                    duration=8
                )

        def notify_batch_complete(summary):
            if self.notify_batch_complete_var.get():
                self.notification_manager.show_notification(
                    "Batch Complete",
                    summary,
                    duration=5
                )

        return {
            'set_progress': set_progress,
            'set_status': set_status,
            'set_next_check': set_next_check,
            'notify_empty': notify_empty,
            'notify_upload_success': notify_upload_success,
            'notify_upload_failed': notify_upload_failed,
            'notify_upload_error': notify_upload_error,
            'notify_quota_exceeded': notify_quota_exceeded,
            'notify_batch_complete': notify_batch_complete
        }
    
    def _on_show_window(self, icon=None):
        # Tray callbacks run outside Tk's main thread (pystray / GLib).
        self._ui_call(self.window_manager.restore_from_tray)
    
    def _quit_application(self):
        def do_quit():
            try:
                if self.watch_controller:
                    self.watch_controller.stop()
                self.system_tray_manager.stop()
                time.sleep(0.3)
                self.root.quit()
                self.root.destroy()
                sys.exit(0)
            except Exception as e:
                print(f"Error during quit: {str(e)}", file=sys.stderr)
                sys.exit(1)

        try:
            self.root.after(0, do_quit)
        except:
            sys.exit(0)

    def _on_quit_app(self, icon=None):
        self._quit_application()
    
    def run(self):
        try:
            self.root.mainloop()
        except Exception as e:
            self.log(f"Error in main loop: {str(e)}")
            raise
