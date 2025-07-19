"""
Youtube Controller module

Handles connection to YouTube's WebSocket for sending commands,
manages the command queue, and interfaces with the GUI.
"""

import datetime
import json
import msvcrt
import os
import queue
import re
import socket
import sys
import threading
import time

import tkinter as tk
from string import Template
from tkinter.scrolledtext import ScrolledText
from PIL import Image
import requests
from pystray import Icon, MenuItem as item, Menu
import websocket
from websocket import WebSocketException, WebSocketTimeoutException


# Set the default socket timeout to 5 seconds
socket.setdefaulttimeout(5)


# ANSI color codes for terminal output
RED = '\033[31m'
GREEN = '\033[32m'
YELLOW = '\033[33m'
BLUE = '\033[34m'
GREY = '\033[90m'
RESET = '\033[0m'


### Classes

class Controller:
    """Controller Class"""
    # pylint: disable=too-few-public-methods

    version = "1.6"
    running = True
    command_queue = queue.Queue()
    lockfile_handle = None
    lockfile = "controller.lock"

    last_printed = None
    last_count = 0
    last_timer = 0.0
    screen_buffer = []
    log_viewer = None
    log_viewer_thread = None

    skip_seconds = 5
    skip_options = [5, 10, 30, 60]
    selected_video = None

class Commands:
    """A class for the JS code/files for the commands"""
    JS_COMMAND_PATH = os.path.join("commands", "JS")

    # Larger commands (with their own .js file)
    JS_COMMAND_FILES = {
        "quality_up": "quality_up.js",
        "quality_down": "quality_down.js",
        "next_chapter" : "next_chapter.js",
        "prev_chapter": "prev_chapter.js",
        "progress_bar": "progress_bar.js",
        "video_navigator": "video_navigator.js",
    }

    # Small commands
    INLINE_COMMANDS = {
        "skip_forward": "document.querySelector('video').currentTime += {skip_seconds}",
        "skip_backward": "document.querySelector('video').currentTime -= {skip_seconds}",
        "cc": """ (() => {
            const btn = document.querySelector('.ytp-subtitles-button');
            if (btn) btn.click();
        })()""",
        "fullscreen": """ (() => {
            const btn = document.querySelector('.ytp-fullscreen-button');
            if (btn) btn.click();
        })()""",
        "theater": """ (() => {
            const btn = document.querySelector('.ytp-size-button');
            if (btn) btn.click();
        })()""",
        "restart": "document.querySelector('video').currentTime = 0",
        "navigator_select": """ (() => {
            window.videoNavController.select();
        })()""",
        "navigator_layout": """ (() => {
                
        })()""",
        "navigator_up": """ (() => {
            window.videoNavController.up();
        })()""",
        "navigator_down": """ (() => {
            window.videoNavController.down();
        })()""",
		"navigator_left": """ (() => {
            window.videoNavController.left();
        })()""",
		"navigator_right": """ (() => {
            window.videoNavController.right();
        })()""",
    }

    @classmethod
    def load_js_command(cls, filename, **kwargs):
        """Load the Javascript command from file"""
        path = os.path.join("commands", "JS", filename)
        with open(path, "r", encoding="utf-8") as js_file:
            js_code = js_file.read()
        return Template(js_code).substitute(**kwargs)

    @classmethod
    def get(cls, command: str, **kwargs) -> str | None:
        """Gets the Javascript command"""
        if command in cls.INLINE_COMMANDS:
            js_code = cls.INLINE_COMMANDS[command]
            if kwargs:
                return js_code.format(**kwargs)
            return js_code
        if command in cls.JS_COMMAND_FILES:
            return cls.load_js_command(cls.JS_COMMAND_FILES[command], **kwargs)
        return None

class LogViewer(tk.Tk):
    """A simple Tkinter window to display log messages with ANSI color codes."""
    def __init__(self):
        """Inital setup for the LogViewer"""
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
            '\033[34m': 'log_blue',
            '\033[90m': 'log_grey',
            '\033[0m': 'log_fg',
        }
        self._setup_tags()
        self.after(1000, self._periodic_update)

    def _setup_tags(self):
        """Setup text tags for colored output"""
        self.text.tag_config('log_red', foreground='#ff5555')
        self.text.tag_config('log_green', foreground='#50fa7b')
        self.text.tag_config('log_yellow', foreground='#f1fa8c')
        self.text.tag_config('log_blue', foreground="#4573ff")
        self.text.tag_config('log_grey', foreground='#888888')
        self.text.tag_config('log_fg', foreground='#e6e6e6')

    def update_log(self, lines):
        """Update the log viewer with new lines"""
        if lines == self._last_lines:
            return
        self._last_lines = list(lines)
        self.text.config(state="normal")
        self.text.delete(1.0, tk.END)
        for line in lines:
            self._insert_colored_line(line)
        self.text.config(state="disabled")
        self.text.see(tk.END)

    def clear_log(self):
        """Clear the log viewer"""
        self._last_lines = []
        self.text.config(state="normal")
        self.text.delete(1.0, tk.END)
        self.text.config(state="disabled")
        self.update()

    def _insert_colored_line(self, line):
        """Insert a line with ANSI color codes"""
        ansi_re = re.compile(r'(\033\[\d+m)')
        parts = ansi_re.split(line)
        current_tag = 'log_fg'
        for part in parts:
            if part in self._color_map:
                current_tag = self._color_map[part]
            else:
                self.text.insert(tk.END, part, current_tag)
        self.text.insert(tk.END, '\n', current_tag)

    def show(self):
        """Show the log viewer window"""
        self.deiconify()
        self.lift()
        self.focus_force()

    def hide(self):
        """Hide the log viewer window"""
        self.withdraw()

    def _periodic_update(self):
        """Periodic update to check for new log lines"""
        if Controller.screen_buffer != self._last_lines:
            self.update_log(Controller.screen_buffer)
        self.after(1000, self._periodic_update)


### Helper Functions ###

def check_single_instance():
    """Function to check if another instance of YouTubeController is already running."""
    try:
        Controller.lockfile_handle = open(Controller.lockfile, "w", encoding="utf-8")
        msvcrt.locking(Controller.lockfile_handle.fileno(), msvcrt.LK_NBLCK, 1)
    except OSError:
        print_msg(
            f"{RED}ERROR: Another instance of YouTubeController is already running. "
            f"Exiting...{RESET}",
            no_time_prefix=True)
        sys.exit(1)

def check_port_available(port=65432):
    """Function to check if the specified port is available."""
    try:
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
            s.bind(("localhost", port))
    except OSError:
        print_msg(
            f"{RED}ERROR: Port {port} is already in use. "
            f"Please check if no other program is using port {port}{RESET}",
            no_time_prefix=True)
        sys.exit(1)

def print_msg(msg, no_time_prefix=False, space_before=False):
    """Function to print messages to the terminal with optional timestamp and buffering."""

    def write_screen_buffer():
        if Controller.log_viewer:
            Controller.log_viewer.update_log(Controller.screen_buffer)

    def current_time_str():
        return datetime.datetime.now().strftime("%H:%M:%S")

    prefix = "\r\n" if space_before else ""
    if no_time_prefix:
        print(f"{prefix}{msg}", flush=True)
        Controller.last_printed = None
        Controller.screen_buffer.append(f"{prefix}{msg}" if space_before else msg)
        write_screen_buffer()
        return
    time_prefix = f"[{current_time_str()}] "
    now = time.time()

    if Controller.running:
        if msg == Controller.last_printed and (now - Controller.last_timer) < 60:
            Controller.last_count += 1
            line = f"{GREY}{time_prefix}{RESET}{msg} {GREY}(x{Controller.last_count}){RESET}"
            Controller.screen_buffer[-1] = line
        else:
            Controller.last_printed = msg
            Controller.last_count = 1
            line = f"{prefix}{GREY}{time_prefix}{RESET}{msg}"
            Controller.screen_buffer.append(line)

        if Controller.last_count > 1:
            print(f"{GREY}\033[F{Controller.screen_buffer[-1]}", flush=True)
        else:
            print(f"{GREY}\r{Controller.screen_buffer[-1]}", flush=True)
        Controller.last_timer = now
        write_screen_buffer()

def start_log_viewer():
    """Function to start the log viewer in a separate thread."""
    if Controller.log_viewer:
        Controller.log_viewer.show()
        return
    def run():
        Controller.log_viewer = LogViewer()
        Controller.log_viewer.update_log(Controller.screen_buffer)
        Controller.log_viewer.mainloop()
        Controller.log_viewer = None
    Controller.log_viewer_THREAD = threading.Thread(target=run, daemon=True)
    Controller.log_viewer_THREAD.start()

def toggle_log_viewer():
    """Function to toggle the visibility of the log viewer."""
    if Controller.log_viewer and Controller.log_viewer.state() != 'withdrawn':
        Controller.log_viewer.hide()
    else:
        start_log_viewer()

def wait_or_exit(duration, interval=0.1):
    """Wait for a duration in small intervals, checking if Controller.running is still True."""
    steps = int(duration / interval)
    for _ in range(steps):
        if not Controller.running:
            return False
        time.sleep(interval)
    return True

def clear_screen():
    """Clears the screen"""
    os.system('cls' if os.name == 'nt' else 'clear')

def welcome_message():
    """Clears the terminal and print a welcome message."""

    clear_screen()

    if Controller.log_viewer:
        Controller.log_viewer.clear_log()
        Controller.log_viewer.show()
        Controller.screen_buffer.clear()

    print_msg(
        f"{GREEN}YouTubeControllerV{Controller.version} is running... "
        f"(Made by: https://github.com/MarB07){RESET}",
        no_time_prefix=True)
    print_msg(
        f"{GREY}Press Ctrl+C, or right-click the tray icon and select 'Quit' to exit.\r\n{RESET}",
        no_time_prefix=True)


### Main Functions ###

def find_youtube_ws_url():
    """Function to find the YouTube WebSocket URL"""
    print_msg("Fetching YouTube WebSocket URL...", no_time_prefix=True)
    start_time = time.time()
    timeout_seconds = 600  # 10 minutes

    while Controller.running:
        elapsed = time.time() - start_time
        if elapsed > timeout_seconds:
            print_msg(f"{RED}ERROR: No YouTube video tab found after 10 minutes. Exiting...{RESET}")
            on_quit(None) # Exit the application
            return None

        try:
            tabs = requests.get("http://localhost:9222/json", timeout=10).json()
            youtube_tabs = [tab for tab in tabs if "youtube.com" in tab.get("url", "")]
            if not youtube_tabs:
                print_msg(
                    f"{YELLOW}WARNING: No YouTube tab found."
                    f"Please open youtube.com in your browser.{RESET}")
                if not wait_or_exit(2):
                    return None
                continue

            video_tabs = [tab for tab in youtube_tabs if "/watch?v=" in tab.get("url", "")]
            if len(video_tabs) > 1:
                print_msg(
                    f"{YELLOW}WARNING: Multiple YouTube video tabs detected!"
                    f" Please close all but one YouTube video tab.{RESET}")
                if not wait_or_exit(5):
                    return None
                continue

            if len(video_tabs) == 1:
                print_msg(
                    f"Found YouTube video tab: {GREEN}{video_tabs[0]['url']}{RESET}",
                    no_time_prefix=True, space_before=True)
                return video_tabs[0]["webSocketDebuggerUrl"]

            print_msg(
                f"{YELLOW}WARNING: No YouTube video detected."
                f"Please open a video in your YouTube tab...{RESET}",
                space_before=True)
            if not wait_or_exit(2):
                return None
            continue

        except requests.exceptions.RequestException as e:
            print_msg(
                f"{RED}ERROR: Error fetching YouTube WebSocket URL."
                f"Is Chrome running with remote debugging?{RESET}",
                no_time_prefix=True)
            print_msg(f"{RED}Exception: {str(e)}{RESET}")
    return None

def send_command_loop():
    """Function to connect to the YouTube WebSocket and send commands from the command queue."""
    try:
        while Controller.running:
            ws_url = find_youtube_ws_url()
            if not ws_url:
                print_msg(
                    f"{YELLOW}WARNING: YouTube WebSocket URL not found. Retrying in 5s.{RESET}")
                if not wait_or_exit(5):
                    return
                continue

            try:
                print_msg(f"Connecting to WebSocket: {GREEN}{ws_url}{RESET}", no_time_prefix=True)
                ws = websocket.create_connection(ws_url, timeout=5)

                welcome_message()
                print_msg(f"{GREEN}Connected to YouTube WebSocket{RESET}", no_time_prefix=True)
                print_msg(f"{GREY}Listening for commands...{RESET}")

                while Controller.running:
                    command = Controller.command_queue.get()
                    if command == "exit":
                        ws.close()
                        return

                    expr = Commands.get(command, skip_seconds=Controller.skip_seconds) \
                        if command in ("skip_forward", "skip_backward") \
                        else Commands.get(command)

                    if expr:
                        if not send_ws_command(ws, expr, command):
                            break

            except WebSocketTimeoutException:
                print_msg(
                    f"{YELLOW}WARNING: WebSocket connect timed out after 5s. Retrying...{RESET}")
                if not wait_or_exit(1):
                    return
            except WebSocketException as e:
                print_msg(f"{RED}ERROR: Error connecting to WebSocket. Retrying in 5s.{RESET}")
                print_msg(f"{RED}Exception: {str(e)}{RESET}")
                if not wait_or_exit(5):
                    return
    finally:
        pass

def send_ws_command(ws, expr, command):
    """Send the evaluated JS expression over the WebSocket."""
    try:
        ws.send(json.dumps({
            "id": 1,
            "method": "Runtime.evaluate",
            "params": {"expression": expr}
        }))
        print_command_result(command)
        return True
    except WebSocketException as e:
        print_msg(f"{RED}ERROR: Failed to execute command: {command}{RESET}")
        print_msg(f"{YELLOW}WebSocket error: {str(e)}{RESET}")
        return False
    except (TypeError, ValueError) as e:
        print_msg(f"{RED}ERROR: Failed to serialize command JSON: {command}{RESET}")
        print_msg(f"{YELLOW}Exception: {str(e)}{RESET}")
        return False

def print_command_result(command):
    """Print a status message based on the executed command."""
    skip = Controller.skip_seconds
    selected = Controller.selected_video

    messages = {
        "skip_forward": f"Skipped {BLUE}forward {skip}{RESET} seconds",
        "skip_backward": f"Skipped {BLUE}backward {skip}{RESET} seconds",
        "quality_up": f"{BLUE}Increased{RESET} video quality",
        "quality_down": f"{BLUE}Decreased{RESET} video quality",
        "cc": f"Toggled {BLUE}Closed Captions{RESET} (CC)",
        "fullscreen": f"Toggled {BLUE}Fullscreen{RESET}",
        "theater": f"Toggled {BLUE}theater Mode{RESET}",
        "restart": f"Restarted {BLUE}video{RESET}",
        "next_chapter": f"Skipped to {BLUE}next{RESET} chapter",
        "prev_chapter": f"Skipped to {BLUE}previous{RESET} chapter",
        "progress_bar": f"Toggled {BLUE}progress bar{RESET} visibility",
        "video_navigator": f"Toggled {BLUE}video navigator{RESET}",
        "navigator_select": f"Selected video {BLUE}{selected}{RESET} in navigator",
        "navigator_layout": f"Changed {BLUE}navigator layout{RESET}",
        "navigator_up": f"Moved {BLUE}up{RESET} in navigator",
        "navigator_down": f"Moved {BLUE}down{RESET} in navigator",
        "navigator_left": f"Moved {BLUE}left{RESET} in navigator",
        "navigator_right": f"Moved {BLUE}right{RESET} in navigator",
    }

    print_msg(messages.get(command, f"Executed command: {command}"))

def socket_listener():
    """Function to listen for commands from a socket and put them in the command queue."""
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        s.bind(("localhost", 65432))
        s.listen()
        while Controller.running:
            s.settimeout(1.0)  # Add timeout to allow periodic check of Controller.running
            try:
                conn, _ = s.accept()
            except socket.timeout:
                continue
            with conn:
                data = conn.recv(1024)
                if data:
                    Controller.command_queue.put(data.decode())


### System Tray Functions ###

def on_quit(icon):
    """Function to handle quitting the application."""
    print_msg(f"{RED}Closing YouTubeController...{RESET}", space_before=True)
    Controller.running = False
    Controller.command_queue.put("exit")
    if icon is not None:
        icon.stop()

def set_skip_seconds(icon, menu_item):
    """Function to set the skip seconds based on the selected menu item."""
    match = re.match(r"(\d+)", menu_item.text)
    if match:
        Controller.skip_seconds = int(match.group(1))
        print_msg(f"Set {BLUE}skip seconds{RESET} to {BLUE}{Controller.skip_seconds}{RESET}s")
    icon.menu = build_tray_menu()

def build_tray_menu():
    """Function to build the system tray menu."""
    skip_menu = tuple(
        item(
            f"{secs}s{' (default)' if secs == 5 else ''}",
            set_skip_seconds,
            checked=lambda i, s=secs: Controller.skip_seconds == s
        ) for secs in Controller.skip_options
    )
    return Menu(
        item(
            f"YouTubeController V{Controller.version}",
            lambda icon, item: None,
            enabled=False
        ),
        Menu.SEPARATOR,
        item(
            f"Seconds to skip: [{Controller.skip_seconds}s]",
            Menu(*skip_menu)
        ),
        Menu.SEPARATOR,
        item("🪟 Show/Hide Log Window", toggle_log_viewer),
        Menu.SEPARATOR,
        item("❌ Quit", on_quit)
    )

def resource_path(relative_path):
    """Get the absolute path to a resource, works for both development and PyInstaller bundle."""
    if hasattr(sys, '_MEIPASS'):  # pylint: disable=protected-access
        return os.path.join(sys._MEIPASS, relative_path)
    return os.path.join(os.path.abspath(os.path.dirname(__file__)), relative_path)

def get_icon_image():
    """Returns the icon.ico for the"""
    return Image.open(resource_path("icon.ico"))

def setup_tray():
    """Function to set up the system tray icon and menu."""
    icon = Icon("icon")
    icon.icon = get_icon_image()
    icon.menu = build_tray_menu()
    threading.Thread(target=icon.run, daemon=True).start()


### Main Application Logic ###

def main():
    """Main function to start the YouTubeController application."""
    check_single_instance()
    check_port_available(65432)
    welcome_message()
    send_thread = threading.Thread(target=send_command_loop)
    socket_thread = threading.Thread(target=socket_listener)
    send_thread.start()
    socket_thread.start()
    setup_tray()

    try:
        while Controller.running:
            time.sleep(0.05)
    except KeyboardInterrupt:
        print_msg(
            f"{RED}Exiting on Ctrl+C. {GREY}Please wait...{RESET}",
            no_time_prefix=True, space_before=True)
        Controller.running = False
        Controller.command_queue.put("exit")
    finally:
        try:
            with socket.create_connection(("localhost", 65432), timeout=0.1):
                pass
        except (socket.timeout, ConnectionRefusedError, OSError):
            pass
        send_thread.join()
        socket_thread.join()
        if Controller.lockfile_handle:
            try:
                msvcrt.locking(Controller.lockfile_handle.fileno(), msvcrt.LK_UNLCK, 1)
                Controller.lockfile_handle.close()
                os.remove(Controller.lockfile)
            except OSError:
                pass

if __name__ == "__main__":
    main()
