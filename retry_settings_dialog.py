import tkinter as tk
from tkinter import messagebox, ttk

from utils.retry_settings import (
    DEFAULT_RETRY_SETTINGS,
    RETRY_FIELDS,
    validate_retry_settings,
)


class RetrySettingsDialog:
    """Modal editor for scheduled-upload retry preferences."""

    def __init__(self, parent, state_manager, on_saved=None):
        self.state_manager = state_manager
        self.on_saved = on_saved
        self.window = tk.Toplevel(parent)
        self.window.title('Retry Settings')
        self.window.resizable(False, False)
        self.window.transient(parent)
        self.window.protocol('WM_DELETE_WINDOW', self.window.destroy)

        content = ttk.Frame(self.window, padding=12)
        content.grid(row=0, column=0, sticky='nsew')
        current = state_manager.get_retry_settings()
        self.vars = {}
        labels = {
            'max_upload_retry_attempts': 'Maximum upload attempts',
            'initial_retry_delay_seconds': 'Initial retry delay (seconds)',
            'max_retry_delay_seconds': 'Maximum retry delay (seconds)',
        }
        for row, (key, minimum, maximum) in enumerate(RETRY_FIELDS):
            ttk.Label(content, text=f'{labels[key]} ({minimum}-{maximum})').grid(
                row=row, column=0, sticky='w', pady=3)
            value = tk.StringVar(value=str(current[key]))
            self.vars[key] = value
            ttk.Entry(content, textvariable=value, width=12).grid(
                row=row, column=1, sticky='ew', padx=(8, 0), pady=3)

        note = (
            'Attempts include the first upload. Changes apply to new attempts; '
            'existing scheduled retry times are unchanged. Short transport '
            'retries within one upload use a separate fixed delay.'
        )
        ttk.Label(content, text=note, wraplength=390, justify='left').grid(
            row=3, column=0, columnspan=2, sticky='w', pady=(8, 10))

        actions = ttk.Frame(content)
        actions.grid(row=4, column=0, columnspan=2, sticky='e')
        ttk.Button(actions, text='Restore Defaults', command=self._restore_defaults).pack(
            side='left', padx=(0, 8))
        ttk.Button(actions, text='Cancel', command=self.window.destroy).pack(
            side='left', padx=(0, 8))
        ttk.Button(actions, text='Save', command=self._save).pack(side='left')
        self.window.grab_set()
        self.window.focus_set()

    def _restore_defaults(self):
        for key, value in DEFAULT_RETRY_SETTINGS.items():
            self.vars[key].set(str(value))

    def _save(self):
        try:
            requested = {
                key: int(self.vars[key].get().strip())
                for key, _, _ in RETRY_FIELDS
            }
        except (ValueError, TypeError):
            messagebox.showerror(
                'Invalid Retry Settings', 'Enter a whole number for each setting.',
                parent=self.window,
            )
            return
        try:
            settings = validate_retry_settings(requested)
        except (ValueError, TypeError) as error:
            messagebox.showerror('Invalid Retry Settings', str(error), parent=self.window)
            return
        try:
            self.state_manager.set_retry_settings(settings)
        except Exception as error:
            messagebox.showerror('Could Not Save Retry Settings', str(error), parent=self.window)
            return
        if self.on_saved:
            self.on_saved(settings)
        self.window.destroy()
