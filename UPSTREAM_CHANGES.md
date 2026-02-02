# Required Changes for netflix-remote-control

This document outlines API enhancements and new endpoints needed in the [netflix-remote-control](https://github.com/dowerner/netflix-remote-control) application to fully support the Kodi addon integration.

## New Endpoints

### POST `/control/focus`

Bring the browser window to the foreground/focus.

**Purpose**: When the user re-launches the Kodi addon while Netflix is already running, we need to bring the browser window back to focus without restarting the application.

**Implementation suggestion**:
```python
# Using Chrome DevTools Protocol
async def focus_browser(self):
    """Bring the browser window to the foreground."""
    await self.page.bringToFront()
    # On Linux, may also need window manager interaction:
    # subprocess.run(['wmctrl', '-a', 'Netflix'])
```

**Response**:
```json
{"success": true}
```

## Enhanced Endpoints

### GET `/status` - Enhanced Response

**Current response**:
```json
{
  "nav_status": {
    "inPlayerMode": true,
    "context": "browse|player|search",
    "focused_element": {...}
  }
}
```

**Requested additions**:
```json
{
  "nav_status": {
    "inPlayerMode": true,
    "context": "browse|player|search",
    "focused_element": {...}
  },
  "playback": {
    "state": "playing|paused|idle",
    "title": "Movie or Episode Name",
    "series_title": "Series Name (if episode)",
    "season": 1,
    "episode": 5,
    "duration_seconds": 7200,
    "position_seconds": 1234,
    "is_muted": false,
    "volume": 100
  }
}
```

**Purpose**: 
- `state`: Needed to synchronize play/pause state with Kodi's player UI
- `title`/`series_title`: Display what's playing in Kodi's Now Playing info
- `duration_seconds`/`position_seconds`: Show progress in Kodi remote apps
- `is_muted`/`volume`: Sync mute state

**Implementation suggestion**:

Netflix's player exposes state via DOM elements and JavaScript. The playback state can be detected by:

1. **Player state detection**:
```javascript
// Check if video is playing or paused
const video = document.querySelector('video');
if (video) {
    const isPlaying = !video.paused && !video.ended && video.readyState > 2;
    const isPaused = video.paused;
    const position = video.currentTime;
    const duration = video.duration;
}
```

2. **Title detection**:
```javascript
// Netflix displays title in specific DOM elements
const titleElement = document.querySelector('[data-uia="video-title"]');
const title = titleElement?.textContent;
```

## Optional Enhancements

### POST `/control/seek`

Seek to a specific position in the video.

**Request body**:
```json
{
  "position_seconds": 1234
}
```

or relative seeking:
```json
{
  "offset_seconds": 30
}
```

**Purpose**: Enable skip forward/backward functionality from Kodi remotes.

### GET `/control/volume`

Get current volume level.

### POST `/control/volume`

Set volume level.

**Request body**:
```json
{
  "level": 75
}
```

## Implementation Priority

1. **High Priority** (needed for basic Kodi integration):
   - `/control/focus` - Required for session reuse
   - Enhanced `/status` with `playback.state` - Required for player sync

2. **Medium Priority** (improves UX):
   - `playback.title` in `/status` - Shows what's playing
   - `playback.duration_seconds` / `playback.position_seconds` - Progress display

3. **Low Priority** (nice to have):
   - `/control/seek` - Skip functionality
   - Volume control endpoints

## Notes

- All playback detection should gracefully handle cases where the video element isn't available (e.g., browsing mode)
- The `inPlayerMode` flag in `nav_status` can be used as a prerequisite check before accessing playback info
- Consider caching playback info to reduce DOM queries on frequent status polling
