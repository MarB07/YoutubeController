import threading
import queue
import socket
import websocket
import json
import time
import requests
from pystray import Icon, MenuItem as item, Menu
from PIL import Image, ImageDraw
import io
import base64
import subprocess
import os
import sys
import msvcrt

# Redirect stdout and stderr to a log file
class Tee:
    def __init__(self, *streams):
        self.streams = [s for s in streams if s is not None]
    def write(self, message):
        for s in self.streams:
            s.write(message)
            s.flush()
    def flush(self):
        for s in self.streams:
            s.flush()

# Open a log file to write output
logfile = open("log.txt", "w", encoding="utf-8")
sys.stdout = Tee(sys.stdout, logfile)
sys.stderr = Tee(sys.stderr, logfile)

VERSION = "1.2"

COMMAND_QUEUE = queue.Queue()

ICON_RUNNING = True
ICON_BASE64 = """
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
"""

RED = '\033[31m'
GREEN = '\033[32m'
YELLOW = '\033[33m'
RESET = '\033[0m'

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

socket.setdefaulttimeout(5)

# Clear the terminal screen & print initial message
clear = lambda: os.system('cls' if os.name == 'nt' else 'clear')
clear()
print(f"{GREEN}YouTubeControllerV{VERSION} is running... (Made by: https://github.com/MarB07)\r\n{RESET}")

def get_icon_image():
    icon_data = base64.b64decode(ICON_BASE64)
    return Image.open(io.BytesIO(icon_data))

def check_port_available(port=65432):
    try:
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
            s.bind(("localhost", port))
    except OSError:
        print(f"{RED}ERROR: Port {port} is already in use. Please check if no other program is using port {port}{RESET}")
        sys.exit(1)

# Function to find the YouTube WebSocket URL
def find_youtube_ws_url():
    try:
        print("Fetching YouTube WebSocket URL...\r\n")
        tabs = requests.get("http://localhost:9222/json").json()
        youtube_tabs = [
            tab for tab in tabs
            if tab.get("url", "").startswith("https://www.youtube.com/watch?v=")
        ]
        if len(youtube_tabs) > 1:
            print(f"{YELLOW}WARNING: Multiple YouTube tabs detected!")
            print(f"Please close all but one YouTube tab and press Enter to continue...{RESET}")
            input()
            return find_youtube_ws_url()  # Re-check after user input
        elif len(youtube_tabs) == 1:
            print(f"Found YouTube tab: {GREEN}{youtube_tabs[0]['url']}{RESET}")
            return youtube_tabs[0]["webSocketDebuggerUrl"]
        else:
            print(f"{YELLOW}WARNING: No YouTube tab found.{RESET}")
            return None
    except Exception:
        print(f"{RED}ERROR: Error fetching YouTube WebSocket URL. Is Chrome running with remote debugging?{RESET}")
        return None

# Function to send commands to the YouTube WebSocket
def send_command_loop():
    while ICON_RUNNING:
        ws_url = find_youtube_ws_url()
        if not ws_url:
            print(f"{YELLOW}WARNING: YouTube WebSocket URL not found. Retrying...{RESET}")
            time.sleep(1)
            continue
        try:
            print(f"Connecting to WebSocket: {GREEN}{ws_url}{RESET}\r\n")
            ws = websocket.create_connection(ws_url, timeout=5)
            print(f"{GREEN}Connected to YouTube WebSocket{RESET}")
            print("Listening for commands...\r\n")
            while ICON_RUNNING:
                command = COMMAND_QUEUE.get()
                if command == "exit":
                    ws.close()
                    return
                expr = {
                    "forward": "document.querySelector('video').currentTime += 5",
                    "backward": "document.querySelector('video').currentTime -= 5",
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
                }.get(command)
                if expr:
                    try:
                        ws.send(json.dumps({
                            "id": 1,
                            "method": "Runtime.evaluate",
                            "params": { "expression": expr }
                        }))
                        ws.recv()
                        if command == "cc":
                            print("Toggled Closed Captions (CC)")
                        elif command == "forward":
                            print("Skipped forward 5 seconds")
                        elif command == "backward":
                            print("Skipped backward 5 seconds")
                        elif command == "quality_up":
                            print("Increased video quality")
                        elif command == "quality_down":
                            print("Decreased video quality")
                        elif command == "fullscreen":
                            print("Toggled Fullscreen")
                        elif command == "theater":  
                            print("Toggled theater Mode")
                        elif command == "restart":
                            print("Restarted video")
                        else:
                            print(f"Executed command: {command}")
                    except:
                        break
        except websocket._exceptions.WebSocketTimeoutException:
            print(f"{YELLOW}WARNING: WebSocket connect timed out after 5s. Retrying...{RESET}")
            time.sleep(1)
            continue
        except Exception as e:
            print(f"{RED}ERROR: Error connecting to WebSocket: {e!r}. Retrying...{RESET}")
            time.sleep(1)

# Function to listen for commands from a socket
def socket_listener():
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        s.bind(("localhost", 65432))
        s.listen()
        while ICON_RUNNING:
            s.settimeout(None)
            conn, _ = s.accept()
            with conn:
                data = conn.recv(1024)
                if data:
                    COMMAND_QUEUE.put(data.decode())

# Function to handle quitting the application
def on_quit(icon, item):
    global ICON_RUNNING, terminal_process
    ICON_RUNNING = False
    COMMAND_QUEUE.put("exit")
    if terminal_process:
        terminal_process.terminate()
        terminal_process = None
    icon.stop()

terminal_process = None

# Function to open a terminal window that tails the log
def open_terminal(icon, item):
    subprocess.Popen('start cmd /k "powershell -Command Get-Content log.txt -Wait"', shell=True)

# functions to handle tray icon actions
def quality_up(icon, item): COMMAND_QUEUE.put("quality_up")
def quality_down(icon, item): COMMAND_QUEUE.put("quality_down")
def toggle_cc(icon, item): COMMAND_QUEUE.put("cc")
def toggle_fullscreen(icon, item): COMMAND_QUEUE.put("fullscreen")
def toggle_theater(icon, item): COMMAND_QUEUE.put("theater")
def restart(icon, item): COMMAND_QUEUE.put("restart")

# Function to set up the system tray icon
def setup_tray():
    icon = Icon("icon")
    icon.icon = get_icon_image()
    icon.menu = Menu(
        item("Open Terminal", open_terminal),
        item("Quality Up", quality_up),
        item("Quality Down", quality_down),
        item("Restart Video", restart),
        item("Toggle CC", toggle_cc),
        item("Toggle Fullscreen", toggle_fullscreen),
        item("Toggle theater Mode", toggle_theater),
        item("Quit", on_quit)
    )
    threading.Thread(target=icon.run, daemon=True).start()

# Function to start the application
def main():
    global ICON_RUNNING
    check_single_instance()
    check_port_available(65432)
    threading.Thread(target=send_command_loop, daemon=True).start()
    threading.Thread(target=socket_listener, daemon=True).start()
    setup_tray()
    try:
        while ICON_RUNNING:
            time.sleep(0.5)
    except KeyboardInterrupt:
        print("Exiting on Ctrl+C")
        ICON_RUNNING = False
        COMMAND_QUEUE.put("exit")
    finally:
        if lockfile_handle:
            try:
                msvcrt.locking(lockfile_handle.fileno(), msvcrt.LK_UNLCK, 1)
                lockfile_handle.close()
                os.remove(LOCKFILE)
            except Exception:
                pass

if __name__ == "__main__":
    main()