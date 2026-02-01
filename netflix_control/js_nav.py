# -*- coding: utf-8 -*-
"""JavaScript-based navigation controller for Netflix UI.

This module provides a more reliable navigation system than mouse simulation
by injecting JavaScript directly into the Netflix page context.
"""

# JavaScript navigation controller to be injected into the page
NAV_CONTROLLER_SCRIPT = """
(function() {
    // Prevent re-initialization
    if (window.NetflixNav && window.NetflixNav.initialized) {
        return window.NetflixNav;
    }

    window.NetflixNav = {
        initialized: true,
        focusedElement: null,
        overlay: null,
        elements: [],
        rows: [],
        currentRow: 0,
        currentCol: 0,

        // Netflix red color for the focus overlay
        FOCUS_COLOR: '#E50914',

        // Selectors for different Netflix UI elements
        SELECTORS: {
            // Browse page content tiles
            tiles: '.title-card-container, .slider-item, .boxart-container',
            // Profile selection
            profiles: '.profile-icon, .profile-link, [data-uia="profile-link"]',
            // Navigation items
            navItems: '[data-uia="navigation-tab"], .navigation-tab',
            // Buttons with data-uia attributes
            buttons: '[data-uia*="button"], [data-uia*="play"], [data-uia*="modal"]',
            // Interactive elements in modals
            modalItems: '.previewModal--container button, .previewModal--container a',
            // Player controls
            playerControls: '[data-uia^="control-"]',
        },

        init() {
            this.createOverlay();
            this.discover();
            console.log('[NetflixNav] Initialized with', this.elements.length, 'elements');
            return { success: true, elementCount: this.elements.length };
        },

        createOverlay() {
            // Remove existing overlay if any
            const existing = document.getElementById('netflix-nav-overlay');
            if (existing) existing.remove();

            // Create focus overlay element
            this.overlay = document.createElement('div');
            this.overlay.id = 'netflix-nav-overlay';
            this.overlay.style.cssText = `
                position: fixed;
                pointer-events: none;
                border: 3px solid ${this.FOCUS_COLOR};
                border-radius: 4px;
                box-shadow: 0 0 20px ${this.FOCUS_COLOR}80, inset 0 0 20px ${this.FOCUS_COLOR}20;
                transition: all 0.15s ease-out;
                z-index: 999999;
                display: none;
            `;
            document.body.appendChild(this.overlay);
        },

        discover() {
            this.elements = [];
            this.rows = [];

            // Detect page context
            const url = window.location.href;
            let selectors = [];

            if (url.includes('/browse') || url.endsWith('netflix.com/')) {
                // Check for profile gate
                const profileGate = document.querySelector('.profile-gate-container, .choose-profile, [data-uia="profile-gate"]');
                if (profileGate) {
                    selectors = [this.SELECTORS.profiles];
                } else {
                    selectors = [this.SELECTORS.tiles, this.SELECTORS.navItems, this.SELECTORS.buttons];
                }
            } else if (url.includes('/watch/')) {
                selectors = [this.SELECTORS.playerControls];
            } else if (url.includes('/search')) {
                selectors = [this.SELECTORS.tiles, this.SELECTORS.buttons];
            } else {
                // Generic - try all
                selectors = [this.SELECTORS.tiles, this.SELECTORS.profiles, this.SELECTORS.buttons, this.SELECTORS.modalItems];
            }

            // Check for modal overlay
            const modal = document.querySelector('.previewModal--container, [data-uia="modal"]');
            if (modal) {
                selectors = [this.SELECTORS.modalItems, this.SELECTORS.buttons];
            }

            // Find all matching elements
            const allElements = [];
            selectors.forEach(selector => {
                try {
                    const found = document.querySelectorAll(selector);
                    found.forEach(el => {
                        // Only include visible elements
                        const rect = el.getBoundingClientRect();
                        if (rect.width > 0 && rect.height > 0 && rect.top < window.innerHeight && rect.bottom > 0) {
                            allElements.push({
                                element: el,
                                rect: rect,
                                y: Math.round(rect.top),
                                x: Math.round(rect.left)
                            });
                        }
                    });
                } catch (e) {
                    console.warn('[NetflixNav] Selector error:', selector, e);
                }
            });

            // Remove duplicates (same element matched by multiple selectors)
            const seen = new Set();
            const uniqueElements = allElements.filter(item => {
                if (seen.has(item.element)) return false;
                seen.add(item.element);
                return true;
            });

            // Sort by position and group into rows
            uniqueElements.sort((a, b) => a.y - b.y || a.x - b.x);

            // Group elements into rows (elements within 50px vertical distance)
            let currentRowY = -1000;
            let currentRowElements = [];
            const ROW_THRESHOLD = 50;

            uniqueElements.forEach(item => {
                if (Math.abs(item.y - currentRowY) > ROW_THRESHOLD) {
                    // New row
                    if (currentRowElements.length > 0) {
                        // Sort current row by x position
                        currentRowElements.sort((a, b) => a.x - b.x);
                        this.rows.push(currentRowElements);
                    }
                    currentRowElements = [item];
                    currentRowY = item.y;
                } else {
                    currentRowElements.push(item);
                }
            });

            // Don't forget the last row
            if (currentRowElements.length > 0) {
                currentRowElements.sort((a, b) => a.x - b.x);
                this.rows.push(currentRowElements);
            }

            // Flatten for easy access
            this.elements = this.rows.flat();

            // Reset position if needed
            if (this.currentRow >= this.rows.length) this.currentRow = 0;
            if (this.rows.length > 0 && this.currentCol >= this.rows[this.currentRow].length) {
                this.currentCol = 0;
            }

            // Update focus
            this.updateFocus();

            return {
                success: true,
                elementCount: this.elements.length,
                rowCount: this.rows.length
            };
        },

        navigate(direction) {
            if (this.rows.length === 0) {
                this.discover();
                if (this.rows.length === 0) {
                    return { success: false, message: 'No elements found' };
                }
            }

            const prevRow = this.currentRow;
            const prevCol = this.currentCol;

            switch (direction) {
                case 'up':
                    if (this.currentRow > 0) {
                        this.currentRow--;
                        // Clamp column to new row length
                        const rowLen = this.rows[this.currentRow].length;
                        this.currentCol = Math.min(this.currentCol, rowLen - 1);
                    }
                    break;

                case 'down':
                    if (this.currentRow < this.rows.length - 1) {
                        this.currentRow++;
                        // Clamp column to new row length
                        const rowLen = this.rows[this.currentRow].length;
                        this.currentCol = Math.min(this.currentCol, rowLen - 1);
                    }
                    break;

                case 'left':
                    if (this.currentCol > 0) {
                        this.currentCol--;
                    }
                    break;

                case 'right':
                    if (this.currentCol < this.rows[this.currentRow].length - 1) {
                        this.currentCol++;
                    }
                    break;

                default:
                    return { success: false, message: 'Invalid direction' };
            }

            const moved = (prevRow !== this.currentRow || prevCol !== this.currentCol);
            this.updateFocus();

            return {
                success: true,
                moved: moved,
                row: this.currentRow,
                col: this.currentCol,
                totalRows: this.rows.length,
                rowLength: this.rows[this.currentRow].length
            };
        },

        select() {
            if (!this.focusedElement) {
                return { success: false, message: 'No element focused' };
            }

            try {
                // Scroll element into view first
                this.focusedElement.scrollIntoView({ behavior: 'smooth', block: 'center' });

                // Small delay then click
                setTimeout(() => {
                    // Try to find the most clickable child element
                    const clickTarget = this.findClickableChild(this.focusedElement) || this.focusedElement;
                    
                    // Focus the element first (helps with React)
                    if (clickTarget.focus) clickTarget.focus();
                    
                    // Dispatch a proper click event
                    const clickEvent = new MouseEvent('click', {
                        bubbles: true,
                        cancelable: true,
                        view: window
                    });
                    clickTarget.dispatchEvent(clickEvent);
                }, 100);

                return { success: true, message: 'Click dispatched' };
            } catch (e) {
                return { success: false, message: e.toString() };
            }
        },

        findClickableChild(element) {
            // Look for anchor or button within the element
            const link = element.querySelector('a[href]');
            if (link) return link;

            const button = element.querySelector('button');
            if (button) return button;

            const clickable = element.querySelector('[role="button"], [tabindex="0"]');
            if (clickable) return clickable;

            return null;
        },

        updateFocus() {
            if (this.rows.length === 0 || !this.rows[this.currentRow]) {
                this.hideFocus();
                return;
            }

            const item = this.rows[this.currentRow][this.currentCol];
            if (!item) {
                this.hideFocus();
                return;
            }

            this.focusedElement = item.element;

            // Update overlay position
            const rect = this.focusedElement.getBoundingClientRect();
            this.overlay.style.display = 'block';
            this.overlay.style.left = (rect.left - 3) + 'px';
            this.overlay.style.top = (rect.top - 3) + 'px';
            this.overlay.style.width = (rect.width + 6) + 'px';
            this.overlay.style.height = (rect.height + 6) + 'px';

            // Scroll into view if needed
            if (rect.top < 100 || rect.bottom > window.innerHeight - 100) {
                this.focusedElement.scrollIntoView({ behavior: 'smooth', block: 'center' });
            }
        },

        hideFocus() {
            this.focusedElement = null;
            if (this.overlay) {
                this.overlay.style.display = 'none';
            }
        },

        getStatus() {
            return {
                initialized: this.initialized,
                elementCount: this.elements.length,
                rowCount: this.rows.length,
                currentRow: this.currentRow,
                currentCol: this.currentCol,
                hasFocus: !!this.focusedElement
            };
        },

        reset() {
            this.currentRow = 0;
            this.currentCol = 0;
            this.discover();
            return { success: true };
        }
    };

    return window.NetflixNav.init();
})();
"""


def get_nav_script() -> str:
    """Get the navigation controller script for injection.
    
    Returns:
        JavaScript code string to inject into the page.
    """
    return NAV_CONTROLLER_SCRIPT


def get_navigate_call(direction: str) -> str:
    """Get JavaScript code to navigate in a direction.
    
    Args:
        direction: One of 'up', 'down', 'left', 'right'.
        
    Returns:
        JavaScript code string.
    """
    return f"window.NetflixNav ? window.NetflixNav.navigate('{direction}') : {{success: false, message: 'Not initialized'}}"


def get_select_call() -> str:
    """Get JavaScript code to select/click the focused element.
    
    Returns:
        JavaScript code string.
    """
    return "window.NetflixNav ? window.NetflixNav.select() : {success: false, message: 'Not initialized'}"


def get_discover_call() -> str:
    """Get JavaScript code to discover/refresh elements.
    
    Returns:
        JavaScript code string.
    """
    return "window.NetflixNav ? window.NetflixNav.discover() : {success: false, message: 'Not initialized'}"


def get_status_call() -> str:
    """Get JavaScript code to get navigation status.
    
    Returns:
        JavaScript code string.
    """
    return "window.NetflixNav ? window.NetflixNav.getStatus() : {initialized: false}"


def get_reset_call() -> str:
    """Get JavaScript code to reset navigation state.
    
    Returns:
        JavaScript code string.
    """
    return "window.NetflixNav ? window.NetflixNav.reset() : {success: false, message: 'Not initialized'}"
