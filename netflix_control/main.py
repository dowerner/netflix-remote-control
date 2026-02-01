# -*- coding: utf-8 -*-
"""Main entry point and orchestration for Netflix Control."""

import argparse
import signal
import sys
import threading
import time
from typing import Optional

import uvicorn

from .api import create_api
from .auth import AuthManager
from .browser import BrowserManager
from .config import config
from .navigation import NavigationState


class NetflixControl:
    """Main application controller."""
    
    def __init__(self):
        """Initialize the application."""
        self.browser = BrowserManager()
        self.auth = AuthManager(self.browser)
        self.nav_state = NavigationState()
        self.api = create_api(self.browser, self.auth, self.nav_state)
        self._shutdown_event = threading.Event()
        self._api_thread: Optional[threading.Thread] = None
        self._monitor_thread: Optional[threading.Thread] = None
    
    def start(self, pin: Optional[int] = None, skip_login: bool = False) -> None:
        """Start the application.
        
        Args:
            pin: Optional PIN for loading stored session.
            skip_login: If True, skip automatic login handling.
        """
        # Setup signal handlers
        signal.signal(signal.SIGINT, self._signal_handler)
        signal.signal(signal.SIGTERM, self._signal_handler)
        
        print("Netflix Control starting...")
        
        # Launch browser
        print("Launching browser...")
        self.browser.launch()
        
        # Connect to browser
        print("Connecting to browser via CDP...")
        self.browser.connect()
        print("Connected to browser")
        
        # Handle authentication
        if skip_login:
            print("Skipping login handling (--skip-login flag)")
        else:
            self._handle_auth(pin)
        
        # Start API server in background thread
        print(f"Starting API server on {config.api_host}:{config.api_port}...")
        self._start_api_server()
        
        # Inject JS navigation controller and discover elements
        print("Injecting navigation controller...")
        time.sleep(2)  # Wait for page to stabilize
        self._inject_navigation()
        
        # Start browser monitor to detect if browser is closed
        self._start_browser_monitor()
        
        print("\nNetflix Control is ready!")
        print(f"API available at: http://{config.api_host}:{config.api_port}")
        print("Press Ctrl+C to exit\n")
        
        # Wait for shutdown
        self._shutdown_event.wait()
    
    def _handle_auth(self, pin: Optional[int] = None) -> None:
        """Handle authentication flow.
        
        Args:
            pin: Optional PIN for stored session.
        """
        print("Starting authentication handling...")
        
        # Check for stored session
        if self.auth.has_stored_session() and pin is not None:
            print("Loading stored session...")
            self.auth.set_pin(pin)
            if self.auth.load_session(pin):
                print("Session loaded successfully")
                self.auth.navigate_to_browse()
                return
            else:
                print("Failed to load stored session (invalid PIN or expired)")
        
        # Check if already logged in (browser profile may have session)
        print(f"Checking for existing session by navigating to {config.netflix_browse_url}...")
        try:
            self.browser.navigate(config.netflix_browse_url)
        except Exception as e:
            print(f"Warning: Navigation error: {e}")
        
        time.sleep(2)
        
        current_url = self.browser.get_current_url()
        print(f"Current URL after navigation: {current_url}")
        
        if self.auth.is_logged_in():
            print("Already logged in via browser profile")
            # Inject navigation controller
            self._inject_navigation()
            return
        
        # Need to login
        print("\nNo valid session found. Please login manually.")
        print("Navigating to Netflix login page...")
        self.auth.initiate_login()
        
        print("Waiting for login (timeout: 5 minutes)...")
        if self.auth.wait_for_login(timeout=300):
            print("Login successful!")
            
            # Inject navigation controller after login
            time.sleep(2)  # Wait for browse page to load
            self._inject_navigation()
            
            # Offer to save session
            try:
                pin = self.auth.save_session()
                print(f"Session saved! Your PIN is: {pin}")
                print("Use this PIN to restore your session next time.")
            except Exception as e:
                print(f"Warning: Could not save session: {e}")
        else:
            print("Login timeout. You can login later via the API.")
    
    def _inject_navigation(self) -> None:
        """Inject the JavaScript navigation controller into the page."""
        try:
            result = self.browser.inject_nav_controller()
            if result.get("success"):
                print(f"Navigation controller ready - found {result.get('elementCount', 0)} elements")
            else:
                print(f"Warning: Navigation controller injection returned: {result}")
        except Exception as e:
            print(f"Warning: Could not inject navigation controller: {e}")
            # Fall back to legacy discovery
            print("Falling back to legacy element discovery...")
            self.nav_state.discover_elements(self.browser)
            print(f"Found {len(self.nav_state.elements)} elements (legacy)")
    
    def _start_api_server(self) -> None:
        """Start the API server in a background thread."""
        uvicorn_config = uvicorn.Config(
            self.api,
            host=config.api_host,
            port=config.api_port,
            log_level="warning",
        )
        server = uvicorn.Server(uvicorn_config)
        
        self._api_thread = threading.Thread(target=server.run, daemon=True)
        self._api_thread.start()
    
    def _start_browser_monitor(self) -> None:
        """Start the browser monitoring thread."""
        self._monitor_thread = threading.Thread(target=self._monitor_browser, daemon=True)
        self._monitor_thread.start()
    
    def _monitor_browser(self) -> None:
        """Wait for browser process to exit and trigger shutdown.
        
        This runs in a background thread and blocks until the browser process
        terminates. When it does (user closes window, crash, etc.), it triggers
        application shutdown.
        """
        self.browser.wait_for_exit()
        if not self._shutdown_event.is_set():
            print("\nBrowser closed - shutting down application...")
            self.stop()
    
    def _signal_handler(self, signum, frame) -> None:
        """Handle shutdown signals."""
        print("\nShutting down...")
        self.stop()
    
    def stop(self) -> None:
        """Stop the application and cleanup."""
        self._shutdown_event.set()
        
        try:
            print("Closing browser...")
            self.browser.close()
        except Exception as e:
            print(f"Error closing browser: {e}")
        
        print("Goodbye!")


def parse_args():
    """Parse command line arguments."""
    parser = argparse.ArgumentParser(
        description="Netflix Control - Kiosk browser with remote control API"
    )
    
    parser.add_argument(
        "--pin",
        type=int,
        help="PIN to load stored session"
    )
    
    parser.add_argument(
        "--port",
        type=int,
        default=8080,
        help="API server port (default: 8080)"
    )
    
    parser.add_argument(
        "--host",
        type=str,
        default="0.0.0.0",
        help="API server host (default: 0.0.0.0)"
    )
    
    parser.add_argument(
        "--no-kiosk",
        action="store_true",
        help="Disable kiosk mode (useful for debugging)"
    )
    
    parser.add_argument(
        "--skip-login",
        action="store_true",
        help="Skip automatic login handling"
    )
    
    parser.add_argument(
        "--browser",
        type=str,
        help="Path to browser executable"
    )
    
    return parser.parse_args()


def run():
    """Main entry point."""
    args = parse_args()
    
    # Apply CLI arguments to config
    config.api_port = args.port
    config.api_host = args.host
    config.kiosk_mode = not args.no_kiosk
    
    if args.browser:
        config.browser_path = args.browser
    
    # Create and start application
    app = NetflixControl()
    
    try:
        app.start(pin=args.pin, skip_login=args.skip_login)
    except KeyboardInterrupt:
        pass
    except Exception as e:
        print(f"Error: {e}")
        sys.exit(1)
    finally:
        app.stop()


if __name__ == "__main__":
    run()
