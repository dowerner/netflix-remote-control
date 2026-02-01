# -*- coding: utf-8 -*-
"""Authentication manager for Netflix session handling."""

import base64
import json
import time
from datetime import datetime, timedelta
from pathlib import Path
from typing import TYPE_CHECKING, Any, Dict, List, Optional

try:
    from Cryptodome.Cipher import AES
    from Cryptodome.Util import Padding
except ImportError:
    from Crypto.Cipher import AES
    from Crypto.Util import Padding

from .config import config

if TYPE_CHECKING:
    from .browser import BrowserManager


# Required Netflix cookies for authentication
REQUIRED_COOKIES = ["nfvdid", "SecureNetflixId", "NetflixId"]


class AuthManager:
    """Manages Netflix authentication and session persistence."""
    
    def __init__(self, browser: "BrowserManager"):
        """Initialize the auth manager.
        
        Args:
            browser: BrowserManager instance for cookie operations.
        """
        self.browser = browser
        self._pin: Optional[int] = None
    
    @property
    def cookies_file(self) -> Path:
        """Get the cookies storage file path."""
        return config.cookies_file
    
    def has_stored_session(self) -> bool:
        """Check if a stored session file exists."""
        return self.cookies_file.exists()
    
    def is_logged_in(self) -> bool:
        """Check if currently logged in by checking URL.
        
        Returns:
            True if on browse page (logged in), False otherwise.
        """
        url = self.browser.get_current_url()
        return "/browse" in url and "/login" not in url
    
    def validate_cookies(self, cookies: List[Dict[str, Any]]) -> bool:
        """Validate that required Netflix cookies are present.
        
        Args:
            cookies: List of cookie dictionaries.
            
        Returns:
            True if all required cookies are present.
        """
        cookie_names = {c.get("name") for c in cookies}
        return all(name in cookie_names for name in REQUIRED_COOKIES)
    
    def load_session(self, pin: Optional[int] = None) -> bool:
        """Load stored session cookies and inject into browser.
        
        Args:
            pin: PIN to decrypt cookies. If None, uses stored PIN.
            
        Returns:
            True if session was loaded successfully.
        """
        if not self.has_stored_session():
            return False
        
        try:
            data = self._load_encrypted_data(pin)
            if not data:
                return False
            
            cookies = data.get("data", {}).get("cookies", [])
            if not self.validate_cookies(cookies):
                return False
            
            # Check expiry
            timestamp = data.get("timestamp", 0)
            if timestamp < int(time.time()):
                return False
            
            # Inject cookies
            self.browser.set_cookies(cookies)
            return True
            
        except Exception:
            return False
    
    def save_session(self, pin: Optional[int] = None) -> int:
        """Capture and save current session cookies.
        
        Args:
            pin: PIN to encrypt cookies. If None, generates random PIN.
            
        Returns:
            The PIN used for encryption.
            
        Raises:
            ValueError: If required cookies are not present.
        """
        cookies = self.browser.get_all_cookies()
        
        if not self.validate_cookies(cookies):
            raise ValueError("Required Netflix cookies not found. Login may have failed.")
        
        # Generate PIN if not provided
        if pin is None:
            import random
            pin = random.randint(1000, 9999)
        
        self._pin = pin
        
        # Create data structure
        data = {
            "app_name": "NetflixControl",
            "app_version": "0.1.0",
            "timestamp": int((datetime.utcnow() + timedelta(days=30)).timestamp()),
            "data": {
                "cookies": cookies
            }
        }
        
        self._save_encrypted_data(data, pin)
        return pin
    
    def clear_session(self) -> None:
        """Clear stored session and browser cookies."""
        if self.cookies_file.exists():
            self.cookies_file.unlink()
        self.browser.clear_cookies()
    
    def wait_for_login(self, timeout: float = 300.0) -> bool:
        """Wait for user to complete login.
        
        Args:
            timeout: Maximum time to wait in seconds (default 5 minutes).
            
        Returns:
            True if login completed, False if timeout.
        """
        start_time = time.time()
        
        while time.time() - start_time < timeout:
            time.sleep(1)
            
            try:
                url = self.browser.get_current_url()
                # User has logged in when redirected to browse page
                if "/browse" in url and "/login" not in url:
                    # Wait a moment for cookies to be fully set
                    time.sleep(2)
                    return True
            except Exception:
                pass
        
        return False
    
    def initiate_login(self) -> None:
        """Navigate to Netflix login page."""
        self.browser.navigate(config.netflix_login_url)
    
    def navigate_to_browse(self) -> None:
        """Navigate to Netflix browse page."""
        self.browser.navigate(config.netflix_browse_url)
    
    def _save_encrypted_data(self, data: Dict[str, Any], pin: int) -> None:
        """Save data encrypted with PIN.
        
        Args:
            data: Data dictionary to encrypt and save.
            pin: 4-digit PIN for encryption key.
        """
        # Create 16-byte key from PIN (repeat to fill)
        key = (str(pin) * 4).encode("utf-8")[:16]
        iv = b"\x00" * 16
        
        # Pad and encrypt
        json_data = json.dumps(data).encode("utf-8")
        padded = Padding.pad(json_data, 16)
        
        cipher = AES.new(key, AES.MODE_CBC, iv)
        encrypted = cipher.encrypt(padded)
        
        # Save as base64
        encoded = base64.b64encode(encrypted).decode("utf-8")
        self.cookies_file.write_text(encoded)
    
    def _load_encrypted_data(self, pin: Optional[int] = None) -> Optional[Dict[str, Any]]:
        """Load and decrypt stored data.
        
        Args:
            pin: PIN for decryption. If None, tries stored PIN.
            
        Returns:
            Decrypted data dictionary or None if decryption fails.
        """
        if pin is None:
            pin = self._pin
        if pin is None:
            # Try default PIN or prompt would be needed
            return None
        
        try:
            encoded = self.cookies_file.read_text()
            encrypted = base64.b64decode(encoded)
            
            # Create 16-byte key from PIN
            key = (str(pin) * 4).encode("utf-8")[:16]
            iv = b"\x00" * 16
            
            cipher = AES.new(key, AES.MODE_CBC, iv)
            decrypted = cipher.decrypt(encrypted)
            unpadded = Padding.unpad(decrypted, 16)
            
            return json.loads(unpadded.decode("utf-8"))
            
        except Exception:
            return None
    
    def get_stored_pin(self) -> Optional[int]:
        """Get the PIN used for the current session.
        
        Returns:
            The PIN if known, None otherwise.
        """
        return self._pin
    
    def set_pin(self, pin: int) -> None:
        """Set the PIN for session operations.
        
        Args:
            pin: 4-digit PIN.
        """
        self._pin = pin
