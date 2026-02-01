# -*- coding: utf-8 -*-
"""Browser manager for controlling Chromium via Chrome DevTools Protocol."""

import json
import os
import subprocess
import time
from typing import Any, Dict, List, Optional, Tuple
from urllib.request import URLError, urlopen

import websocket

from .config import config


class BrowserManager:
    """Manages browser lifecycle and control via CDP."""
    
    def __init__(self):
        """Initialize the browser manager."""
        self._process: Optional[subprocess.Popen] = None
        self._ws: Optional[websocket.WebSocket] = None
        self._msg_id: int = 0
    
    @property
    def msg_id(self) -> int:
        """Get next message ID for CDP requests."""
        self._msg_id += 1
        return self._msg_id
    
    @property
    def is_running(self) -> bool:
        """Check if browser process is running."""
        return self._process is not None and self._process.poll() is None
    
    @property
    def is_connected(self) -> bool:
        """Check if WebSocket is connected."""
        return self._ws is not None and self._ws.connected
    
    def launch(self) -> None:
        """Launch the browser in kiosk mode with remote debugging."""
        if self.is_running:
            return
        
        params = [
            f"--user-data-dir={config.browser_profile_dir}",
            f"--remote-debugging-port={config.cdp_port}",
            "--remote-allow-origins=*",
            "--no-first-run",
            "--no-default-browser-check",
            "--disable-infobars",
            "--disable-session-crashed-bubble",
            "--disable-features=TranslateUI",
        ]
        
        if config.kiosk_mode:
            params.extend([
                "--kiosk",
                "--start-fullscreen",
            ])
        
        # Start with about:blank, we'll navigate after connecting
        params.append("about:blank")
        
        dev_null = open(os.devnull, "wb")
        try:
            self._process = subprocess.Popen(
                [config.browser_path] + params,
                stdout=dev_null,
                stderr=subprocess.STDOUT,
            )
        finally:
            dev_null.close()
    
    def connect(self, timeout: float = 15.0) -> None:
        """Connect to browser via CDP WebSocket.
        
        Args:
            timeout: Maximum time to wait for connection.
            
        Raises:
            ConnectionError: If unable to connect within timeout.
        """
        start_time = time.time()
        endpoint = None
        
        while time.time() - start_time < timeout:
            try:
                data = urlopen(config.cdp_url, timeout=1).read().decode("utf-8")
                if data:
                    sessions = json.loads(data)
                    for session in sessions:
                        if session.get("type") == "page":
                            endpoint = session.get("webSocketDebuggerUrl")
                            break
                if endpoint:
                    break
            except (URLError, json.JSONDecodeError, KeyError):
                pass
            time.sleep(0.5)
        
        if not endpoint:
            raise ConnectionError("Unable to connect to browser CDP endpoint")
        
        # Set timeout on websocket so recv() doesn't block forever
        self._ws = websocket.create_connection(endpoint, timeout=5)
        
        # Enable required CDP domains
        self.ws_request("Network.enable")
        self.ws_request("Page.enable")
        self.ws_request("DOM.enable")
        
        print("CDP domains enabled")
    
    def close(self) -> None:
        """Close browser and cleanup."""
        if self._ws:
            try:
                self.ws_request("Browser.close")
            except Exception:
                pass
            try:
                self._ws.close()
            except Exception:
                pass
            self._ws = None
        
        if self._process:
            try:
                self._process.terminate()
                self._process.wait(timeout=5)
            except Exception:
                self._process.kill()
            self._process = None
    
    def ws_request(self, method: str, params: Optional[Dict] = None, timeout: float = 10.0) -> Dict[str, Any]:
        """Send a CDP request and wait for response.
        
        Args:
            method: CDP method name.
            params: Optional parameters for the method.
            timeout: Maximum time to wait for response.
            
        Returns:
            The result from the CDP response.
            
        Raises:
            TimeoutError: If no response within timeout.
            RuntimeError: If not connected.
        """
        if not self._ws:
            raise RuntimeError("Not connected to browser")
        
        req_id = self.msg_id
        message = json.dumps({
            "id": req_id,
            "method": method,
            "params": params or {},
        })
        
        self._ws.send(message)
        
        start_time = time.time()
        while time.time() - start_time < timeout:
            try:
                response = self._ws.recv()
                parsed = json.loads(response)
                if parsed.get("id") == req_id:
                    if "error" in parsed:
                        raise RuntimeError(f"CDP error: {parsed['error']}")
                    return parsed.get("result", {})
            except websocket.WebSocketTimeoutException:
                continue
        
        raise TimeoutError(f"CDP request '{method}' timed out")
    
    def ws_wait_event(self, event_name: str, timeout: float = 10.0) -> Dict[str, Any]:
        """Wait for a specific CDP event.
        
        Args:
            event_name: The event method name to wait for.
            timeout: Maximum time to wait.
            
        Returns:
            The event data.
            
        Raises:
            TimeoutError: If event not received within timeout.
        """
        if not self._ws:
            raise RuntimeError("Not connected to browser")
        
        start_time = time.time()
        while time.time() - start_time < timeout:
            try:
                message = self._ws.recv()
                parsed = json.loads(message)
                if parsed.get("method") == event_name:
                    return parsed
            except websocket.WebSocketTimeoutException:
                continue
        
        raise TimeoutError(f"CDP event '{event_name}' timed out")
    
    # Navigation methods
    
    def navigate(self, url: str, wait_for_load: bool = True, timeout: float = 30.0) -> None:
        """Navigate to a URL and optionally wait for load.
        
        Args:
            url: URL to navigate to.
            wait_for_load: Whether to wait for page load.
            timeout: Maximum time to wait for load.
        """
        print(f"Navigating to: {url}")
        result = self.ws_request("Page.navigate", {"url": url})
        
        if "errorText" in result:
            raise RuntimeError(f"Navigation failed: {result['errorText']}")
        
        if wait_for_load:
            # Wait for the page to finish loading
            try:
                self.ws_wait_event("Page.loadEventFired", timeout=timeout)
            except TimeoutError:
                # Page might still be usable even if load event times out
                print(f"Warning: Page load event timed out for {url}")
        
        print(f"Navigation complete: {url}")
    
    def get_current_url(self) -> str:
        """Get the current page URL."""
        history = self.ws_request("Page.getNavigationHistory")
        index = history.get("currentIndex", 0)
        entries = history.get("entries", [])
        if entries and index < len(entries):
            return entries[index].get("url", "")
        return ""
    
    def go_back(self) -> None:
        """Navigate back in browser history."""
        history = self.ws_request("Page.getNavigationHistory")
        index = history.get("currentIndex", 0)
        if index > 0:
            entries = history.get("entries", [])
            self.ws_request("Page.navigateToHistoryEntry", {
                "entryId": entries[index - 1]["id"]
            })
    
    # Keyboard input methods
    
    def send_key(self, key: str, code: Optional[str] = None) -> None:
        """Send a keyboard key press.
        
        Args:
            key: The key value (e.g., 'Space', 'Escape', 'f').
            code: Optional key code. Auto-generated if not provided.
        """
        if code is None:
            if len(key) == 1:
                code = f"Key{key.upper()}"
            else:
                code = key
        
        # Key down
        self.ws_request("Input.dispatchKeyEvent", {
            "type": "keyDown",
            "key": key,
            "code": code,
        })
        
        # Key up
        self.ws_request("Input.dispatchKeyEvent", {
            "type": "keyUp",
            "key": key,
            "code": code,
        })
    
    def send_text(self, text: str) -> None:
        """Send text input character by character."""
        for char in text:
            self.ws_request("Input.dispatchKeyEvent", {
                "type": "char",
                "text": char,
            })
    
    # Mouse input methods
    
    def mouse_move(self, x: int, y: int) -> None:
        """Move mouse to coordinates."""
        self.ws_request("Input.dispatchMouseEvent", {
            "type": "mouseMoved",
            "x": x,
            "y": y,
        })
    
    def mouse_click(self, x: int, y: int, button: str = "left") -> None:
        """Click at coordinates.
        
        Args:
            x: X coordinate.
            y: Y coordinate.
            button: Mouse button ('left', 'right', 'middle').
        """
        # Move to position
        self.mouse_move(x, y)
        
        # Press
        self.ws_request("Input.dispatchMouseEvent", {
            "type": "mousePressed",
            "x": x,
            "y": y,
            "button": button,
            "clickCount": 1,
        })
        
        # Release
        self.ws_request("Input.dispatchMouseEvent", {
            "type": "mouseReleased",
            "x": x,
            "y": y,
            "button": button,
            "clickCount": 1,
        })
    
    # DOM query methods
    
    def get_document(self) -> Dict[str, Any]:
        """Get the document root node."""
        return self.ws_request("DOM.getDocument")
    
    def query_selector(self, selector: str, node_id: Optional[int] = None) -> Optional[int]:
        """Query for an element by CSS selector.
        
        Args:
            selector: CSS selector string.
            node_id: Optional parent node ID. Uses document root if not provided.
            
        Returns:
            Node ID of found element, or None if not found.
        """
        if node_id is None:
            doc = self.get_document()
            node_id = doc["root"]["nodeId"]
        
        try:
            result = self.ws_request("DOM.querySelector", {
                "nodeId": node_id,
                "selector": selector,
            })
            found_id = result.get("nodeId", 0)
            return found_id if found_id > 0 else None
        except RuntimeError:
            return None
    
    def query_selector_all(self, selector: str, node_id: Optional[int] = None) -> List[int]:
        """Query for all elements matching CSS selector.
        
        Args:
            selector: CSS selector string.
            node_id: Optional parent node ID. Uses document root if not provided.
            
        Returns:
            List of node IDs for found elements.
        """
        if node_id is None:
            doc = self.get_document()
            node_id = doc["root"]["nodeId"]
        
        try:
            result = self.ws_request("DOM.querySelectorAll", {
                "nodeId": node_id,
                "selector": selector,
            })
            return result.get("nodeIds", [])
        except RuntimeError:
            return []
    
    def get_box_model(self, node_id: int) -> Optional[Dict[str, Any]]:
        """Get the box model for an element.
        
        Args:
            node_id: The DOM node ID.
            
        Returns:
            Box model data with content, padding, border, margin quads.
        """
        try:
            result = self.ws_request("DOM.getBoxModel", {"nodeId": node_id})
            return result.get("model")
        except RuntimeError:
            return None
    
    def get_element_center(self, node_id: int) -> Optional[Tuple[int, int]]:
        """Get the center coordinates of an element.
        
        Args:
            node_id: The DOM node ID.
            
        Returns:
            Tuple of (x, y) center coordinates, or None if not found.
        """
        box = self.get_box_model(node_id)
        if not box:
            return None
        
        # Content quad is [x1, y1, x2, y2, x3, y3, x4, y4]
        content = box.get("content", [])
        if len(content) < 8:
            return None
        
        # Calculate center from quad points
        x = int((content[0] + content[2] + content[4] + content[6]) / 4)
        y = int((content[1] + content[3] + content[5] + content[7]) / 4)
        return (x, y)
    
    def click_element(self, selector: str) -> bool:
        """Find an element by selector and click it.
        
        Args:
            selector: CSS selector for the element.
            
        Returns:
            True if element was found and clicked, False otherwise.
        """
        node_id = self.query_selector(selector)
        if not node_id:
            return False
        
        center = self.get_element_center(node_id)
        if not center:
            return False
        
        self.mouse_click(center[0], center[1])
        return True
    
    def execute_script(self, script: str) -> Any:
        """Execute JavaScript in the page context.
        
        Args:
            script: JavaScript code to execute.
            
        Returns:
            The result value from the script.
        """
        result = self.ws_request("Runtime.evaluate", {
            "expression": script,
            "returnByValue": True,
        })
        return result.get("result", {}).get("value")
    
    def get_page_html(self) -> str:
        """Get the full HTML of the current page."""
        return self.execute_script("document.documentElement.outerHTML") or ""
    
    # Cookie methods
    
    def get_all_cookies(self) -> List[Dict[str, Any]]:
        """Get all browser cookies."""
        result = self.ws_request("Network.getAllCookies")
        return result.get("cookies", [])
    
    def set_cookies(self, cookies: List[Dict[str, Any]]) -> None:
        """Set cookies in the browser.
        
        Args:
            cookies: List of cookie objects with name, value, domain, etc.
        """
        self.ws_request("Network.setCookies", {"cookies": cookies})
    
    def clear_cookies(self) -> None:
        """Clear all browser cookies."""
        self.ws_request("Network.clearBrowserCookies")
