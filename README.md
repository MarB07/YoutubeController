# YoutubeController

This program lets you control YouTube playback and other actions using command-line commands via `.bat` files or through the system tray icon menu.

## Prerequisites

- **Google Chrome** installed
- **Chrome debugging** enabled
- **Windows** (for `.bat` file support)

## Enabling Chrome Debugging

1. Close all Chrome windows.
2. Open a command prompt.
3. Run:

    ```
    "C:\Program Files\Google\Chrome\Application\chrome.exe" --remote-debugging-port=9222
    ```

    This launches Chrome with remote debugging enabled on port 9222.

To always start Chrome with debugging enabled, create a desktop shortcut:

1. Right-click the desktop and select **New > Shortcut**.
2. Enter:

    ```
    "C:\Program Files\Google\Chrome\Application\chrome.exe" --remote-debugging-port=9222
    ```

3. Click **Next**, name the shortcut (e.g., "Chrome Debug"), and click **Finish**.
4. Use this shortcut whenever you need debugging enabled.

## Using `.bat` Files and the System Tray Menu

- The provided `.bat` files send commands to YoutubeController.
- Each `.bat` file triggers a specific action (e.g., skip 5s, toggle captions).
- The same actions are available via the YoutubeController system tray icon menu.

Ways to trigger commands:
- **Stream Deck:** Assign `.bat` files to Stream Deck buttons.
- **Keyboard Software:** Map `.bat` files to custom key combinations.
- **System Tray Icon:** Right-click the YoutubeController tray icon and select an action.
- **Manual Execution:** Double-click a `.bat` file or run it from the command prompt:

    ```
    path\to\your\file.bat
    ```

## How It Works

- `.bat` files and the tray menu send commands to YoutubeController.
- The program communicates with Chrome through the debugging port to control YouTube.

## Troubleshooting

- Make sure Chrome is running with debugging enabled before using the `.bat` files or tray menu.
- To verify, open `http://localhost:9222/json` in your browser. If it loads, debugging is enabled.