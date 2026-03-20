import tkinter as tk


class TooltipHelper:
    @staticmethod
    def create_tooltip(widget, text):
        tooltip_window = None
        scheduled_show = None

        def on_enter(event):
            nonlocal tooltip_window, scheduled_show
            if scheduled_show is not None:
                widget.after_cancel(scheduled_show)
                scheduled_show = None

            if tooltip_window is not None:
                try:
                    tooltip_window.destroy()
                except:
                    pass
                tooltip_window = None

            def show_tooltip():
                nonlocal tooltip_window, scheduled_show
                scheduled_show = None
                if tooltip_window is None:
                    tooltip_window = tk.Toplevel()
                    tooltip_window.wm_overrideredirect(True)
                    tooltip_window.wm_geometry(f"+{event.x_root+10}+{event.y_root+10}")
                    label = tk.Label(
                        tooltip_window,
                        text=text,
                        background="#ffffe0",
                        relief=tk.SOLID,
                        borderwidth=1,
                        font=("Arial", 9),
                        padx=5,
                        pady=3
                    )
                    label.pack()

            scheduled_show = widget.after(300, show_tooltip)

        def on_leave(event):
            nonlocal tooltip_window, scheduled_show
            if scheduled_show is not None:
                widget.after_cancel(scheduled_show)
                scheduled_show = None

            if tooltip_window is not None:
                try:
                    tooltip_window.destroy()
                except:
                    pass
                tooltip_window = None

        widget.bind("<Enter>", on_enter)
        widget.bind("<Leave>", on_leave)
