# -*- coding: utf-8 -*-
"""Navigation state management for Netflix UI."""

from dataclasses import dataclass, field
from enum import Enum
from typing import TYPE_CHECKING, Dict, List, Optional, Tuple

if TYPE_CHECKING:
    from .browser import BrowserManager


class PageContext(Enum):
    """Netflix page context types."""
    UNKNOWN = "unknown"
    LOGIN = "login"
    PROFILE_SELECT = "profile_select"
    BROWSE = "browse"
    SEARCH = "search"
    TITLE_DETAIL = "title_detail"
    PLAYER = "player"


@dataclass
class UIElement:
    """Represents a discoverable UI element."""
    node_id: int
    selector: str
    x: int
    y: int
    width: int
    height: int
    row: int = 0
    col: int = 0
    
    @property
    def center(self) -> Tuple[int, int]:
        """Get center coordinates."""
        return (self.x + self.width // 2, self.y + self.height // 2)


@dataclass
class NavigationState:
    """Tracks navigation state and focus position."""
    
    context: PageContext = PageContext.UNKNOWN
    elements: List[UIElement] = field(default_factory=list)
    rows: Dict[int, List[UIElement]] = field(default_factory=dict)
    focus_row: int = 0
    focus_col: int = 0
    
    # Netflix-specific selectors for different contexts
    SELECTORS = {
        PageContext.BROWSE: {
            "rows": ".lolomoRow",
            "items": ".slider-item, .title-card-container",
            "nav_items": "[data-uia='navigation-tab']",
        },
        PageContext.PROFILE_SELECT: {
            "profiles": ".profile-gate-container .profile-icon, .choose-profile .profile-icon",
        },
        PageContext.PLAYER: {
            "play_pause": "[data-uia='control-play-pause-pause'], [data-uia='control-play-pause-play']",
            "back": "[data-uia='control-nav-back']",
            "forward": "[data-uia='control-forward10']",
            "rewind": "[data-uia='control-back10']",
            "fullscreen": "[data-uia='control-fullscreen-enter'], [data-uia='control-fullscreen-exit']",
            "volume": "[data-uia='control-volume-high'], [data-uia='control-volume-medium'], [data-uia='control-volume-low'], [data-uia='control-volume-off']",
        },
        PageContext.TITLE_DETAIL: {
            "play_button": "[data-uia='play-button'], [data-uia='hero-title-card-play-button']",
            "close": "[data-uia='previewModal--closebtn']",
        },
    }
    
    def detect_context(self, browser: "BrowserManager") -> PageContext:
        """Detect current page context from URL and DOM.
        
        Args:
            browser: BrowserManager instance for DOM queries.
            
        Returns:
            Detected PageContext.
        """
        url = browser.get_current_url()
        
        if "/login" in url:
            self.context = PageContext.LOGIN
        elif "/browse" in url or url.endswith("netflix.com/"):
            # Check for profile gate
            if browser.query_selector(".profile-gate-container, .choose-profile"):
                self.context = PageContext.PROFILE_SELECT
            else:
                self.context = PageContext.BROWSE
        elif "/search" in url:
            self.context = PageContext.SEARCH
        elif "/watch/" in url:
            self.context = PageContext.PLAYER
        elif "/title/" in url:
            self.context = PageContext.TITLE_DETAIL
        else:
            # Check for player overlay
            if browser.query_selector("[data-uia='player']"):
                self.context = PageContext.PLAYER
            elif browser.query_selector(".previewModal--container"):
                self.context = PageContext.TITLE_DETAIL
            else:
                self.context = PageContext.BROWSE
        
        return self.context
    
    def discover_elements(self, browser: "BrowserManager") -> List[UIElement]:
        """Discover interactive elements based on current context.
        
        Args:
            browser: BrowserManager instance for DOM queries.
            
        Returns:
            List of discovered UIElements.
        """
        self.detect_context(browser)
        self.elements = []
        self.rows = {}
        
        if self.context == PageContext.PROFILE_SELECT:
            self._discover_profile_elements(browser)
        elif self.context == PageContext.BROWSE:
            self._discover_browse_elements(browser)
        elif self.context == PageContext.PLAYER:
            self._discover_player_elements(browser)
        elif self.context == PageContext.TITLE_DETAIL:
            self._discover_detail_elements(browser)
        
        return self.elements
    
    def _discover_profile_elements(self, browser: "BrowserManager") -> None:
        """Discover profile selection elements."""
        selectors = self.SELECTORS[PageContext.PROFILE_SELECT]
        node_ids = browser.query_selector_all(selectors["profiles"])
        
        for col, node_id in enumerate(node_ids):
            element = self._create_element(browser, node_id, selectors["profiles"], row=0, col=col)
            if element:
                self.elements.append(element)
                if 0 not in self.rows:
                    self.rows[0] = []
                self.rows[0].append(element)
    
    def _discover_browse_elements(self, browser: "BrowserManager") -> None:
        """Discover browse page elements (content rows and tiles)."""
        selectors = self.SELECTORS[PageContext.BROWSE]
        
        # Find all content rows
        row_node_ids = browser.query_selector_all(selectors["rows"])
        
        for row_idx, row_node_id in enumerate(row_node_ids):
            if row_idx not in self.rows:
                self.rows[row_idx] = []
            
            # Find items within this row
            item_node_ids = browser.query_selector_all(selectors["items"], row_node_id)
            
            for col_idx, node_id in enumerate(item_node_ids):
                element = self._create_element(
                    browser, node_id, selectors["items"],
                    row=row_idx, col=col_idx
                )
                if element:
                    self.elements.append(element)
                    self.rows[row_idx].append(element)
    
    def _discover_player_elements(self, browser: "BrowserManager") -> None:
        """Discover video player control elements."""
        selectors = self.SELECTORS[PageContext.PLAYER]
        col = 0
        
        for name, selector in selectors.items():
            node_id = browser.query_selector(selector)
            if node_id:
                element = self._create_element(browser, node_id, selector, row=0, col=col)
                if element:
                    self.elements.append(element)
                    if 0 not in self.rows:
                        self.rows[0] = []
                    self.rows[0].append(element)
                    col += 1
    
    def _discover_detail_elements(self, browser: "BrowserManager") -> None:
        """Discover title detail modal elements."""
        selectors = self.SELECTORS[PageContext.TITLE_DETAIL]
        col = 0
        
        for name, selector in selectors.items():
            node_id = browser.query_selector(selector)
            if node_id:
                element = self._create_element(browser, node_id, selector, row=0, col=col)
                if element:
                    self.elements.append(element)
                    if 0 not in self.rows:
                        self.rows[0] = []
                    self.rows[0].append(element)
                    col += 1
    
    def _create_element(
        self,
        browser: "BrowserManager",
        node_id: int,
        selector: str,
        row: int = 0,
        col: int = 0
    ) -> Optional[UIElement]:
        """Create a UIElement from a node ID.
        
        Args:
            browser: BrowserManager instance.
            node_id: DOM node ID.
            selector: CSS selector used to find element.
            row: Row index.
            col: Column index.
            
        Returns:
            UIElement or None if box model unavailable.
        """
        box = browser.get_box_model(node_id)
        if not box:
            return None
        
        content = box.get("content", [])
        if len(content) < 8:
            return None
        
        # Calculate bounding box from quad
        x = int(min(content[0], content[2], content[4], content[6]))
        y = int(min(content[1], content[3], content[5], content[7]))
        x2 = int(max(content[0], content[2], content[4], content[6]))
        y2 = int(max(content[1], content[3], content[5], content[7]))
        
        return UIElement(
            node_id=node_id,
            selector=selector,
            x=x,
            y=y,
            width=x2 - x,
            height=y2 - y,
            row=row,
            col=col,
        )
    
    def get_focused_element(self) -> Optional[UIElement]:
        """Get the currently focused element.
        
        Returns:
            The focused UIElement or None.
        """
        if self.focus_row in self.rows:
            row_elements = self.rows[self.focus_row]
            if 0 <= self.focus_col < len(row_elements):
                return row_elements[self.focus_col]
        return None
    
    def navigate(self, direction: str) -> Optional[UIElement]:
        """Navigate focus in a direction.
        
        Args:
            direction: One of 'up', 'down', 'left', 'right'.
            
        Returns:
            The newly focused UIElement or None.
        """
        if not self.rows:
            return None
        
        row_indices = sorted(self.rows.keys())
        
        if direction == "up":
            current_idx = row_indices.index(self.focus_row) if self.focus_row in row_indices else 0
            if current_idx > 0:
                self.focus_row = row_indices[current_idx - 1]
                # Clamp column to row length
                row_len = len(self.rows.get(self.focus_row, []))
                self.focus_col = min(self.focus_col, row_len - 1) if row_len > 0 else 0
        
        elif direction == "down":
            current_idx = row_indices.index(self.focus_row) if self.focus_row in row_indices else 0
            if current_idx < len(row_indices) - 1:
                self.focus_row = row_indices[current_idx + 1]
                # Clamp column to row length
                row_len = len(self.rows.get(self.focus_row, []))
                self.focus_col = min(self.focus_col, row_len - 1) if row_len > 0 else 0
        
        elif direction == "left":
            if self.focus_col > 0:
                self.focus_col -= 1
        
        elif direction == "right":
            row_len = len(self.rows.get(self.focus_row, []))
            if self.focus_col < row_len - 1:
                self.focus_col += 1
        
        return self.get_focused_element()
    
    def reset_focus(self) -> None:
        """Reset focus to first element."""
        self.focus_row = 0
        self.focus_col = 0
