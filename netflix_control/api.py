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
    focused_element: Optional[dict] = None


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
            focused = nav_state.get_focused_element()
            
            return StatusResponse(
                status="running",
                context=nav_state.context.value,
                url=url,
                focused_element={
                    "row": focused.row,
                    "col": focused.col,
                    "x": focused.x,
                    "y": focused.y,
                } if focused else None,
            )
        except Exception as e:
            raise HTTPException(status_code=500, detail=str(e))
    
    # Playback control endpoints (keyboard-based)
    
    @app.post("/control/play", response_model=ControlResponse)
    async def play():
        """Start playback (sends Space key)."""
        try:
            browser.send_key(" ", "Space")
            return ControlResponse(success=True, message="Play command sent")
        except Exception as e:
            raise HTTPException(status_code=500, detail=str(e))
    
    @app.post("/control/pause", response_model=ControlResponse)
    async def pause():
        """Pause playback (sends Space key)."""
        try:
            browser.send_key(" ", "Space")
            return ControlResponse(success=True, message="Pause command sent")
        except Exception as e:
            raise HTTPException(status_code=500, detail=str(e))
    
    @app.post("/control/playpause", response_model=ControlResponse)
    async def playpause():
        """Toggle play/pause (sends Space key)."""
        try:
            browser.send_key(" ", "Space")
            return ControlResponse(success=True, message="Play/pause toggled")
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
    
    # Navigation endpoints (mouse-based)
    
    @app.post("/control/navigate", response_model=ControlResponse)
    async def navigate(request: NavigateRequest):
        """Navigate in a direction (up/down/left/right)."""
        try:
            # Refresh element discovery if needed
            if not nav_state.elements:
                nav_state.discover_elements(browser)
            
            element = nav_state.navigate(request.direction.value)
            
            if element:
                # Move mouse to element to show hover effect
                cx, cy = element.center
                browser.mouse_move(cx, cy)
                return ControlResponse(
                    success=True,
                    message=f"Navigated {request.direction.value} to row={element.row}, col={element.col}"
                )
            else:
                return ControlResponse(
                    success=False,
                    message=f"Cannot navigate {request.direction.value} - at boundary"
                )
        except Exception as e:
            raise HTTPException(status_code=500, detail=str(e))
    
    @app.post("/control/select", response_model=ControlResponse)
    async def select():
        """Click the currently focused element."""
        try:
            element = nav_state.get_focused_element()
            
            if element:
                cx, cy = element.center
                browser.mouse_click(cx, cy)
                return ControlResponse(success=True, message="Element selected")
            else:
                return ControlResponse(success=False, message="No element focused")
        except Exception as e:
            raise HTTPException(status_code=500, detail=str(e))
    
    @app.post("/control/home", response_model=ControlResponse)
    async def home():
        """Navigate to Netflix home/browse page."""
        try:
            auth.navigate_to_browse()
            nav_state.reset_focus()
            nav_state.discover_elements(browser)
            return ControlResponse(success=True, message="Navigated to home")
        except Exception as e:
            raise HTTPException(status_code=500, detail=str(e))
    
    @app.post("/control/refresh", response_model=ControlResponse)
    async def refresh_elements():
        """Refresh discovered UI elements."""
        try:
            nav_state.discover_elements(browser)
            return ControlResponse(
                success=True,
                message=f"Discovered {len(nav_state.elements)} elements in {len(nav_state.rows)} rows"
            )
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
