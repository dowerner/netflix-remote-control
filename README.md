# Netflix Control

A Python application that launches a Chromium browser in kiosk mode for Netflix, with a REST API for remote control. Designed for devices like Raspberry Pi to act as a Netflix remote-controlled display.

## Features

- **Kiosk Browser**: Launches Chromium in fullscreen kiosk mode
- **Session Persistence**: Stores Netflix authentication cookies encrypted with a PIN
- **REST API**: Control Netflix remotely via HTTP endpoints
- **Mouse-based Navigation**: Simulates mouse interactions for Netflix UI (since Netflix doesn't support keyboard navigation)
- **Playback Controls**: Play, pause, mute, fullscreen via keyboard shortcuts

## Requirements

- Python 3.8+
- Chromium, Google Chrome, or Brave browser
- Linux (x64 or ARM64) or macOS

## Installation

```bash
# Clone the repository
cd netflix-control

# Create virtual environment
python3 -m venv venv
source venv/bin/activate

# Install dependencies
pip install -r requirements.txt
```

## Usage

### Basic Start

```bash
python run.py
```

On first run, the browser will navigate to Netflix login. Complete the login manually, and the session will be saved with a PIN.

### With Stored Session

```bash
python run.py --pin 1234
```

### Command Line Options

```
--pin PIN         PIN to load stored session
--port PORT       API server port (default: 8080)
--host HOST       API server host (default: 0.0.0.0)
--no-kiosk        Disable kiosk mode (useful for debugging)
--skip-login      Skip automatic login handling
--browser PATH    Path to browser executable
```

## API Endpoints

### Status

| Endpoint | Method | Description |
|----------|--------|-------------|
| `/status` | GET | Get current status, context, and focused element |

### Playback Control (keyboard-based)

| Endpoint | Method | Description |
|----------|--------|-------------|
| `/control/play` | POST | Start playback |
| `/control/pause` | POST | Pause playback |
| `/control/playpause` | POST | Toggle play/pause |
| `/control/fullscreen` | POST | Toggle fullscreen |
| `/control/mute` | POST | Toggle mute |
| `/control/back` | POST | Go back (Escape key) |

### Navigation (mouse-based)

| Endpoint | Method | Body | Description |
|----------|--------|------|-------------|
| `/control/navigate` | POST | `{"direction": "up\|down\|left\|right"}` | Move focus |
| `/control/select` | POST | - | Click focused element |
| `/control/home` | POST | - | Go to Netflix home |
| `/control/refresh` | POST | - | Refresh UI element discovery |

### Authentication

| Endpoint | Method | Body | Description |
|----------|--------|------|-------------|
| `/auth/status` | GET | - | Check login status |
| `/auth/login` | POST | - | Navigate to login page |
| `/auth/save` | POST | - | Save session (returns PIN) |
| `/auth/load` | POST | `{"pin": 1234}` | Load stored session |
| `/auth/clear` | POST | - | Clear stored session |

## Example Usage with curl

```bash
# Check status
curl http://localhost:8080/status

# Navigate down
curl -X POST http://localhost:8080/control/navigate \
  -H "Content-Type: application/json" \
  -d '{"direction": "down"}'

# Select current item
curl -X POST http://localhost:8080/control/select

# Play/pause
curl -X POST http://localhost:8080/control/playpause

# Toggle fullscreen
curl -X POST http://localhost:8080/control/fullscreen
```

## Architecture

```
┌─────────────────────────────────────────────────────────────┐
│                    Netflix Control System                    │
├─────────────────────────────────────────────────────────────┤
│                                                              │
│  ┌─────────────┐     ┌──────────────────┐     ┌───────────┐ │
│  │  Control    │────▶│  Browser Manager  │────▶│  Chrome/  │ │
│  │  API (HTTP) │     │  (CDP WebSocket)  │     │  Chromium │ │
│  └─────────────┘     └──────────────────┘     │  (Kiosk)  │ │
│        ▲                     │                └───────────┘ │
│        │                     │                      │       │
│  ┌─────┴─────┐       ┌──────┴─────┐         ┌─────┴──────┐ │
│  │  Remote   │       │  Auth      │         │  Netflix   │ │
│  │  App/CLI  │       │  Manager   │         │  Website   │ │
│  └───────────┘       └────────────┘         └────────────┘ │
│                                                              │
└─────────────────────────────────────────────────────────────┘
```

## How Navigation Works

Netflix's web UI doesn't support keyboard arrow navigation like a TV app. This application works around that by:

1. **Element Discovery**: Scanning the DOM for interactive elements (content tiles, buttons)
2. **Virtual Focus**: Tracking which element is "focused" by row/column index
3. **Mouse Simulation**: Using Chrome DevTools Protocol to simulate mouse movements and clicks

When you send a `navigate` command, the app moves the virtual focus and hovers the mouse over the new element. When you send a `select` command, it clicks that element.

## Troubleshooting

### Browser not detected
Ensure Chrome, Chromium, or Brave is installed. You can specify the path manually:
```bash
python run.py --browser /path/to/chrome
```

### Login session expired
Clear the stored session and login again:
```bash
curl -X POST http://localhost:8080/auth/clear
curl -X POST http://localhost:8080/auth/login
# Complete login in browser, then:
curl -X POST http://localhost:8080/auth/save
```

### Navigation not finding elements
Netflix's DOM structure can change. Use the refresh endpoint after page loads:
```bash
curl -X POST http://localhost:8080/control/refresh
```

## License

MIT
