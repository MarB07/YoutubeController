# YoutubeController

This program allows you to control YouTube playback and other actions via command-line commands executed through `.bat` files.

## Prerequisites

- **Google Chrome** installed.
- **Chrome debugging** enabled.
- **Windows** (for `.bat` file support).

## Enabling Chrome Debugging

1. Close all running Chrome instances.
2. Open a command prompt.
3. Run the following command (replace the path if needed):

    ```
    "C:\Program Files\Google\Chrome\Application\chrome.exe" --remote-debugging-port=9222
    ```

    This starts Chrome with remote debugging enabled on port 9222.

## Using the `.bat` Files

- The `.bat` files in this project are used to send commands to the YoutubeController program.
- Each `.bat` file corresponds to a specific action (e.g., skip 5s forward/backward, toggle CC (closed captions), next video).

You can trigger these `.bat` files in several ways:
- **Stream Deck:** Assign the `.bat` files to buttons on your Stream Deck for quick access.
- **Keyboard Software:** Use keyboard macro software to execute the `.bat` files with custom key combinations.
- **Manual Execution:** Double-click the `.bat` file in Windows Explorer or run it from the command prompt:

    ```
    path\to\your\file.bat
    ```

## How It Works

- The `.bat` files execute commands that interact with the YoutubeController program.
- The program communicates with Chrome via the debugging port to control YouTube.

## Troubleshooting

- Ensure Chrome is running with debugging enabled before using the `.bat` files.
- If commands do not work, check that no other Chrome instance is running without debugging.

## License

MIT License