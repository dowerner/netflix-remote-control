# -*- coding: utf-8 -*-
"""REST API for Netflix remote control."""

from enum import Enum
from typing import TYPE_CHECKING, Optional

from fastapi import FastAPI, HTTPException
from pydantic import BaseModel

if TYPE_CHECKING:
    from .auth import AuthManager
    from .browser import BrowserManager
    from .navigation import NavigationState


class Direction(str, Enum):
    """Navigation directions."""
    UP = "up"
    DOWN = "down"
    LEFT = "left"
    RIGHT = "right"


class NavigateRequest(BaseModel):
    """Request body for navigation."""
    direction: Direction


class PinRequest(BaseModel):
    """Request body for PIN operations."""
    pin: int


class SearchRequest(BaseModel):
    """Request body for search operations."""
    query: str


class SeekRequest(BaseModel):
    """Request body for seek operations."""
    position_seconds: Optional[int] = None
    offset_seconds: Optional[int] = None


class VolumeRequest(BaseModel):
    """Request body for volume operations."""
    level: int


class PlaybackRateRequest(BaseModel):
    """Request body for playback rate operations."""
    rate: float


class PlaybackInfo(BaseModel):
    """Playback state information for Kodi integration."""
    state: str  # "playing" | "paused" | "idle"
    title: Optional[str] = None
    series_title: Optional[str] = None
    season: Optional[int] = None
    episode: Optional[int] = None
    duration_seconds: Optional[int] = None
    position_seconds: Optional[int] = None
    is_muted: Optional[bool] = None
    volume: Optional[int] = None


class StatusResponse(BaseModel):
    """Response for status endpoint."""
    status: str
    context: str
    url: str
    nav_status: Optional[dict] = None
    playback: Optional[PlaybackInfo] = None


class AuthStatusResponse(BaseModel):
    """Response for auth status endpoint."""
    logged_in: bool
    has_stored_session: bool


class ControlResponse(BaseModel):
    """Generic control response."""
    success: bool
    message: str


def create_api(
    browser: "BrowserManager",
    auth: "AuthManager",
    nav_state: "NavigationState"
) -> FastAPI:
    """Create and configure the FastAPI application.
    
    Args:
        browser: BrowserManager instance.
        auth: AuthManager instance.
        nav_state: NavigationState instance.
        
    Returns:
        Configured FastAPI application.
    """
    app = FastAPI(
        title="Netflix Control API",
        description="Remote control API for Netflix kiosk browser",
        version="0.1.0",
    )
    
    # Store references
    app.state.browser = browser
    app.state.auth = auth
    app.state.nav = nav_state
    
    # Status endpoints
    
    @app.get("/status", response_model=StatusResponse)
    async def get_status():
        """Get current application status including playback info."""
        try:
            nav_state.detect_context(browser)
            url = browser.get_current_url()
            js_status = browser.js_nav_status()
            
            # Get playback info if video player is available
            playback_info = None
            player_state = browser.player_state()
            
            if player_state.get("found"):
                playback_info = PlaybackInfo(
                    state=player_state.get("state", "idle"),
                    title=player_state.get("title"),
                    series_title=player_state.get("series_title"),
                    season=player_state.get("season"),
                    episode=player_state.get("episode"),
                    duration_seconds=player_state.get("duration_seconds"),
                    position_seconds=player_state.get("position_seconds"),
                    is_muted=player_state.get("is_muted"),
                    volume=player_state.get("volume"),
                )
            
            return StatusResponse(
                status="running",
                context=nav_state.context.value,
                url=url,
                nav_status=js_status if js_status.get("initialized") else None,
                playback=playback_info,
            )
        except Exception as e:
            raise HTTPException(status_code=500, detail=str(e))
    
    # Playback control endpoints (JavaScript-based)
    
    @app.post("/control/play", response_model=ControlResponse)
    async def play():
        """Start video playback using JavaScript."""
        try:
            result = browser.player_play()
            if result.get("success"):
                state = result.get("state", "playing")
                method = result.get("method", "unknown")
                return ControlResponse(success=True, message=f"Playback started ({state}, via {method})")
            else:
                return ControlResponse(success=False, message=result.get("message", "Failed to start playback"))
        except Exception as e:
            raise HTTPException(status_code=500, detail=str(e))
    
    @app.post("/control/pause", response_model=ControlResponse)
    async def pause():
        """Pause video playback using JavaScript."""
        try:
            result = browser.player_pause()
            if result.get("success"):
                state = result.get("state", "paused")
                return ControlResponse(success=True, message=f"Playback paused ({state})")
            else:
                return ControlResponse(success=False, message=result.get("message", "Failed to pause"))
        except Exception as e:
            raise HTTPException(status_code=500, detail=str(e))
    
    @app.post("/control/playpause", response_model=ControlResponse)
    async def playpause():
        """Toggle video play/pause using JavaScript."""
        try:
            result = browser.player_toggle()
            if result.get("success"):
                state = result.get("state", "toggled")
                method = result.get("method", "unknown")
                return ControlResponse(success=True, message=f"Playback toggled ({state}, via {method})")
            else:
                return ControlResponse(success=False, message=result.get("message", "Failed to toggle playback"))
        except Exception as e:
            raise HTTPException(status_code=500, detail=str(e))
    
    @app.get("/control/player/status", response_model=ControlResponse)
    async def player_status():
        """Get current video player state (playing, position, duration)."""
        try:
            result = browser.player_state()
            if result.get("found"):
                playing = "playing" if result.get("playing") else "paused"
                current = result.get("currentTime", 0)
                duration = result.get("duration", 0)
                return ControlResponse(
                    success=True,
                    message=f"Player {playing}, {current:.1f}s / {duration:.1f}s"
                )
            else:
                return ControlResponse(success=False, message="No video player found")
        except Exception as e:
            raise HTTPException(status_code=500, detail=str(e))
    
    @app.post("/control/stop", response_model=ControlResponse)
    async def stop():
        """Stop video playback and close the player."""
        try:
            result = browser.player_stop()
            if result.get("success"):
                return ControlResponse(success=True, message=result.get("message", "Player stopped"))
            else:
                return ControlResponse(success=False, message=result.get("message", "Failed to stop"))
        except Exception as e:
            raise HTTPException(status_code=500, detail=str(e))
    
    @app.post("/control/skip/forward", response_model=ControlResponse)
    async def skip_forward():
        """Skip forward in the video by 10 seconds (clicks skip button)."""
        try:
            result = browser.player_skip_forward()
            if result.get("success"):
                return ControlResponse(success=True, message=result.get("message", "Skipped forward 10 seconds"))
            else:
                return ControlResponse(success=False, message=result.get("message", "Failed to skip forward"))
        except Exception as e:
            raise HTTPException(status_code=500, detail=str(e))
    
    @app.post("/control/skip/backward", response_model=ControlResponse)
    async def skip_backward():
        """Skip backward in the video by 10 seconds (clicks skip button)."""
        try:
            result = browser.player_skip_backward()
            if result.get("success"):
                return ControlResponse(success=True, message=result.get("message", "Skipped backward 10 seconds"))
            else:
                return ControlResponse(success=False, message=result.get("message", "Failed to skip backward"))
        except Exception as e:
            raise HTTPException(status_code=500, detail=str(e))
    
    @app.post("/control/seek", response_model=ControlResponse)
    async def seek(request: SeekRequest):
        """Seek to a specific position or by an offset.
        
        Provide either position_seconds (absolute) or offset_seconds (relative).
        Note: Netflix DRM may prevent direct seeking via video.currentTime.
        """
        try:
            if request.position_seconds is not None:
                result = browser.player_seek(request.position_seconds)
                if result.get("success"):
                    pos = result.get("position_seconds", 0)
                    return ControlResponse(success=True, message=f"Seeked to {pos}s")
                else:
                    return ControlResponse(success=False, message=result.get("message", "Seek failed"))
            elif request.offset_seconds is not None:
                result = browser.player_seek_relative(request.offset_seconds)
                if result.get("success"):
                    pos = result.get("position_seconds", 0)
                    return ControlResponse(success=True, message=f"Seeked to {pos}s")
                else:
                    return ControlResponse(success=False, message=result.get("message", "Seek failed"))
            else:
                return ControlResponse(success=False, message="Provide position_seconds or offset_seconds")
        except Exception as e:
            raise HTTPException(status_code=500, detail=str(e))
    
    @app.post("/control/fullscreen", response_model=ControlResponse)
    async def fullscreen():
        """Toggle fullscreen (sends F key)."""
        try:
            browser.send_key("f", "KeyF")
            return ControlResponse(success=True, message="Fullscreen toggled")
        except Exception as e:
            raise HTTPException(status_code=500, detail=str(e))
    
    @app.post("/control/mute", response_model=ControlResponse)
    async def mute():
        """Toggle mute (sends M key)."""
        try:
            browser.send_key("m", "KeyM")
            return ControlResponse(success=True, message="Mute toggled")
        except Exception as e:
            raise HTTPException(status_code=500, detail=str(e))
    
    @app.get("/control/volume")
    async def get_volume():
        """Get current volume level and muted state."""
        try:
            result = browser.player_get_volume()
            if result.get("found"):
                return {
                    "success": True,
                    "volume": result.get("volume", 100),
                    "is_muted": result.get("is_muted", False),
                }
            else:
                return {"success": False, "message": "No video player found"}
        except Exception as e:
            raise HTTPException(status_code=500, detail=str(e))
    
    @app.post("/control/volume", response_model=ControlResponse)
    async def set_volume(request: VolumeRequest):
        """Set volume level (0-100)."""
        try:
            result = browser.player_set_volume(request.level)
            if result.get("success"):
                vol = result.get("volume", request.level)
                return ControlResponse(success=True, message=f"Volume set to {vol}")
            else:
                return ControlResponse(success=False, message=result.get("message", "Failed to set volume"))
        except Exception as e:
            raise HTTPException(status_code=500, detail=str(e))
    
    @app.get("/control/speed")
    async def get_playback_rate():
        """Get current playback speed/rate."""
        try:
            result = browser.player_get_playback_rate()
            if result.get("found"):
                return {
                    "success": True,
                    "rate": result.get("rate", 1.0),
                    "method": result.get("method", "unknown"),
                }
            else:
                return {"success": False, "message": "No video player found"}
        except Exception as e:
            raise HTTPException(status_code=500, detail=str(e))
    
    @app.post("/control/speed", response_model=ControlResponse)
    async def set_playback_rate(request: PlaybackRateRequest):
        """Set playback speed/rate (e.g., 1.0 for normal, 1.5 for 1.5x)."""
        try:
            result = browser.player_set_playback_rate(request.rate)
            if result.get("success"):
                rate = result.get("rate", request.rate)
                return ControlResponse(success=True, message=f"Playback speed set to {rate}x")
            else:
                return ControlResponse(success=False, message=result.get("message", "Failed to set playback rate"))
        except Exception as e:
            raise HTTPException(status_code=500, detail=str(e))
    
    @app.get("/control/tracks/audio")
    async def get_audio_tracks():
        """Get available audio tracks."""
        try:
            result = browser.player_get_audio_tracks()
            if result.get("found"):
                return {
                    "success": True,
                    "tracks": result.get("tracks", []),
                    "currentTrack": result.get("currentTrack"),
                }
            else:
                return {"success": False, "message": "No audio tracks found"}
        except Exception as e:
            raise HTTPException(status_code=500, detail=str(e))
    
    @app.get("/control/tracks/text")
    async def get_text_tracks():
        """Get available subtitle/text tracks."""
        try:
            result = browser.player_get_text_tracks()
            if result.get("found"):
                return {
                    "success": True,
                    "tracks": result.get("tracks", []),
                    "currentTrack": result.get("currentTrack"),
                }
            else:
                return {"success": False, "message": "No text tracks found"}
        except Exception as e:
            raise HTTPException(status_code=500, detail=str(e))
    
    @app.post("/control/back", response_model=ControlResponse)
    async def back():
        """Go back (sends Escape key or browser back)."""
        try:
            # First try Escape (works in player and modals)
            browser.send_key("Escape", "Escape")
            return ControlResponse(success=True, message="Back command sent")
        except Exception as e:
            raise HTTPException(status_code=500, detail=str(e))
    
    @app.post("/control/focus", response_model=ControlResponse)
    async def focus_browser():
        """Bring the browser window to the foreground.
        
        Useful when reconnecting to an already running Netflix session.
        """
        try:
            result = browser.bring_to_front()
            if result.get("success"):
                return ControlResponse(success=True, message="Browser window focused")
            else:
                return ControlResponse(success=False, message=result.get("error", "Failed to focus browser"))
        except Exception as e:
            raise HTTPException(status_code=500, detail=str(e))
    
    # Navigation endpoints (JavaScript-based - preferred)
    
    @app.post("/control/navigate", response_model=ControlResponse)
    async def navigate(request: NavigateRequest):
        """Navigate in a direction (up/down/left/right) using JS injection."""
        try:
            result = browser.js_navigate(request.direction.value)
            
            if result.get("success"):
                if result.get("moved"):
                    return ControlResponse(
                        success=True,
                        message=f"Navigated {request.direction.value} to row={result.get('row')}, col={result.get('col')}"
                    )
                else:
                    return ControlResponse(
                        success=True,
                        message=f"Already at {request.direction.value} boundary"
                    )
            else:
                return ControlResponse(
                    success=False,
                    message=result.get("message", "Navigation failed")
                )
        except Exception as e:
            raise HTTPException(status_code=500, detail=str(e))
    
    @app.post("/control/select", response_model=ControlResponse)
    async def select():
        """Click the currently focused element using JS injection."""
        try:
            result = browser.js_select()
            
            if result.get("success"):
                return ControlResponse(success=True, message="Element clicked")
            else:
                return ControlResponse(
                    success=False,
                    message=result.get("message", "No element focused")
                )
        except Exception as e:
            raise HTTPException(status_code=500, detail=str(e))
    
    @app.post("/control/home", response_model=ControlResponse)
    async def home():
        """Navigate to Netflix home/browse page."""
        try:
            auth.navigate_to_browse()
            # Re-inject nav controller and discover elements
            browser.inject_nav_controller()
            return ControlResponse(success=True, message="Navigated to home")
        except Exception as e:
            raise HTTPException(status_code=500, detail=str(e))
    
    @app.post("/control/refresh", response_model=ControlResponse)
    async def refresh_elements():
        """Refresh discovered UI elements using JS injection."""
        try:
            result = browser.js_discover()
            return ControlResponse(
                success=result.get("success", False),
                message=f"Discovered {result.get('elementCount', 0)} elements in {result.get('rowCount', 0)} rows"
            )
        except Exception as e:
            raise HTTPException(status_code=500, detail=str(e))
    
    @app.post("/control/inject", response_model=ControlResponse)
    async def inject_nav():
        """Inject/reinject the navigation controller into the page."""
        try:
            result = browser.inject_nav_controller()
            return ControlResponse(
                success=result.get("success", False),
                message=f"Nav controller injected, found {result.get('elementCount', 0)} elements"
            )
        except Exception as e:
            raise HTTPException(status_code=500, detail=str(e))
    
    # Search endpoints
    
    @app.post("/control/search/open", response_model=ControlResponse)
    async def open_search():
        """Open the search box by clicking the search icon."""
        try:
            result = browser.open_search()
            return ControlResponse(
                success=result.get("success", False),
                message=result.get("message", "Search operation completed")
            )
        except Exception as e:
            raise HTTPException(status_code=500, detail=str(e))
    
    @app.post("/control/search", response_model=ControlResponse)
    async def search(request: SearchRequest):
        """Type a search query into the search box.
        
        Opens search if not already open, clears existing text, and types the query.
        """
        try:
            result = browser.search_type(request.query)
            return ControlResponse(
                success=result.get("success", False),
                message=result.get("message", "Search completed")
            )
        except Exception as e:
            raise HTTPException(status_code=500, detail=str(e))
    
    @app.post("/control/search/clear", response_model=ControlResponse)
    async def clear_search():
        """Clear the search input field."""
        try:
            result = browser.clear_search()
            return ControlResponse(
                success=result.get("success", False),
                message=result.get("message", "Search cleared")
            )
        except Exception as e:
            raise HTTPException(status_code=500, detail=str(e))
    
    # Legacy navigation endpoints (mouse-based - deprecated)
    
    @app.post("/control/legacy/navigate", response_model=ControlResponse)
    async def legacy_navigate(request: NavigateRequest):
        """[DEPRECATED] Navigate using mouse simulation. Use /control/navigate instead."""
        try:
            if not nav_state.elements:
                nav_state.discover_elements(browser)
            
            element = nav_state.navigate(request.direction.value)
            
            if element:
                cx, cy = element.center
                browser.mouse_move(cx, cy)
                return ControlResponse(
                    success=True,
                    message=f"[Legacy] Navigated {request.direction.value} to row={element.row}, col={element.col}"
                )
            else:
                return ControlResponse(
                    success=False,
                    message=f"Cannot navigate {request.direction.value} - at boundary"
                )
        except Exception as e:
            raise HTTPException(status_code=500, detail=str(e))
    
    @app.post("/control/legacy/select", response_model=ControlResponse)
    async def legacy_select():
        """[DEPRECATED] Click using mouse simulation. Use /control/select instead."""
        try:
            element = nav_state.get_focused_element()
            
            if element:
                cx, cy = element.center
                browser.mouse_click(cx, cy)
                return ControlResponse(success=True, message="[Legacy] Element selected")
            else:
                return ControlResponse(success=False, message="No element focused")
        except Exception as e:
            raise HTTPException(status_code=500, detail=str(e))
    
    # Authentication endpoints
    
    @app.get("/auth/status", response_model=AuthStatusResponse)
    async def auth_status():
        """Get authentication status."""
        try:
            return AuthStatusResponse(
                logged_in=auth.is_logged_in(),
                has_stored_session=auth.has_stored_session(),
            )
        except Exception as e:
            raise HTTPException(status_code=500, detail=str(e))
    
    @app.post("/auth/login", response_model=ControlResponse)
    async def initiate_login():
        """Initiate login flow by navigating to login page."""
        try:
            auth.initiate_login()
            return ControlResponse(
                success=True,
                message="Navigated to login page. Please complete login in browser."
            )
        except Exception as e:
            raise HTTPException(status_code=500, detail=str(e))
    
    @app.post("/auth/save", response_model=ControlResponse)
    async def save_session():
        """Save current session cookies."""
        try:
            if not auth.is_logged_in():
                return ControlResponse(success=False, message="Not logged in")
            
            pin = auth.save_session()
            return ControlResponse(
                success=True,
                message=f"Session saved. Your PIN is: {pin}"
            )
        except ValueError as e:
            return ControlResponse(success=False, message=str(e))
        except Exception as e:
            raise HTTPException(status_code=500, detail=str(e))
    
    @app.post("/auth/load", response_model=ControlResponse)
    async def load_session(request: PinRequest):
        """Load stored session with PIN."""
        try:
            auth.set_pin(request.pin)
            if auth.load_session(request.pin):
                auth.navigate_to_browse()
                return ControlResponse(success=True, message="Session loaded")
            else:
                return ControlResponse(success=False, message="Failed to load session. Invalid PIN or expired.")
        except Exception as e:
            raise HTTPException(status_code=500, detail=str(e))
    
    @app.post("/auth/clear", response_model=ControlResponse)
    async def clear_session():
        """Clear stored session and cookies."""
        try:
            auth.clear_session()
            return ControlResponse(success=True, message="Session cleared")
        except Exception as e:
            raise HTTPException(status_code=500, detail=str(e))
    
    return app
