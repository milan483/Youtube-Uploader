"""Tkinter dialog for inspecting and recycling archived local clips."""
import os
import threading
import tkinter as tk
from tkinter import ttk

from utils.config_utils import format_file_size, get_uploaded_folder_path


class UploadedClipsDialog:
    def __init__(self, parent, manager, watch_root, dialog_manager, logger=None):
        self.manager = manager
        self.watch_root = os.path.abspath(watch_root)  # snapshot; never retarget live deletion
        self.dialogs = dialog_manager
        self.logger = logger
        self.busy = False

        self.window = tk.Toplevel(parent)
        self.window.title("Uploaded Clips — Local Archive")
        self.window.geometry("760x460")
        self.window.transient(parent)
        self.window.protocol("WM_DELETE_WINDOW", self.window.destroy)

        ttk.Label(
            self.window, text=f"Local archive: {get_uploaded_folder_path(self.watch_root)}",
            wraplength=730
        ).pack(fill=tk.X, padx=10, pady=(10, 4))
        ttk.Label(
            self.window,
            text="Deleting here sends local copies to the Recycle Bin/Trash. YouTube videos are not deleted.",
            wraplength=730
        ).pack(fill=tk.X, padx=10, pady=(0, 7))

        table_frame = ttk.Frame(self.window)
        table_frame.pack(fill=tk.BOTH, expand=True, padx=10)
        self.tree = ttk.Treeview(
            table_frame, columns=("path", "size"), show="headings", selectmode="extended"
        )
        self.tree.heading("path", text="Relative path")
        self.tree.heading("size", text="Size")
        self.tree.column("path", anchor=tk.W, width=580)
        self.tree.column("size", anchor=tk.E, width=130)
        scrollbar = ttk.Scrollbar(table_frame, orient=tk.VERTICAL, command=self.tree.yview)
        self.tree.configure(yscrollcommand=scrollbar.set)
        self.tree.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        scrollbar.pack(side=tk.RIGHT, fill=tk.Y)

        self.summary = tk.StringVar(value="Loading archived clips...")
        ttk.Label(self.window, textvariable=self.summary).pack(fill=tk.X, padx=10, pady=6)

        buttons = ttk.Frame(self.window)
        buttons.pack(fill=tk.X, padx=10, pady=(2, 10))
        self.refresh_button = ttk.Button(buttons, text="Refresh", command=self.refresh)
        self.refresh_button.pack(side=tk.LEFT, padx=(0, 4))
        self.select_button = ttk.Button(buttons, text="Select All", command=self.select_all)
        self.select_button.pack(side=tk.LEFT, padx=4)
        self.selected_button = ttk.Button(
            buttons, text="Delete Selected", command=self.delete_selected
        )
        self.selected_button.pack(side=tk.LEFT, padx=4)
        self.all_button = ttk.Button(buttons, text="Delete All", command=self.delete_all)
        self.all_button.pack(side=tk.LEFT, padx=4)
        ttk.Button(buttons, text="Close", command=self.window.destroy).pack(side=tk.RIGHT)
        self.refresh()

    def _on_ui(self, callback, *args):
        try:
            self.window.after(0, lambda: self._if_alive(callback, *args))
        except (RuntimeError, tk.TclError):
            pass

    def _if_alive(self, callback, *args):
        if self.window.winfo_exists():
            callback(*args)

    def _set_busy(self, busy):
        self.busy = busy
        state = tk.DISABLED if busy else tk.NORMAL
        for widget in (self.refresh_button, self.select_button,
                       self.selected_button, self.all_button):
            widget.configure(state=state)

    def refresh(self):
        if self.busy:
            return
        self._set_busy(True)
        self.summary.set("Scanning archived clips...")

        def run():
            try:
                clips = self.manager.list_clips(self.watch_root)
                self._on_ui(self._show_clips, clips, None)
            except Exception as error:
                self._on_ui(self._show_clips, [], str(error))

        threading.Thread(target=run, daemon=True).start()

    def _show_clips(self, clips, error):
        for item in self.tree.get_children():
            self.tree.delete(item)
        total = 0
        for clip in clips:
            total += clip.size_bytes
            self.tree.insert(
                "", tk.END, iid=clip.relative_path,
                values=(clip.relative_path, format_file_size(clip.size_bytes))
            )
        if error:
            self.summary.set(f"Archive unavailable: {error}")
        else:
            self.summary.set(f"{len(clips)} archived clip(s) — {format_file_size(total)}")
        self._set_busy(False)

    def select_all(self):
        self.tree.selection_set(self.tree.get_children())

    def delete_selected(self):
        self._confirm_delete(list(self.tree.selection()))

    def delete_all(self):
        self._confirm_delete(list(self.tree.get_children()))

    def _confirm_delete(self, names):
        if self.busy or not names:
            return
        # The dialog retains its original watch-root snapshot even if the
        # main window's selected folder changes in the meantime.
        count = len(names)
        archive_path = get_uploaded_folder_path(self.watch_root)
        if not self.dialogs.ask_yes_no(
            "Move local clips to Recycle Bin/Trash?",
            f"Move {count} local clip(s) from:\n{archive_path}\n\n"
            "This does not delete anything from YouTube. Continue?"
        ):
            return

        self._set_busy(True)
        self.summary.set(f"Moving {count} clip(s) to Trash...")

        def run():
            result = self.manager.delete_clips(self.watch_root, names)
            self._on_ui(self._show_delete_results, result)

        threading.Thread(target=run, daemon=True).start()

    def _show_delete_results(self, result):
        if self.logger:
            self.logger(
                f"Archive cleanup: {len(result.deleted)} recycled, {len(result.failed)} failed"
            )
        if result.failed:
            failures = "\n".join(
                f"{name}: {reason}" for name, reason in list(result.failed.items())[:12]
            )
            self.dialogs.show_warning(
                "Some clips were not moved",
                f"{len(result.deleted)} recycled, {len(result.failed)} failed.\n\n{failures}"
            )
        self._set_busy(False)
        self.refresh()
