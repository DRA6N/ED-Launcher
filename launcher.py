import tkinter as tk
from tkinter import filedialog, simpledialog, messagebox, Menu, ttk
import os
import subprocess
import json
import webbrowser
from PIL import Image, ImageTk
import urllib.request
import io
import win32gui
import win32ui
import win32con
import psutil
import pystray
from pystray import MenuItem as TrayMenuItem
import threading
import time
import requests
import random

CONFIG_FILE = "data.edl"
ICON_SIZE = (48, 48)
OVERLAY_ICON_PATH = "images/launch_overlay.png"
APP_BG = "#2c0f07"
APP_BORDER = "#fe9020"
WEB_BORDER = "#00ff00"
HIGHLIGHT_BORDER = "#ffcc00"
BORDER_WIDTH = 3
ICON_PATH = "images/icon.png"
ED_LAUNCHER_NAME = "EDLaunch.exe"
CURRENT_VERSION = "2.0.0"

def check_for_updates():
    try:
        response = requests.get("https://api.github.com/repos/DRA6N/ED-Launcher/releases/latest", timeout=5)
        if response.status_code == 200:
            latest_version = response.json().get("tag_name", "").lstrip("v")
            if latest_version and latest_version != CURRENT_VERSION:
                if messagebox.askokcancel("Update Available", "A new version is available.\nClick OK to open the download page."):
                    webbrowser.open("https://github.com/DRA6N/ED-Launcher/releases")
    except:
        pass

def extract_icon(path):
    try:
        large, small = win32gui.ExtractIconEx(path, 0)
        hicon = small[0] if small else large[0]
        hdc = win32ui.CreateDCFromHandle(win32gui.GetDC(0))
        hbmp = win32ui.CreateBitmap()
        hbmp.CreateCompatibleBitmap(hdc, ICON_SIZE[0], ICON_SIZE[1])
        hdc = hdc.CreateCompatibleDC()
        hdc.SelectObject(hbmp)
        win32gui.DrawIconEx(hdc.GetHandleOutput(), 0, 0, hicon, ICON_SIZE[0], ICON_SIZE[1], 0, None, win32con.DI_NORMAL)
        bmpinfo = hbmp.GetInfo()
        bmpstr = hbmp.GetBitmapBits(True)
        image = Image.frombuffer('RGB', (bmpinfo['bmWidth'], bmpinfo['bmHeight']), bmpstr, 'raw', 'BGRX', 0, 1)
        return image
    except:
        return Image.new("RGB", ICON_SIZE, color="gray")

def overlay_launch_icon(base_image):
    try:
        overlay = Image.open(OVERLAY_ICON_PATH).resize((16, 16))
        base_image.paste(overlay, (ICON_SIZE[0] - 18, 2), overlay)
    except:
        pass
    return base_image

def fetch_favicon(url):
    domain = url.split("//")[-1].split("/")[0]
    favicon_url = f"https://www.google.com/s2/favicons?domain={domain}&sz=64"
    try:
        with urllib.request.urlopen(favicon_url) as response:
            icon_data = response.read()
            image = Image.open(io.BytesIO(icon_data)).resize(ICON_SIZE)
            return image
    except:
        try:
            return Image.open("images/Coriolis.png").resize(ICON_SIZE)
        except:
            return Image.new("RGB", ICON_SIZE, color="gray")

def monitor_edlauncher(app):
    seen = False
    while True:
        found = any(proc.name().lower() == ED_LAUNCHER_NAME.lower() for proc in psutil.process_iter(['name']))
        if found and not seen:
            seen = True
            for item in app.data.get("apps", []):
                if item.get("launch_with_ed"):
                    try:
                        path = item.get("path")
                        if path.lower().endswith(".bat"):
                            subprocess.Popen(["cmd.exe", "/c", path])
                        else:
                            subprocess.Popen(path)
                    except Exception as e:
                        print(f"Failed to auto-launch app: {e}")
        elif not found:
            seen = False
        time.sleep(5)

class LauncherTab:
    def __init__(self, parent, type_, data_key, border_color, extract_func, launch_func):
        self.parent = parent
        self.type_ = type_
        self.data_key = data_key
        self.border_color = border_color
        self.extract_icon = extract_func
        self.launch_action = launch_func
        self.items = []
        self.icons = []
        self.rearrange_mode = False
        self.drag_data = {"index": None}
        self.original_order = []

        tab_name = "\U0001F4BE Apps" if type_ == "apps" else "\U0001F310 Websites"

        self.frame = tk.Frame(parent.notebook, bg=APP_BG)
        parent.notebook.add(self.frame, text=tab_name)
        self.grid = tk.Frame(self.frame, bg=APP_BG)
        self.grid.pack(fill=tk.BOTH, expand=True)

    def load(self):
        self.items = self.parent.data.get(self.data_key, [])
        self.refresh()

    def save(self):
        self.parent.data[self.data_key] = self.items
        self.parent.save_config()

    def add_item(self):
        if self.type_ == "apps":
            path = filedialog.askopenfilename(filetypes=[("Executable & Batch files", "*.exe *.bat")])
            if path:
                self.items.append({"path": path, "launch_with_ed": False})
        elif self.type_ == "websites":
            url = simpledialog.askstring("Add Website", "Enter website URL:")
            if url:
                self.items.append({"url": url})
        self.save()
        self.refresh()

    def refresh(self):
        for widget in self.grid.winfo_children():
            widget.destroy()
        self.icons.clear()

        for i, item in enumerate(self.items):
            name = item.get("custom_name")
            if not name:
                key = "path" if self.type_ == "apps" else "url"
                name = os.path.splitext(os.path.basename(item[key]))[0] if self.type_ == "apps" else item[key].split("//")[-1].split("/")[0]

            icon_img = self.extract_icon(item.get("path") if self.type_ == "apps" else item.get("url"))

            if self.type_ == "apps" and item.get("launch_with_ed"):
                path = item.get("path", "").lower()
                if not path.endswith("edlaunch.exe"):
                    icon_img = overlay_launch_icon(icon_img)

            icon = ImageTk.PhotoImage(icon_img)
            self.icons.append(icon)

            border = HIGHLIGHT_BORDER if self.rearrange_mode else self.border_color
            container = tk.Frame(self.grid, bg=border, padx=2, pady=2)
            cols = self.parent.grid_columns.get()
            container.grid(row=i // cols, column=i % cols, padx=10, pady=10)

            label = tk.Label(container, image=icon, text=name, compound='top', bg=APP_BG, fg="white", bd=0)
            label._item_index = i
            label.pack()

            if not self.rearrange_mode:
                label.bind("<Button-1>", lambda e, key=item.get("path") or item.get("url"): self.launch_action(key))
                label.bind("<Button-3>", lambda e, idx=i: self.show_context_menu(e, idx))
            else:
                label.bind("<ButtonPress-1>", lambda e, idx=i: self.on_drag_start(e, idx))
                label.bind("<B1-Motion>", self.on_drag_motion)


    def on_drag_start(self, event, idx):
        self.drag_data["index"] = idx
        self.drag_data["widget"] = event.widget

    def on_drag_motion(self, event):
        widget = event.widget.winfo_containing(event.x_root, event.y_root)
        if widget and hasattr(widget, "_item_index"):
            target_idx = widget._item_index
            original_idx = self.drag_data["index"]
            if target_idx != original_idx:
                self.items.insert(target_idx, self.items.pop(original_idx))
                self.drag_data["index"] = target_idx
                self.refresh()

    def show_context_menu(self, event, index):
        menu = Menu(self.parent.root, tearoff=0)
        

        if self.type_ == "apps":
            path = self.items[index].get("path", "").lower()
            if not path.endswith("edlaunch.exe"):
                var = tk.BooleanVar(value=self.items[index].get("launch_with_ed", False))
                def toggle():
                    self.items[index]["launch_with_ed"] = var.get()
                    self.save()
                    self.refresh()
                menu.add_checkbutton(label="Launch with Elite Dangerous", onvalue=True, offvalue=False,
                                    variable=var, command=toggle)
        menu.add_command(label="Rename", command=lambda: self.rename_item(index))
        menu.add_command(label="Remove", command=lambda: self.remove_item(index))

        menu.tk_popup(event.x_root, event.y_root)

    def rename_item(self, index):
        current = self.items[index].get("custom_name") or ""
        new_name = simpledialog.askstring("Rename", "Enter new name:", initialvalue=current)
        if new_name:
            self.items[index]["custom_name"] = new_name
            self.save()
            self.refresh()

    def remove_item(self, index):
        if messagebox.askyesno("Confirm Delete", "Are you sure you want to delete this item?"):
            del self.items[index]
            self.save()
            self.refresh()

    def enter_rearrange_mode(self):
        self.rearrange_mode = True
        self.original_order = self.items.copy()
        self.refresh()

    def cancel_rearrange(self):
        self.rearrange_mode = False
        self.items = self.original_order.copy()
        self.refresh()

    def save_rearranged(self):
        self.rearrange_mode = False
        self.save()
        self.refresh()


class AppLauncher:
    def __init__(self, root):
        self.root = root
        self.root.title("Elite:Dangerous Launcher")
        self.root.configure(bg=APP_BORDER)  # Set to border color
        self.root.geometry("500x400")
        self.root.protocol("WM_DELETE_WINDOW", self.exit_app)
        self.keep_on_top_var = tk.BooleanVar(value=False)
        self.data = {}

        try:
            ctypes.windll.shell32.SetCurrentProcessExplicitAppUserModelID(u"elite.dangerous.launcher")
            self.root.iconbitmap("images/icon.ico")  # Ensure it's a real .ico file
            self.root.iconphoto(True, tk.PhotoImage(file=ICON_PATH))  # Use .png for the UI icon
            self.tray_image = Image.open(ICON_PATH).resize((64, 64))
        except Exception as e:
            print(f"Icon error: {e}")
            self.tray_image = Image.new("RGB", (64, 64), "gray")


        # Create a border frame with 3px padding
        self.border_frame = tk.Frame(self.root, bg=APP_BORDER, padx=3, pady=3)
        self.border_frame.pack(fill=tk.BOTH, expand=True)

        # Inner content frame
        self.inner_frame = tk.Frame(self.border_frame, bg=APP_BG)
        self.inner_frame.pack(fill=tk.BOTH, expand=True)

        # Use a grid layout
        self.inner_frame.grid_rowconfigure(0, weight=1)
        self.inner_frame.grid_columnconfigure(0, weight=1)

        # Notebook using grid
        self.notebook = ttk.Notebook(self.inner_frame)
        self.notebook.grid(row=0, column=0, sticky="nsew")

        # Add and Save buttons using grid (with fixed height)
        self.add_button = tk.Button(self.inner_frame, text="Add", command=self.add_item, bg=APP_BORDER, fg="white", height=1)
        self.add_button.grid(row=1, column=0, sticky="ew")

        self.save_button = tk.Button(self.inner_frame, text="Save Positions", command=self.save_rearranged, bg=HIGHLIGHT_BORDER, height=2)
        self.save_button.grid(row=2, column=0, sticky="ew")
        self.save_button.grid_remove()  # Hidden by default

        # Tab Colors
        style = ttk.Style()
        style.theme_use("default")
        style.configure("TNotebook.Tab", background=APP_BORDER, foreground="white", padding=[10, 5])
        style.configure("TNotebook", background=APP_BORDER, borderwidth=0)
        style.map("TNotebook.Tab", background=[("selected", APP_BG)], foreground=[("selected", "white")])

        # Tabs
        self.grid_columns = tk.IntVar(value=5)
        self.apps_tab = LauncherTab(self, "apps", "apps", APP_BORDER, extract_icon, self.launch_app)
        self.web_tab = LauncherTab(self, "websites", "websites", WEB_BORDER, fetch_favicon, self.launch_website)

        # Menu
        self.menu_bar = Menu(self.root)
        options_menu = Menu(self.menu_bar, tearoff=0)
        options_menu.add_checkbutton(label="Keep on Top", variable=self.keep_on_top_var, command=self.toggle_on_top)
        options_menu.add_command(label="Rearrange Apps", command=lambda: self.toggle_rearrange(self.apps_tab))
        options_menu.add_command(label="Rearrange Websites", command=lambda: self.toggle_rearrange(self.web_tab))
        options_menu.add_command(label="Minimize to Tray", command=self.hide_to_tray)
        options_menu.add_command(label="Set Grid Size", command=self.prompt_grid_size)
        options_menu.add_separator()
        options_menu.add_command(label="Close", command=self.exit_app)
        self.menu_bar.add_cascade(label="Options", menu=options_menu)

        help_menu = Menu(self.menu_bar, tearoff=0)
        help_menu.add_command(label="How to Use", command=self.show_help)
        help_menu.add_separator()
        help_menu.add_command(label="About ED Launcher", command=self.show_about)
        self.menu_bar.add_cascade(label="Help", menu=help_menu)

        self.root.config(menu=self.menu_bar)

        # Load config and initialize
        self.load_config()
        self.root.bind("<Escape>", lambda e: self.cancel_rearrange())
        
        threading.Thread(target=monitor_edlauncher, args=(self,), daemon=True).start()

    def prompt_grid_size(self):
        size = simpledialog.askinteger("Grid Size", "Enter number of icons per row (e.g., 3–10):", minvalue=1, maxvalue=10)
        if size:
            self.grid_columns.set(size)
            self.apps_tab.refresh()
            self.web_tab.refresh()

    def exit_app(self, icon=None, item=None):
        if hasattr(self, 'tray_icon') and self.tray_icon:
            self.tray_icon.stop()
        self.save_config()
        self.apps_tab.refresh()
        self.root.quit()

    def show_help(self):
        help_text = (
            "Elite:Dangerous Launcher - How to Use\n"
            "──────────────────────────────\n\n"
            "📁  Adding:\n"
            "• Use the 'Add' button to add either apps or websites based on the selected tab.\n\n"
            "🖱️  Launching:\n"
            "• Click any icon to launch the app or open the website in your browser.\n\n"
            "🛠️  Managing:\n"
            "• Right-click an icon to Rename or Remove it.\n"
            "• Apps also have an option to 'Launch with Elite Dangerous'.\n"
            "  - This option automatically starts the app when ED is launched.\n"
            "  - A small 🚀 icon appears in the top-right of any app set to auto-launch.\n"
            "  - You cannot set the ED launcher itself to auto-launch.\n\n"
            "🔃  Rearranging:\n"
            "• Use the 'Options' menu to enter Rearranging Mode.\n"
            "• Drag icons to reorder them.\n"
            "• Click 'Save Positions' to confirm, or press ESC to cancel.\n\n"
            "⚙️  Options Menu:\n"
            "• Keep on Top – keeps the window above others.\n"
            "• Minimize to Tray – hides the app to the system tray.\n"
            "• Set Grid Size – change the number of icons per row.\n"
            "• Close – exits the launcher.\n\n"
            "💾  The launcher remembers your window position, size, layout, and all entries automatically.\n\n"
            "🆕  Apps marked for auto-launch will launch automatically when 'EDLaunch.exe' is detected running."
        )
        messagebox.showinfo("Help", help_text)


    def show_about(self):
        about_text = (
            "Elite:Dangerous Launcher\n"
            f"Version {CURRENT_VERSION}\n\n"
            "Created by CMDR Aeldwulf\n\n"
            "Join the Elite Dangerous Community:\n"
            "https://discord.gg/elite"
        )
        messagebox.showinfo("About", about_text)

    def add_item(self):
        current = self.notebook.index(self.notebook.select())
        tab = self.apps_tab if current == 0 else self.web_tab
        tab.add_item()

    def toggle_rearrange(self, tab):
        tab.enter_rearrange_mode()
        self.save_button.grid()

    def cancel_rearrange(self):
        self.apps_tab.cancel_rearrange()
        self.web_tab.cancel_rearrange()
        self.save_button.pack_forget()

    def save_rearranged(self):
        self.apps_tab.save_rearranged()
        self.web_tab.save_rearranged()
        self.save_button.grid_remove()


    def toggle_on_top(self):
        self.root.attributes('-topmost', self.keep_on_top_var.get())

    def launch_app(self, path):
        try:
            if path.lower().endswith(".bat"):
                subprocess.Popen(["cmd.exe", "/c", path])
            else:
                subprocess.Popen(path)
        except Exception as e:
            messagebox.showerror("Error", f"Failed to launch app:\n{e}")

    def launch_website(self, url):
        try:
            webbrowser.open(url)
        except Exception as e:
            messagebox.showerror("Error", f"Failed to open website:\n{e}")

    def load_config(self):
        if os.path.exists(CONFIG_FILE):
            with open(CONFIG_FILE, "r") as f:
                self.data = json.load(f)
                grid_size = self.data.get("grid_columns", 5)
                self.grid_columns = tk.IntVar(value=grid_size)

                self.apps_tab.load()
                self.web_tab.load()

                # ✅ Apply geometry BEFORE showing window
                pos = self.data.get("window_position")
                if pos:
                    x = pos.get("x", 100)
                    y = pos.get("y", 100)
                    w = pos.get("width", 500)
                    h = pos.get("height", 400)
                    self.root.geometry(f"{w}x{h}+{x}+{y}")
        else:
            self.apps_tab.load()
            self.web_tab.load()

    def save_config(self):
        self.data["grid_columns"] = self.grid_columns.get()
        x = self.root.winfo_x()
        y = self.root.winfo_y()
        w = self.root.winfo_width()
        h = self.root.winfo_height()
        self.data["window_position"] = {"x": x, "y": y, "width": w, "height": h}
        with open(CONFIG_FILE, "w") as f:
            json.dump(self.data, f, indent=4)

    def hide_to_tray(self):
        self.save_config()
        self.apps_tab.refresh()
        self.root.withdraw()
        menu = (TrayMenuItem("Show", self.show_window), TrayMenuItem("Exit", self.exit_app))
        self.tray_icon = pystray.Icon("launcher", self.tray_image, "Elite:Dangerous Launcher", menu)
        threading.Thread(target=self.tray_icon.run, daemon=True).start()

    def show_window(self, icon=None, item=None):
        self.root.deiconify()
        if self.tray_icon:
            self.tray_icon.stop()

    def exit_app(self, icon=None, item=None):
        if hasattr(self, 'tray_icon') and self.tray_icon:
            self.tray_icon.stop()
        self.save_config()
        self.apps_tab.refresh()
        self.root.quit()

    
import ctypes
from ctypes import windll

def make_window_rounded(hwnd, width, height, radius=30):
    region = windll.gdi32.CreateRoundRectRgn(
        0, 0, width, height, radius, radius
    )
    windll.user32.SetWindowRgn(hwnd, region, True)

def show_splash(app_data):
    splash = tk.Toplevel()
    splash.overrideredirect(True)
    splash.configure(bg="#fe9020")
    splash.geometry("500x500")

    # Center the splash on screen
    splash.update_idletasks()
    screen_width = splash.winfo_screenwidth()
    screen_height = splash.winfo_screenheight()
    x = (screen_width - 500) // 2
    y = (screen_height - 500) // 2
    splash.geometry(f"500x500+{x}+{y}")

    splash.update_idletasks()
    hwnd = ctypes.windll.user32.GetParent(splash.winfo_id())
    make_window_rounded(hwnd, 500, 500, radius=30)

    try:
        img = Image.open(ICON_PATH).convert("RGBA").resize((300, 300))

        # Create an orange background
        bg = Image.new("RGBA", img.size, "#fe9020")
        img = Image.alpha_composite(bg, img).convert("RGB")

    except:
        img = Image.new("RGB", (400, 400), "#fe9020")

    icon = ImageTk.PhotoImage(img)

    label_icon = tk.Label(splash, image=icon, bg="#fe9020", bd=0, highlightthickness=0)
    label_icon.image = icon
    label_icon.pack(pady=(30, 10))

    label_title = tk.Label(splash, text="Elite:Dangerous Launcher", fg="black", bg="#fe9020", font=("Segoe UI", 18, "bold"))
    label_title.pack()

    label_version = tk.Label(splash, text=f"Version {CURRENT_VERSION}", fg="black", bg="#fe9020", font=("Segoe UI", 12))
    label_version.pack(pady=(5, 0))

    slogans = app_data.get("slogans", [])
    if slogans:
        random_slogan = random.choice(slogans)
        label_slogan = tk.Label(splash, text=random_slogan, fg="black", bg="#fe9020", font=("Segoe UI", 10, "italic"))
        label_slogan.pack(pady=(10, 0))

    return splash


if __name__ == "__main__":
    # Load config early to access slogans for splash
    data = {}
    if os.path.exists(CONFIG_FILE):
        with open(CONFIG_FILE, "r") as f:
            data = json.load(f)

    root = tk.Tk()
    splash = show_splash(data)
    root.withdraw()

    def start_app():
        splash.destroy()
        AppLauncher(root)
        root.deiconify()
        check_for_updates()

    root.after(5000, start_app) #5 seconds before loading into app
    root.mainloop()