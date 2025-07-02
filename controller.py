import threading
import queue
import socket
import websocket
import json
import time
import requests
from pystray import Icon, MenuItem as item, Menu
from PIL import Image
import io
import base64
import subprocess
import os
import sys
import msvcrt
import datetime

# Constants
VERSION = "1.4.1"
COMMAND_QUEUE = queue.Queue()
CONTROLLER_RUNNING = True

RED = '\033[31m'
GREEN = '\033[32m'
YELLOW = '\033[33m'
GREY = '\033[90m'
RESET = '\033[0m'

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
        print(f"{RED}ERROR: Another instance of YouTubeController is already running. Exiting...{RESET}")
        sys.exit(1)


# Set the default socket timeout to 5 seconds
socket.setdefaulttimeout(5)

# Function to check if the port is available
def check_port_available(port=65432):
    try:
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
            s.bind(("localhost", port))
    except OSError:
        print(f"{RED}ERROR: Port {port} is already in use. Please check if no other program is using port {port}{RESET}")
        sys.exit(1)


# Global state for print_command
_last_printed = None
_last_count = 0

# Helper to get current time as HH:MM:SS
def current_time_str():
    return datetime.datetime.now().strftime("%H:%M:%S")

# Global print_command function
def print_command(msg):
    global _last_printed, _last_count
    time_prefix = f"[{current_time_str()}] "
    if CONTROLLER_RUNNING:
        if msg == _last_printed:
            _last_count += 1
            print(f"{GREY}\033[F{time_prefix}{RESET}{msg} {GREY}(x{_last_count}){RESET}", flush=True)
        else:
            _last_printed = msg
            _last_count = 1
            print(f"{GREY}\r{time_prefix}{RESET}{msg}", flush=True)


# Wait for 'duration' seconds in 'interval' steps, exit early if CONTROLLER_RUNNING is False.
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
print(f"{GREEN}YouTubeControllerV{VERSION} is running... (Made by: https://github.com/MarB07){RESET}")
print(f"{GREY}Press Ctrl+C, or right-click the tray icon and select 'Quit' to exit.{RESET}")



### Main Functions ###

# Function to find the YouTube WebSocket URL
def find_youtube_ws_url():
    try:
        print("\r\nFetching YouTube WebSocket URL...\r\n")
        while True:
            if not CONTROLLER_RUNNING:
                return None
            tabs = requests.get("http://localhost:9222/json").json()
            # Find any YouTube tab
            youtube_tabs = [
                tab for tab in tabs
                if "youtube.com" in tab.get("url", "")
            ]
            if not youtube_tabs:
                print_command(f"{YELLOW}WARNING: No YouTube tab found. Please open youtube.com in your browser.{RESET}")
                if not wait_or_exit(2): return None; continue
            # Now look for a video tab
            video_tabs = [
                tab for tab in youtube_tabs
                if "/watch?v=" in tab.get("url", "")
            ]
            if len(video_tabs) > 1:
                print_command(f"{YELLOW}WARNING: Multiple YouTube video tabs detected!\r\nPlease close all but one YouTube video tab.")
                if not wait_or_exit(5): return None; continue
            elif len(video_tabs) == 1:
                print(f"\r\nFound YouTube video tab: {GREEN}{video_tabs[0]['url']}{RESET}")
                return video_tabs[0]["webSocketDebuggerUrl"]
            else:
                print_command(f"{YELLOW}WARNING: No YouTube video detected. Please open a video in your YouTube tab...{RESET}")
                if not wait_or_exit(2): return None
    except Exception:
        print(f"{RED}ERROR: Error fetching YouTube WebSocket URL. Is Chrome running with remote debugging?{RESET}")
        return None


# Function to send commands to the YouTube WebSocket
def send_command_loop():
    try:
        while CONTROLLER_RUNNING:
            ws_url = find_youtube_ws_url()
            if not ws_url:
                print_command(f"\r\n{YELLOW}WARNING: YouTube WebSocket URL not found. Retrying...{RESET}")
                if not wait_or_exit(1): return None; continue
            try:
                print(f"Connecting to WebSocket: {GREEN}{ws_url}{RESET}")
                ws = websocket.create_connection(ws_url, timeout=5)
                print(f"\r\n{GREEN}Connected to YouTube WebSocket{RESET}")
                print(f"{GREY}Listening for commands...\r\n{RESET}")
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
                            ws.recv()
                            match command:
                                case "skip_forward": print_command("Skipped forward {SKIP_SECONDS} seconds")
                                case "skip_backward": print_command("Skipped backward {SKIP_SECONDS} seconds")
                                case "quality_up": print_command("Increased video quality")
                                case "quality_down": print_command("Decreased video quality")
                                case "fix_video": print_command("Set Quality and Volume to default")
                                case "cc": print_command("Toggled Closed Captions (CC)")
                                case "fullscreen": print_command("Toggled Fullscreen")
                                case "theater": print_command("Toggled theater Mode")
                                case "restart": print_command("Restarted video")
                                case "next_chapter": print_command("Skipped to next chapter")
                                case "prev_chapter": print_command("Skipped to previous chapter")
                                case "progress_bar": print_command("Toggled progress bar visibility")
                                case _: print_command(f"Executed command: {command}")
                        except:
                            break
            except websocket._exceptions.WebSocketTimeoutException:
                print_command(f"\r\n{YELLOW}WARNING: WebSocket connect timed out after 5s. Retrying...{RESET}")
                if not wait_or_exit(1): return None; continue
            except Exception as e:
                print_command(f"\r\n{RED}ERROR: Error connecting to WebSocket: {e!r}. Retrying...{RESET}")
                if not wait_or_exit(1): return None
    finally:
        # Ensure the WebSocket is closed when the loop ends
        pass


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


# Function to handle quitting the application
def on_quit(icon, item):
    global CONTROLLER_RUNNING, terminal_process
    CONTROLLER_RUNNING = False
    COMMAND_QUEUE.put("exit")
    if terminal_process:
        terminal_process.terminate()
        terminal_process = None
    icon.stop()


# Function to open a terminal window that tails the log
def open_terminal(icon, item):
    subprocess.Popen('start cmd /k "powershell -Command Get-Content log.txt -Wait"', shell=True)


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


# Global skip seconds setting
SKIP_SECONDS = 5
SKIP_OPTIONS = [5, 10, 30, 60]

def set_skip_seconds(icon, item):
    global SKIP_SECONDS
    SKIP_SECONDS = int(item.text[:-1])  # Remove 's' and convert to int
    # Rebuild the menu to update the checked state
    icon.menu = build_tray_menu(icon)

def build_tray_menu(icon):
    # Helper to build the skip seconds submenu
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
        item("Quality Up", quality_up),
        item("Quality Down", quality_down),
        item("Reset Quality and Volume to default", fix_video),
        item("Toggle CC", cc),
        item("Toggle Fullscreen", toggle_fullscreen),
        item("Toggle theater Mode", toggle_theater),
        item("Restart Video", restart),
        item("Next Chapter", next_chapter),
        item("Previous Chapter", prev_chapter),
        item("Toggle Progress Bar", toggle_progress_bar),
        item("Open Terminal", open_terminal),
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
        print(f"\r\n{RED}Exiting on Ctrl+C. {GREY}Please wait...{RESET}")
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