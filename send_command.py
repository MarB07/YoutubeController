import socket
import sys

COMMANDS = (
    "skip_forward",
    "skip_backward",
    "quality_up",
    "quality_down",
    "fix_video",
    "cc",
    "fullscreen",
    "theater",
    "restart",
    "next_chapter",
    "prev_chapter",
    "progress_bar",
    )

if len(sys.argv) != 2 or sys.argv[1] not in COMMANDS:
    sys.exit(1)

try:
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        s.connect(("localhost", 65432))
        s.sendall(sys.argv[1].encode())
except Exception as e:
    print(f"Error: {e}")