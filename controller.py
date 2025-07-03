import base64
import datetime
import io
import json
import msvcrt
import os
import queue
import re
import socket
import sys
import threading
import time

import requests
import websocket
from PIL import Image
from pystray import Icon, MenuItem as item, Menu
import tkinter as tk
from tkinter.scrolledtext import ScrolledText


# Constants
VERSION = "1.5"
COMMAND_QUEUE = queue.Queue()
CONTROLLER_RUNNING = True

# ANSI color codes for terminal output
RED = '\033[31m'
GREEN = '\033[32m'
YELLOW = '\033[33m'
GREY = '\033[90m'
RESET = '\033[0m'

# Global variables for skip seconds and options
SKIP_SECONDS = 5
SKIP_OPTIONS = [5, 10, 30, 60]



### Helper Functions ###

# Function to get the absolute path to a resource, works for both development and PyInstaller bundle
def resource_path(relative_path):
    if hasattr(sys, '_MEIPASS'):
        return os.path.join(sys._MEIPASS, relative_path)
    return os.path.join(os.path.abspath(os.path.dirname(__file__)), relative_path)

# Load ICON_BASE64 from external file
with open(resource_path("icon_base64.txt"), "r") as f:
    ICON_BASE64 = f.read()

# Function to get the icon image for the system tray
def get_icon_image():
    icon_data = base64.b64decode(ICON_BASE64)
    return Image.open(io.BytesIO(icon_data))


# Single instance check (Windows only)
LOCKFILE = "controller.lock"
lockfile_handle = None
def check_single_instance():
    global lockfile_handle
    try:
        lockfile_handle = open(LOCKFILE, "w")
        msvcrt.locking(lockfile_handle.fileno(), msvcrt.LK_NBLCK, 1)
    except OSError:
        print_msg(f"{RED}ERROR: Another instance of YouTubeController is already running. Exiting...{RESET}", no_time_prefix=True)
        sys.exit(1)


# Set the default socket timeout to 5 seconds
socket.setdefaulttimeout(5)

# Function to check if the port is available
def check_port_available(port=65432):
    try:
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
            s.bind(("localhost", port))
    except OSError:
        print_msg(f"{RED}ERROR: Port {port} is already in use. Please check if no other program is using port {port}{RESET}", no_time_prefix=True)
        sys.exit(1)


# Global variables for buffering and log viewer
_last_printed = None
_last_count = 0
_screen_buffer = []
_log_viewer = None
_log_viewer_thread = None

def write_screen_buffer():
    # Only update log viewer if open
    if _log_viewer:
        _log_viewer.update_log(_screen_buffer)

# Helper to get current time as HH:MM:SS
def current_time_str():
    return datetime.datetime.now().strftime("%H:%M:%S")

# Function to print messages to the terminal with a timestamp and buffering
# If the message is the same as the last printed message, it will update the count
def print_msg(msg, no_time_prefix=False, space_before=False):
    global _last_printed, _last_count, _screen_buffer
    prefix = "\r\n" if space_before else ""
    if no_time_prefix:
        print(f"{prefix}{msg}", flush=True)
        _screen_buffer.append(f"{prefix}{msg}" if space_before else msg)
        write_screen_buffer()
        return
    time_prefix = f"[{current_time_str()}] "

    if CONTROLLER_RUNNING:
        if msg == _last_printed:
            _last_count += 1
            line = f"{GREY}{time_prefix}{RESET}{msg} {GREY}(x{_last_count}){RESET}"
            _screen_buffer[-1] = line
        else:
            _last_printed = msg
            _last_count = 1
            line = f"{prefix}{GREY}{time_prefix}{RESET}{msg}"
            _screen_buffer.append(line)

        # Print to terminal
        if _last_count > 1:
            print(f"{GREY}\033[F{_screen_buffer[-1]}", flush=True)
        else:
            print(f"{GREY}\r{_screen_buffer[-1]}", flush=True)
        write_screen_buffer()


# --- Tkinter Log Viewer ---
class LogViewer(tk.Tk):
    def __init__(self):
        super().__init__()
        self.title("YouTubeController Log Viewer")
        self.geometry("800x400")
        self.configure(bg="#23272e")
        self.protocol("WM_DELETE_WINDOW", self.hide)
        self.text = ScrolledText(self, state="disabled", font=("Consolas", 11),
        bg="#23272e", fg="#e6e6e6", insertbackground="#e6e6e6",
        selectbackground="#44475a", selectforeground="#f8f8f2",
        borderwidth=0, highlightthickness=0)
        self.text.pack(fill=tk.BOTH, expand=True)
        self._last_lines = []
        self._color_map = {
            '\033[31m': 'log_red',
            '\033[32m': 'log_green',
            '\033[33m': 'log_yellow',
            '\033[90m': 'log_grey',
            '\033[0m': 'log_fg',
        }
        self._setup_tags()
        self.after(1000, self._periodic_update)

    # Setup text tags for colored output
    def _setup_tags(self):
        self.text.tag_config('log_red', foreground='#ff5555')
        self.text.tag_config('log_green', foreground='#50fa7b')
        self.text.tag_config('log_yellow', foreground='#f1fa8c')
        self.text.tag_config('log_grey', foreground='#888888')
        self.text.tag_config('log_fg', foreground='#e6e6e6')

    # Update the log viewer with new lines
    def update_log(self, lines):
        if lines == self._last_lines:
            return
        self._last_lines = list(lines)
        self.text.config(state="normal")
        self.text.delete(1.0, tk.END)
        for line in lines:
            self._insert_colored_line(line)
        self.text.config(state="disabled")
        self.text.see(tk.END)

    # Insert a line with ANSI color codes
    def _insert_colored_line(self, line):
        ansi_re = re.compile(r'(\033\[\d+m)')
        parts = ansi_re.split(line)
        current_tag = 'log_fg'
        for part in parts:
            if part in self._color_map:
                current_tag = self._color_map[part]
            else:
                self.text.insert(tk.END, part, current_tag)
        self.text.insert(tk.END, '\n', current_tag)

    # Show the log viewer window
    def show(self):
        self.deiconify()
        self.lift()
        self.focus_force()

    # Hide the log viewer window
    def hide(self):
        self.withdraw()

    # Periodic update to check for new log lines
    def _periodic_update(self):
        if _screen_buffer != self._last_lines:
            self.update_log(_screen_buffer)
        self.after(1000, self._periodic_update)

# Function to start the log viewer in a separate thread
def start_log_viewer():
    global _log_viewer, _log_viewer_thread
    if _log_viewer:
        _log_viewer.show()
        return
    def run():
        global _log_viewer
        _log_viewer = LogViewer()
        _log_viewer.update_log(_screen_buffer)
        _log_viewer.mainloop()
        _log_viewer = None
    _log_viewer_thread = threading.Thread(target=run, daemon=True)
    _log_viewer_thread.start()

# Function to toggle the log viewer visibility
def toggle_log_viewer(icon, item):
    if _log_viewer and _log_viewer.state() != 'withdrawn':
        _log_viewer.hide()
    else:
        start_log_viewer()


# Wait for 'duration' seconds in 'interval' steps, exit early if CONTROLLER_RUNNING is False.
# This is useful to avoid blocking the main thread for too long.
def wait_or_exit(duration, interval=0.1):
    steps = int(duration / interval)
    for _ in range(steps):
        if not CONTROLLER_RUNNING:
            return False
        time.sleep(interval)
    return True


# Clear the terminal screen & print initial message
clear = lambda: os.system('cls' if os.name == 'nt' else 'clear')
clear()
print_msg(f"{GREEN}YouTubeControllerV{VERSION} is running... (Made by: https://github.com/MarB07){RESET}", no_time_prefix=True)
print_msg(f"{GREY}Press Ctrl+C, or right-click the tray icon and select 'Quit' to exit.\r\n{RESET}", no_time_prefix=True)



### Main Functions ###

# Function to find the YouTube WebSocket URL
def find_youtube_ws_url():
    print_msg("Fetching YouTube WebSocket URL...", no_time_prefix=True)
    start_time = time.time()
    TIMEOUT_SECONDS = 600  # 10 minutes

    while CONTROLLER_RUNNING:
        elapsed = time.time() - start_time
        if elapsed > TIMEOUT_SECONDS:
            print_msg(f"{RED}ERROR: No YouTube video tab found after 10 minutes. Exiting...{RESET}")
            on_quit(None, None) # Exit the application
            return None
        
        try:
            tabs = requests.get("http://localhost:9222/json").json()
            youtube_tabs = [tab for tab in tabs if "youtube.com" in tab.get("url", "")]
            if not youtube_tabs:
                print_msg(f"{YELLOW}WARNING: No YouTube tab found. Please open youtube.com in your browser.{RESET}")
                if not wait_or_exit(2): return None; continue

            video_tabs = [tab for tab in youtube_tabs if "/watch?v=" in tab.get("url", "")]
            if len(video_tabs) > 1:
                print_msg(f"{YELLOW}WARNING: Multiple YouTube video tabs detected!Please close all but one YouTube video tab.")
                if not wait_or_exit(5): return None; continue

            elif len(video_tabs) == 1:
                print_msg(f"Found YouTube video tab: {GREEN}{video_tabs[0]['url']}{RESET}", no_time_prefix=True, space_before=True)
                return video_tabs[0]["webSocketDebuggerUrl"]
            
            else:
                print_msg(f"{YELLOW}WARNING: No YouTube video detected. Please open a video in your YouTube tab...{RESET}", space_before=True)
                if not wait_or_exit(2): return None

        except Exception:
            print_msg(f"{RED}ERROR: Error fetching YouTube WebSocket URL. Is Chrome running with remote debugging?{RESET}", no_time_prefix=True)
            return None


def send_command_loop():
    try:
        while CONTROLLER_RUNNING:
            ws_url = find_youtube_ws_url()
            if not ws_url:
                print_msg(f"{YELLOW}WARNING: YouTube WebSocket URL not found. Retrying...{RESET}")
                if not wait_or_exit(1): return None; continue

            try:
                print_msg(f"Connecting to WebSocket: {GREEN}{ws_url}{RESET}", no_time_prefix=True, space_before=True)
                ws = websocket.create_connection(ws_url, timeout=5)
                print_msg(f"{GREEN}Connected to YouTube WebSocket{RESET}", no_time_prefix=True)
                
                print_msg(f"{GREY}Listening for commands...{RESET}", space_before=True)
                while CONTROLLER_RUNNING:
                    command = COMMAND_QUEUE.get()
                    if command == "exit":
                        ws.close()
                        return
                    expr = {
                        "skip_forward": f"document.querySelector('video').currentTime += {SKIP_SECONDS}",
                        "skip_backward": f"document.querySelector('video').currentTime -= {SKIP_SECONDS}",
                        "quality_up": """
                            (() => {
                                const menuBtn = document.querySelector('.ytp-settings-button');
                                if (!menuBtn) return;
                                menuBtn.click();
                                setTimeout(() => {
                                    const items = Array.from(document.querySelectorAll('.ytp-menuitem'));
                                    const qualityItem = items.find(i =>
                                        i.textContent.includes('Quality') || i.textContent.includes('Kwaliteit')
                                    );
                                    if (!qualityItem) { menuBtn.click(); return; }
                                    qualityItem.click();
                                    setTimeout(() => {
                                        const options = Array.from(document.querySelectorAll('.ytp-quality-menu .ytp-menuitem'));
                                        const selected = options.findIndex(o => o.getAttribute('aria-checked') === 'true');
                                        if (selected > 0) options[selected - 1].click();
                                        menuBtn.click();
                                    }, 100);
                                }, 100);
                            })()
                        """,
                        "quality_down": """
                            (() => {
                                const menuBtn = document.querySelector('.ytp-settings-button');
                                if (!menuBtn) return;
                                menuBtn.click();
                                setTimeout(() => {
                                    const items = Array.from(document.querySelectorAll('.ytp-menuitem'));
                                    const qualityItem = items.find(i =>
                                        i.textContent.includes('Quality') || i.textContent.includes('Kwaliteit')
                                    );
                                    if (!qualityItem) { menuBtn.click(); return; }
                                    qualityItem.click();
                                    setTimeout(() => {
                                        const options = Array.from(document.querySelectorAll('.ytp-quality-menu .ytp-menuitem'));
                                        const selected = options.findIndex(o => o.getAttribute('aria-checked') === 'true');
                                        if (selected < options.length - 1 && selected !== -1) options[selected + 1].click();
                                        menuBtn.click();
                                    }, 100);
                                }, 100);
                            })()
                        """,
                        "fix_video": """
                            (() => {
                                const video = document.querySelector('video');
                                if (video) video.volume = 1.0;

                                const d = new Date();
                                let ms = d.valueOf();
                                let oneYear = 365 * 24 * 60 * 60 * 1000;
                                try {
                                    localStorage.setItem('yt-player-volume', JSON.stringify({
                                        data: "{\\"volume\\":100,\\"muted\\":false}",
                                        expiration: ms + oneYear,
                                        creation: ms
                                    }));
                                } catch (e) {}
                            })()
                        """,
                        "cc": """
                            (() => {
                                const btn = document.querySelector('.ytp-subtitles-button');
                                if (btn) btn.click();
                            })()
                        """,
                        "fullscreen": """
                            (() => {
                                const btn = document.querySelector('.ytp-fullscreen-button');
                                if (btn) btn.click();
                            })()
                        """,
                        "theater": """
                            (() => {
                                const btn = document.querySelector('.ytp-size-button');
                                if (btn) btn.click();
                            })()
                        """,
                        "restart": "document.querySelector('video').currentTime = 0",
                        "next_chapter": """
                            (() => {
                                const video = document.querySelector('video');
                                if (!video) return;
                                const timeDivs = Array.from(document.querySelectorAll('#contents #endpoint #details div#time.style-scope.ytd-macro-markers-list-item-renderer'));
                                if (timeDivs.length === 0) return;
                                function parseTime(t) {
                                    return t.split(':').reduce((acc, v) => acc * 60 + parseFloat(v), 0);
                                }
                                const times = timeDivs.map(div => parseTime(div.textContent.trim()));
                                times.push(video.duration);
                                const now = video.currentTime;
                                for (let i = 0; i < times.length - 1; i++) {
                                    if (now < times[i] - 1) {
                                        video.currentTime = times[i];
                                        return;
                                    }
                                }
                                video.currentTime = video.duration;
                            })()
                        """,
                        "prev_chapter": """
                            (() => {
                                const video = document.querySelector('video');
                                if (!video) return;
                                const timeDivs = Array.from(document.querySelectorAll('#contents #endpoint #details div#time.style-scope.ytd-macro-markers-list-item-renderer'));
                                if (timeDivs.length === 0) return;
                                function parseTime(t) {
                                    return t.split(':').reduce((acc, v) => acc * 60 + parseFloat(v), 0);
                                }
                                const times = timeDivs.map(div => parseTime(div.textContent.trim()));
                                times.unshift(0);
                                const now = video.currentTime;
                                let prev = 0;
                                for (let i = 1; i < times.length; i++) {
                                    if (now < times[i] - 1) {
                                        video.currentTime = times[i - 2] || 0;
                                        return;
                                    }
                                }
                                video.currentTime = times[times.length - 2];
                            })()
                        """,
                        "progress_bar": """
                            (() => {
                                # const player = document.getElementById('movie_player');
                                # if (!player) return;
                                # // Toggle progress bar visibility by toggling autohide classes
                                # if (player.classList.contains('ytp-autohide') || player.classList.contains('ytp-autohide-active')) {
                                #     player.classList.remove('ytp-autohide', 'ytp-autohide-active');
                                # } else {
                                #     player.classList.add('ytp-autohide', 'ytp-autohide-active');
                                # }
                                # // Try to trigger the UI update by dispatching mouseenter and mousemove events
                                # const video = document.querySelector('video');
                                # if (video) {
                                #     const rect = video.getBoundingClientRect();
                                #     const eventOpts = {bubbles: true, cancelable: true, view: window};
                                #     // Mouseenter
                                #     video.dispatchEvent(new MouseEvent('mouseenter', {
                                #         ...eventOpts,
                                #         clientX: rect.left + rect.width / 2,
                                #         clientY: rect.top + rect.height / 2
                                #     }));
                                #     // Mousemove
                                #     video.dispatchEvent(new MouseEvent('mousemove', {
                                #         ...eventOpts,
                                #         clientX: rect.left + rect.width / 2,
                                #         clientY: rect.top + rect.height / 2
                                #     }));
                                # }
                            })()
                        """,
                    }.get(command)

                    if expr:
                        try:
                            ws.send(json.dumps({
                                "id": 1,
                                "method": "Runtime.evaluate",
                                "params": { "expression": expr }
                            }))

                            match command:
                                case "skip_forward": print_msg(f"Skipped forward {SKIP_SECONDS} seconds")
                                case "skip_backward": print_msg(f"Skipped backward {SKIP_SECONDS} seconds")
                                case "quality_up": print_msg("Increased video quality")
                                case "quality_down": print_msg("Decreased video quality")
                                case "fix_video": print_msg("Set Quality and Volume to default")
                                case "cc": print_msg("Toggled Closed Captions (CC)")
                                case "fullscreen": print_msg("Toggled Fullscreen")
                                case "theater": print_msg("Toggled theater Mode")
                                case "restart": print_msg("Restarted video")
                                case "next_chapter": print_msg("Skipped to next chapter")
                                case "prev_chapter": print_msg("Skipped to previous chapter")
                                case "progress_bar": print_msg("Toggled progress bar visibility")
                                case _: print_msg(f"Executed command: {command}")

                        except:
                            print_msg(f"{RED}ERROR: Failed to execute command: {command}. Is the video playing?{RESET}")
                            break

            except websocket._exceptions.WebSocketTimeoutException:
                print_msg(f"{YELLOW}WARNING: WebSocket connect timed out after 5s. Retrying...{RESET}")
                if not wait_or_exit(1): return None; continue

            except Exception as e:
                print_msg(f"{RED}ERROR: Error connecting to WebSocket: {e!r}. Retrying...{RESET}")
                if not wait_or_exit(1): return None
    finally: pass


# Function to listen for commands from a socket
def socket_listener():
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        s.bind(("localhost", 65432))
        s.listen()
        while CONTROLLER_RUNNING:
            s.settimeout(1.0)  # Add timeout to allow periodic check of CONTROLLER_RUNNING
            try:
                conn, _ = s.accept()
            except socket.timeout:
                continue
            with conn:
                data = conn.recv(1024)
                if data:
                    COMMAND_QUEUE.put(data.decode())


# functions to handle tray icon actions
def quality_up(icon, item): COMMAND_QUEUE.put("quality_up")
def quality_down(icon, item): COMMAND_QUEUE.put("quality_down")
def fix_video(icon, item): COMMAND_QUEUE.put("fix_video")
def cc(icon, item): COMMAND_QUEUE.put("cc")
def toggle_fullscreen(icon, item): COMMAND_QUEUE.put("fullscreen")
def toggle_theater(icon, item): COMMAND_QUEUE.put("theater")
def restart(icon, item): COMMAND_QUEUE.put("restart")
def next_chapter(icon, item): COMMAND_QUEUE.put("next_chapter")
def prev_chapter(icon, item): COMMAND_QUEUE.put("prev_chapter")
def toggle_progress_bar(icon, item): COMMAND_QUEUE.put("progress_bar")
def on_quit(icon, item):
    print_msg(f"{RED}Closing YouTubeController...{RESET}", space_before=True)
    global CONTROLLER_RUNNING
    CONTROLLER_RUNNING = False
    COMMAND_QUEUE.put("exit")
    if icon is not None:
        icon.stop()


# Function to set the skip seconds based on the selected menu item
def set_skip_seconds(icon, item):
    global SKIP_SECONDS
    match = re.match(r"(\d+)", item.text)
    if match:
        SKIP_SECONDS = int(match.group(1))
        print_msg(f"Set skip seconds to {SKIP_SECONDS}s")
    icon.menu = build_tray_menu(icon)

# Function to build the system tray menu
def build_tray_menu(icon):
    skip_menu = tuple(
        item(
            f"{secs}s{' (default)' if secs == 5 else ''}",
            set_skip_seconds,
            checked=lambda i, s=secs: SKIP_SECONDS == s
        ) for secs in SKIP_OPTIONS
    )
    return Menu(
        item(
            f"YouTubeController V{VERSION}",
            lambda icon, item: None,
            enabled=False
        ),
        Menu.SEPARATOR,
        item(
            f"Seconds to skip: [{SKIP_SECONDS}s]",
            Menu(*skip_menu)
        ),
        Menu.SEPARATOR,
        item("🔺 Quality Up", quality_up),
        item("🔻 Quality Down", quality_down),
        item("🔃 Reset Quality and Volume to default", fix_video),
        item("🔤 Toggle CC", cc),
        item("🎦 Toggle Fullscreen", toggle_fullscreen),
        item("🎦 Toggle theater Mode", toggle_theater),
        item("🔄️ Restart Video", restart),
        item("▶️ Next Chapter", next_chapter),
        item("◀️ Previous Chapter", prev_chapter),
        item("📶 Toggle Progress Bar", toggle_progress_bar),
        item("🪟 Show/Hide Log Window", toggle_log_viewer),
        item("❌ Quit", on_quit)
    )

# Function to set up the system tray icon
def setup_tray():
    icon = Icon("icon")
    icon.icon = get_icon_image()
    icon.menu = build_tray_menu(icon)
    threading.Thread(target=icon.run, daemon=True).start()


# Function to start the application
def main():
    global CONTROLLER_RUNNING
    check_single_instance()
    check_port_available(65432)
    send_thread = threading.Thread(target=send_command_loop)
    socket_thread = threading.Thread(target=socket_listener)
    send_thread.start()
    socket_thread.start()
    setup_tray()
    
    try:
        while CONTROLLER_RUNNING:
            time.sleep(0.05)
    except KeyboardInterrupt:
        print_msg(f"{RED}Exiting on Ctrl+C. {GREY}Please wait...{RESET}", no_time_prefix=True, space_before=True)
        CONTROLLER_RUNNING = False
        COMMAND_QUEUE.put("exit")
    finally:
        CONTROLLER_RUNNING = False
        try:
            with socket.create_connection(("localhost", 65432), timeout=0.1):
                pass
        except Exception:
            pass
        send_thread.join()
        socket_thread.join()
        if lockfile_handle:
            try:
                msvcrt.locking(lockfile_handle.fileno(), msvcrt.LK_UNLCK, 1)
                lockfile_handle.close()
                os.remove(LOCKFILE)
            except Exception:
                pass


if __name__ == "__main__":
    main()