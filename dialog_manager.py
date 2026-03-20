from tkinter import filedialog, messagebox


class DialogManager:
    @staticmethod
    def ask_directory(title="Select Folder"):
        folder = filedialog.askdirectory(title=title)
        return folder if folder else ""

    @staticmethod
    def ask_open_filename(title="Select File", filetypes=None):
        if filetypes is None:
            filetypes = [("All files", "*.*")]
        filepath = filedialog.askopenfilename(title=title, filetypes=filetypes)
        return filepath if filepath else ""

    @staticmethod
    def ask_video_file(title="Select Video to Upload"):
        from config import SUPPORTED_VIDEO_EXTENSIONS
        filetypes = [
            ("Video files", " ".join(f"*{ext}" for ext in SUPPORTED_VIDEO_EXTENSIONS)),
            ("All files", "*.*")
        ]
        return DialogManager.ask_open_filename(title=title, filetypes=filetypes)

    @staticmethod
    def show_info(title, message):
        messagebox.showinfo(title, message)

    @staticmethod
    def show_warning(title, message):
        messagebox.showwarning(title, message)

    @staticmethod
    def show_error(title, message):
        messagebox.showerror(title, message)

    @staticmethod
    def ask_yes_no(title, message):
        return messagebox.askyesno(title, message)
