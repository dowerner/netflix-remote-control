# -*- coding: utf-8 -*-
"""Configuration management for Netflix Control."""

import os
import platform
import subprocess
from dataclasses import dataclass, field
from pathlib import Path
from typing import Optional


@dataclass
class Config:
    """Application configuration."""
    
    # CDP settings
    cdp_port: int = 9222
    cdp_host: str = "127.0.0.1"
    
    # API settings
    api_host: str = "0.0.0.0"
    api_port: int = 8080
    
    # Browser settings
    browser_path: Optional[str] = None
    kiosk_mode: bool = True
    
    # Data paths
    data_dir: Path = field(default_factory=lambda: Path.home() / ".netflix-control")
    
    # Netflix URLs
    netflix_login_url: str = "https://www.netflix.com/login"
    netflix_browse_url: str = "https://www.netflix.com/browse"
    
    def __post_init__(self):
        """Initialize paths and detect browser."""
        if self.browser_path is None:
            self.browser_path = detect_browser_path()
        
        self.data_dir = Path(self.data_dir)
        self.data_dir.mkdir(parents=True, exist_ok=True)
        
        # Determine browser profile directory based on browser type
        # Snap Chromium requires profile in ~/snap/chromium/common/ due to sandboxing
        self.browser_profile_dir = self._get_browser_profile_dir()
        self.browser_profile_dir.mkdir(parents=True, exist_ok=True)
        
        self.cookies_file = self.data_dir / "cookies.json"
    
    def _get_browser_profile_dir(self) -> Path:
        """Get appropriate browser profile directory.
        
        Snap packages have sandboxing restrictions and can only write
        to specific directories like ~/snap/<app>/common/
        """
        if self.browser_path and is_snap_browser(self.browser_path):
            # Use snap-compatible directory
            snap_data_dir = Path.home() / "snap" / "chromium" / "common" / "netflix-control"
            snap_data_dir.mkdir(parents=True, exist_ok=True)
            return snap_data_dir / "browser_profile"
        else:
            return self.data_dir / "browser_profile"
    
    @property
    def cdp_url(self) -> str:
        """Get the CDP JSON endpoint URL."""
        return f"http://{self.cdp_host}:{self.cdp_port}/json"


def is_snap_browser(browser_path: str) -> bool:
    """Check if the browser is installed as a snap package.
    
    Args:
        browser_path: Path to the browser executable.
        
    Returns:
        True if the browser is a snap package.
    """
    # Direct snap path
    if "/snap/" in browser_path:
        return True
    
    # Check if it's a wrapper script for snap chromium
    # Common on Ubuntu where /usr/bin/chromium-browser wraps snap
    if "chromium" in browser_path.lower():
        snap_chromium = Path("/snap/bin/chromium")
        if snap_chromium.exists():
            # Check if the browser_path is a shell script wrapper
            browser_file = Path(browser_path)
            if browser_file.exists() and browser_file.stat().st_size < 10000:
                try:
                    content = browser_file.read_text()
                    if "/snap/bin/chromium" in content or "snap install chromium" in content:
                        return True
                except (OSError, UnicodeDecodeError):
                    pass
    
    return False


def detect_browser_path() -> str:
    """Detect installed Chromium-based browser path.
    
    Prefers non-snap versions when available to avoid sandboxing issues.
    
    Returns:
        Path to the browser executable.
        
    Raises:
        RuntimeError: If no supported browser is found.
    """
    system = platform.system().lower()
    
    if system == "darwin":  # macOS
        browser_candidates = [
            "/Applications/Google Chrome.app/Contents/MacOS/Google Chrome",
            "/Applications/Chromium.app/Contents/MacOS/Chromium",
            "/Applications/Brave Browser.app/Contents/MacOS/Brave Browser",
        ]
        for path in browser_candidates:
            if os.path.exists(path):
                return path
    else:  # Linux
        # Prefer non-snap versions first to avoid sandboxing issues
        browser_names = [
            "google-chrome",
            "google-chrome-stable",
            "google-chrome-unstable",
            "brave-browser",
            "chromium",
            "chromium-browser",
        ]
        
        found_paths = []
        for name in browser_names:
            try:
                path = subprocess.check_output(
                    ["which", name], stderr=subprocess.DEVNULL
                ).decode("utf-8").strip()
                if path:
                    found_paths.append(path)
            except subprocess.CalledProcessError:
                pass
        
        # Prefer non-snap browsers
        for path in found_paths:
            if not is_snap_browser(path):
                return path
        
        # Fall back to snap if that's all we have
        if found_paths:
            return found_paths[0]
    
    raise RuntimeError(
        "No supported browser found. Please install Chrome, Chromium, or Brave, "
        "or specify the browser path in configuration."
    )


# Global config instance
config = Config()
