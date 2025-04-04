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
import pystray
from pystray import MenuItem as TrayMenuItem
import threading

CONFIG_FILE = "data.edl"
ICON_SIZE = (48, 48)
APP_BG = "#2c0f07"
APP_BORDER = "#fe9020"
WEB_BORDER = "#00ff00"
HIGHLIGHT_BORDER = "#ffcc00"
BORDER_WIDTH = 3
ICON_PATH = "images/icon.png"

CURRENT_VERSION = "1.3.0"

# Check for Updates
import requests

def check_for_updates():
    try:
        response = requests.get("RELEASE PAGE URL", timeout=5)
        if response.status_code == 200:
            latest_version = response.json().get("tag_name", "").lstrip("v")
            if latest_version and latest_version != CURRENT_VERSION:
                if messagebox.askokcancel("Update Available", "A new version is available.\nClick OK to open the download page."):
                    webbrowser.open("RELEASE PAGE URL")
    except Exception as e:
        # Optional: print or log error silently
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

class WideInputDialog(simpledialog._QueryString):
    def __init__(self, master, title, prompt, initial_value=""):
        self._initial_value = initial_value
        self._custom_title = title  # store the custom title explicitly
        super().__init__(master, title, prompt, initial_value)


    def body(self, master):
        self.wm_title(self._custom_title)  # use stored title
        self.entry = super().body(master)
        self.entry.config(width=60)
        self.after(0, self.center_over_parent)
        return self.entry

    def center_over_parent(self):
        try:
            parent_x = self.master.winfo_rootx()
            parent_y = self.master.winfo_rooty()
            parent_w = self.master.winfo_width()
            parent_h = self.master.winfo_height()

            self.update_idletasks()
            win_w = self.winfo_width()
            win_h = self.winfo_height()

            x = parent_x + (parent_w - win_w) // 2
            y = parent_y + (parent_h - win_h) // 2
            self.geometry(f"+{x}+{y}")
        except:
            pass  # fallback if master not available


def fetch_favicon(url):
    domain = url.split("//")[-1].split("/")[0]
    favicon_url = f"https://www.google.com/s2/favicons?domain={domain}&sz=64"
    try:
        with urllib.request.urlopen(favicon_url) as response:
            icon_data = response.read()
            image = Image.open(io.BytesIO(icon_data)).resize(ICON_SIZE)
            return image
    except:
        # If favicon fails, use local fallback
        try:
            return Image.open("images/Coriolis.png").resize(ICON_SIZE)
        except:
            return Image.new("RGB", ICON_SIZE, color="gray")


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

        tab_name = "💾 Apps" if type_ == "apps" else "🌐 Websites"

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
                self.items.append({"path": path})
        elif self.type_ == "websites":
            dialog = WideInputDialog(self.parent.root, "Add Website", "Enter website URL:")
            url = dialog.result

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

            icon_img = self.extract_icon(item["path"] if self.type_ == "apps" else item["url"])
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
        menu.add_command(label="Rename", command=lambda: self.rename_item(index))
        menu.add_command(label="Remove", command=lambda: self.remove_item(index))
        menu.tk_popup(event.x_root, event.y_root)

    def rename_item(self, index):
        current = self.items[index].get("custom_name") or ""
        item_type = "App" if self.type_ == "apps" else "Website"
        dialog = WideInputDialog(self.parent.root, f"Rename {item_type}", "Enter new name:", current)
        new_name = dialog.result

        if new_name:
            self.items[index]["custom_name"] = new_name
            self.save()
            self.refresh()

    def remove_item(self, index):
        item_type = "app" if self.type_ == "apps" else "site"
        name = self.items[index].get("custom_name") or self.items[index].get("path", "") or self.items[index].get("url", "")
        if messagebox.askyesno("Confirm Delete", f"Are you sure you want to delete this {item_type}?\n\n{name}"):
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
            self.root.iconphoto(True, tk.PhotoImage(file=ICON_PATH))
            self.tray_image = Image.open(ICON_PATH).resize((64, 64))
        except:
            self.tray_image = Image.new("RGB", (64, 64), "gray")

        # Create a border frame with 3px padding
        self.border_frame = tk.Frame(self.root, bg=APP_BORDER, padx=3, pady=3)
        self.border_frame.pack(fill=tk.BOTH, expand=True)

        # Inner content frame
        self.inner_frame = tk.Frame(self.border_frame, bg=APP_BG)
        self.inner_frame.pack(fill=tk.BOTH, expand=True)

        # Tab Colors
        style = ttk.Style()
        style.theme_use("default")  

        style.configure("TNotebook.Tab", # Sets websites tab (and apps tab) color when not selected
            background=APP_BORDER,      # Orange tab background
            foreground="white",         # Tab text color
            padding=[10, 5],            # Optional: makes tabs roomier
        )

        style.configure("TNotebook", background=APP_BORDER, borderwidth=0)
        style.configure("TNotebook.Tab", padding=[10, 5], background=APP_BORDER, foreground="white")
        style.map("TNotebook.Tab",
            background=[("selected", APP_BG)],
            foreground=[("selected", "white")]
        )

        style.map("TNotebook.Tab",
            background=[("selected", APP_BG)],
            foreground=[("selected", "white")]
        )

        self.notebook = ttk.Notebook(self.inner_frame)
        self.notebook.pack(fill=tk.BOTH, expand=True)

        self.grid_columns = tk.IntVar(value=5)  # default to 5 icons per row
        self.apps_tab = LauncherTab(self, "apps", "apps", APP_BORDER, extract_icon, self.launch_app)
        self.web_tab = LauncherTab(self, "websites", "websites", WEB_BORDER, fetch_favicon, self.launch_website)

        self.menu_bar = Menu(self.root)
        options_menu = Menu(self.menu_bar, tearoff=0)
        options_menu.add_checkbutton(label="Keep on Top", variable=self.keep_on_top_var, command=self.toggle_on_top)
        options_menu.add_command(label="Rearrange Apps", command=lambda: self.toggle_rearrange(self.apps_tab))
        options_menu.add_command(label="Rearrange Websites", command=lambda: self.toggle_rearrange(self.web_tab))
        options_menu.add_command(label="Minimize to Tray", command=self.hide_to_tray)
        def set_grid_size():
            size = simpledialog.askinteger("Grid Size", "Enter number of icons per row (e.g., 3–10):", minvalue=1, maxvalue=10)
            if size:
                self.grid_columns.set(size)
                self.apps_tab.refresh()
                self.web_tab.refresh()
        
        options_menu.add_command(label="Set Grid Size", command=set_grid_size)
        options_menu.add_separator()
        options_menu.add_command(label="Close", command=self.exit_app)
        self.menu_bar.add_cascade(label="Options", menu=options_menu)

        help_menu = Menu(self.menu_bar, tearoff=0)
        help_menu.add_command(label="How to Use", command=self.show_help)
        help_menu.add_separator()
        help_menu.add_command(label="About ED Launcher", command=self.show_about)
        self.menu_bar.add_cascade(label="Help", menu=help_menu)

        self.root.config(menu=self.menu_bar)

        self.add_button = tk.Button(self.inner_frame, text="Add", command=self.add_item, bg=APP_BORDER, fg="white")
        self.add_button.pack(fill=tk.X)

        self.save_button = tk.Button(self.inner_frame, text="Save Positions", command=self.save_rearranged, bg=HIGHLIGHT_BORDER)
        self.save_button.pack_forget()

        self.load_config()
        self.root.bind("<Escape>", lambda e: self.cancel_rearrange())

        check_for_updates()


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
            "• Right-click an icon to Rename or Remove it.\n\n"
            "🔃  Rearranging:\n"
            "• Use the 'Options' menu to enter Rearranging Mode.\n"
            "• Drag icons to reorder them.\n"
            "• Click 'Save Positions' to confirm, or press ESC to cancel.\n\n"
            "⚙️  Options Menu:\n"
            "• Keep on Top – keeps the window above others.\n"
            "• Minimize to Tray – hides the app to the system tray.\n"
            "• Close – exits the launcher.\n\n"
            "💾  The launcher remembers your window position, size, and all entries automatically."
        )
        messagebox.showinfo("Help", help_text)

    def show_about(self):
        about_text = ( # If you compile this on your own, please give credit where credit is due.
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
        self.save_button.pack(fill=tk.X)

    def cancel_rearrange(self):
        self.apps_tab.cancel_rearrange()
        self.web_tab.cancel_rearrange()
        self.save_button.pack_forget()

    def save_rearranged(self):
        self.apps_tab.save_rearranged()
        self.web_tab.save_rearranged()
        self.save_button.pack_forget()

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

                pos = self.data.get("window_position")
                if pos:
                    x = pos.get("x", 100)
                    y = pos.get("y", 100)
                    w = pos.get("width", 500)
                    h = pos.get("height", 400)
                    self.root.geometry(f"{w}x{h}+{x}+{y}")
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


if __name__ == "__main__":
    root = tk.Tk()
    app = AppLauncher(root)
    root.mainloop()