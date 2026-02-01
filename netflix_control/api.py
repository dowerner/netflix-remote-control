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


class StatusResponse(BaseModel):
    """Response for status endpoint."""
    status: str
    context: str
    url: str
    nav_status: Optional[dict] = None


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
        """Get current application status."""
        try:
            nav_state.detect_context(browser)
            url = browser.get_current_url()
            js_status = browser.js_nav_status()
            
            return StatusResponse(
                status="running",
                context=nav_state.context.value,
                url=url,
                nav_status=js_status if js_status.get("initialized") else None,
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
    
    @app.post("/control/back", response_model=ControlResponse)
    async def back():
        """Go back (sends Escape key or browser back)."""
        try:
            # First try Escape (works in player and modals)
            browser.send_key("Escape", "Escape")
            return ControlResponse(success=True, message="Back command sent")
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
