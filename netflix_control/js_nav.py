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
        observer: null,
        discoverTimeout: null,
        
        // Modal navigation state
        inModalMode: false,
        zones: [],           // Array of zone objects: { type: string, elements: Element[] }
        currentZone: 0,
        
        // Season dropdown state
        dropdownOpen: false,
        dropdownOptions: [],
        dropdownIndex: 0,
        
        // Player mode overlay auto-hide
        inPlayerMode: false,
        overlayHideTimeout: null,
        OVERLAY_HIDE_DELAY: 5000,  // 5 seconds

        // Netflix red color for the focus overlay
        FOCUS_COLOR: '#E50914',

        // Selectors for different Netflix UI elements
        SELECTORS: {
            // Browse page content tiles - use specific selector to avoid nested duplicates
            tiles: '.slider-item > .title-card-container, .rowContainer .title-card-container',
            // Profile selection
            profiles: '.profile-icon, .profile-link, [data-uia="profile-link"]',
            // Navigation items
            navItems: '[data-uia="navigation-tab"], .navigation-tab',
            // Buttons with data-uia attributes
            buttons: '[data-uia*="button"], [data-uia="play-button"], [data-uia="mylist-button"]',
            // Interactive elements in modals (generic)
            modalItems: '.previewModal--container [data-uia*="button"], .previewModal--container [role="button"]',
            // Player controls
            playerControls: '[data-uia^="control-"]',
            // Episode list items (for series) - specific to episode selector container
            episodes: '.episodeSelector-container [data-uia="titleCard--container"], .titleCardList--container.episode-item',
            // Season/dropdown selector trigger
            seasonSelector: '.episodeSelector-header [role="button"], .episodeSelector-header button, [data-uia="dropdown-toggle"]',
            // Season dropdown options (when dropdown is open)
            seasonOptions: '[role="listbox"] [role="option"], .episodeSelector-dropdown [role="option"], .dropdown-menu li',
            // Modal header buttons (play, my list, rate, audio, close)
            modalHeaderButtons: '[data-uia="play-button"], [data-uia="add-to-my-list"], [data-uia="thumbs-rate-button"], [data-uia="audio-toggle-unmuted"], [data-uia="audio-toggle-muted"], [data-uia="previewModal-closebtn"]',
            // More Like This section cards
            moreLikeThis: '.moreToExplore [data-uia="titleCard--container"], [data-uia="trailersAndMore--container"] [data-uia="titleCard--container"], .moreLikeThis [data-uia="titleCard--container"]',
        },

        init() {
            this.createOverlay();
            this.discover();
            this.observeDOM();
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

        observeDOM() {
            // Watch for DOM changes to handle lazy-loaded content
            if (this.observer) {
                this.observer.disconnect();
            }
            
            this.observer = new MutationObserver((mutations) => {
                // Check if significant changes occurred
                let shouldRediscover = false;
                for (const mutation of mutations) {
                    if (mutation.addedNodes.length > 0 || mutation.removedNodes.length > 0) {
                        // Check if the changes are relevant (not just the overlay)
                        for (const node of mutation.addedNodes) {
                            if (node.nodeType === 1 && node.id !== 'netflix-nav-overlay') {
                                shouldRediscover = true;
                                break;
                            }
                        }
                    }
                    if (shouldRediscover) break;
                }
                
                if (shouldRediscover) {
                    // Debounce re-discovery
                    clearTimeout(this.discoverTimeout);
                    this.discoverTimeout = setTimeout(() => {
                        this.discover();
                    }, 300);
                }
            });
            
            this.observer.observe(document.body, {
                childList: true,
                subtree: true
            });
        },

        // Zone-based discovery for modal dialogs
        discoverModal(modal) {
            this.zones = [];
            this.inModalMode = true;
            
            // Check if season dropdown is open
            const dropdownMenu = modal.querySelector('[role="listbox"], .episodeSelector-dropdown, .dropdown-menu');
            if (dropdownMenu && dropdownMenu.offsetParent !== null) {
                // Dropdown is open - navigate dropdown options
                this.dropdownOpen = true;
                const options = dropdownMenu.querySelectorAll('[role="option"], li[tabindex], li > a');
                this.dropdownOptions = [...options].filter(el => {
                    const rect = el.getBoundingClientRect();
                    return rect.width > 0 && rect.height > 0;
                });
                
                if (this.dropdownOptions.length > 0) {
                    // Create a single zone for dropdown
                    this.zones.push({
                        type: 'dropdown',
                        elements: this.dropdownOptions.map(el => ({
                            element: el,
                            rect: el.getBoundingClientRect()
                        })),
                        layout: 'vertical'
                    });
                    console.log('[NetflixNav] Dropdown open with', this.dropdownOptions.length, 'options');
                    return;
                }
            } else {
                this.dropdownOpen = false;
                this.dropdownOptions = [];
                this.dropdownIndex = 0;
            }
            
            // Zone 0: Header controls (horizontal row)
            const headerButtons = modal.querySelectorAll(this.SELECTORS.modalHeaderButtons);
            const visibleHeaderButtons = [...headerButtons].filter(el => {
                const rect = el.getBoundingClientRect();
                return rect.width > 10 && rect.height > 10 && rect.top < window.innerHeight;
            });
            if (visibleHeaderButtons.length > 0) {
                // Sort by x position for horizontal navigation
                visibleHeaderButtons.sort((a, b) => a.getBoundingClientRect().left - b.getBoundingClientRect().left);
                this.zones.push({
                    type: 'header',
                    elements: visibleHeaderButtons.map(el => ({
                        element: el,
                        rect: el.getBoundingClientRect()
                    })),
                    layout: 'horizontal'
                });
            }
            
            // Zone 1: Season selector (if multi-season)
            const seasonToggle = modal.querySelector(this.SELECTORS.seasonSelector);
            if (seasonToggle) {
                const rect = seasonToggle.getBoundingClientRect();
                if (rect.width > 0 && rect.height > 0) {
                    this.zones.push({
                        type: 'season',
                        elements: [{ element: seasonToggle, rect: rect }],
                        layout: 'single'
                    });
                }
            }
            
            // Zone 2: Episode list (vertical list)
            const episodes = modal.querySelectorAll(this.SELECTORS.episodes);
            const visibleEpisodes = [...episodes].filter(el => {
                const rect = el.getBoundingClientRect();
                return rect.width > 10 && rect.height > 10;
            });
            if (visibleEpisodes.length > 0) {
                // Sort by y position for vertical navigation
                visibleEpisodes.sort((a, b) => a.getBoundingClientRect().top - b.getBoundingClientRect().top);
                this.zones.push({
                    type: 'episodes',
                    elements: visibleEpisodes.map(el => ({
                        element: el,
                        rect: el.getBoundingClientRect()
                    })),
                    layout: 'vertical'
                });
            }
            
            // Zone 3: More Like This (horizontal carousel)
            const similarCards = modal.querySelectorAll(this.SELECTORS.moreLikeThis);
            const visibleSimilar = [...similarCards].filter(el => {
                const rect = el.getBoundingClientRect();
                return rect.width > 10 && rect.height > 10;
            });
            if (visibleSimilar.length > 0) {
                // Sort by x position for horizontal navigation
                visibleSimilar.sort((a, b) => a.getBoundingClientRect().left - b.getBoundingClientRect().left);
                this.zones.push({
                    type: 'similar',
                    elements: visibleSimilar.map(el => ({
                        element: el,
                        rect: el.getBoundingClientRect()
                    })),
                    layout: 'horizontal'
                });
            }
            
            // Reset zone position if needed
            if (this.currentZone >= this.zones.length) {
                this.currentZone = 0;
            }
            if (this.zones.length > 0) {
                const zone = this.zones[this.currentZone];
                if (this.currentCol >= zone.elements.length) {
                    this.currentCol = 0;
                }
            }
            
            console.log('[NetflixNav] Modal discovered', this.zones.length, 'zones:', 
                this.zones.map(z => z.type + '(' + z.elements.length + ')').join(', '));
        },

        discover() {
            this.elements = [];
            this.rows = [];

            // Check for modal overlay (title detail view) - use zone-based navigation
            const modal = document.querySelector('.previewModal--container');
            if (modal) {
                this.discoverModal(modal);
                
                // Build rows from zones for compatibility with updateFocus
                this.rows = this.zones.map(zone => zone.elements);
                this.elements = this.rows.flat();
                
                // Map zone/col to row/col for focus update
                this.currentRow = this.currentZone;
                
                this.updateFocus();
                
                return {
                    success: true,
                    elementCount: this.elements.length,
                    zoneCount: this.zones.length,
                    inModalMode: true
                };
            }
            
            // Not in modal mode - use standard row-based discovery
            this.inModalMode = false;
            this.zones = [];
            this.inPlayerMode = false;  // Will be set to true if on /watch/ page
            
            // Detect page context
            const url = window.location.href;
            let selectors = [];

            if (url.includes('/browse') || url.endsWith('netflix.com/')) {
                // Check for profile gate
                const profileGate = document.querySelector('.profile-gate-container, .choose-profile, [data-uia="profile-gate"]');
                if (profileGate) {
                    selectors = [this.SELECTORS.profiles];
                } else {
                    selectors = [this.SELECTORS.tiles, this.SELECTORS.navItems];
                }
            } else if (url.includes('/watch/')) {
                selectors = [this.SELECTORS.playerControls];
                this.inPlayerMode = true;
            } else if (url.includes('/search')) {
                selectors = [this.SELECTORS.tiles, this.SELECTORS.buttons];
            } else {
                // Generic - try common selectors
                selectors = [this.SELECTORS.tiles, this.SELECTORS.profiles, this.SELECTORS.buttons];
            }

            // Find all matching elements
            const allElements = [];
            const seenElements = new Set();
            
            selectors.forEach(selector => {
                try {
                    const found = document.querySelectorAll(selector);
                    found.forEach(el => {
                        // Skip if already seen
                        if (seenElements.has(el)) return;
                        
                        // Only include visible elements
                        const rect = el.getBoundingClientRect();
                        if (rect.width > 10 && rect.height > 10 && 
                            rect.top < window.innerHeight && rect.bottom > 0 &&
                            rect.left < window.innerWidth && rect.right > 0) {
                            seenElements.add(el);
                            allElements.push({
                                element: el,
                                rect: rect,
                                y: Math.round(rect.top),
                                x: Math.round(rect.left),
                                width: rect.width,
                                height: rect.height
                            });
                        }
                    });
                } catch (e) {
                    console.warn('[NetflixNav] Selector error:', selector, e);
                }
            });

            // Filter out nested elements - keep only outermost
            const filteredElements = allElements.filter(item => {
                let parent = item.element.parentElement;
                while (parent) {
                    if (seenElements.has(parent)) {
                        return false; // Skip - parent is already in our list
                    }
                    parent = parent.parentElement;
                }
                return true;
            });

            // Sort by position
            filteredElements.sort((a, b) => a.y - b.y || a.x - b.x);

            // Group elements into rows using adaptive threshold
            // Use 10% of viewport height or 80px, whichever is smaller
            const ROW_THRESHOLD = Math.min(window.innerHeight * 0.1, 80);
            let currentRowY = -1000;
            let currentRowElements = [];

            filteredElements.forEach(item => {
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

            console.log('[NetflixNav] Discovered', this.elements.length, 'elements in', this.rows.length, 'rows');

            return {
                success: true,
                elementCount: this.elements.length,
                rowCount: this.rows.length
            };
        },

        navigate(direction) {
            // Always re-discover to catch lazy-loaded content and handle scroll
            this.discover();
            
            // Use zone-based navigation for modals
            if (this.inModalMode && this.zones.length > 0) {
                return this.navigateModal(direction);
            }
            
            // Standard row-based navigation
            return this.navigateStandard(direction);
        },

        // Zone-based navigation for modal dialogs
        navigateModal(direction) {
            if (this.zones.length === 0) {
                return { success: false, message: 'No zones found' };
            }

            const prevZone = this.currentZone;
            const prevCol = this.currentCol;
            
            const zone = this.zones[this.currentZone];
            const layout = zone.layout || 'horizontal';
            
            // Handle dropdown specially
            if (this.dropdownOpen && zone.type === 'dropdown') {
                return this.navigateDropdown(direction);
            }
            
            switch (direction) {
                case 'up':
                    if (layout === 'vertical') {
                        // In vertical zones (episodes), up moves within the zone
                        if (this.currentCol > 0) {
                            this.currentCol--;
                        } else if (this.currentZone > 0) {
                            // At top of zone, move to previous zone
                            this.currentZone--;
                            const newZone = this.zones[this.currentZone];
                            this.currentCol = newZone.elements.length - 1;
                        }
                    } else {
                        // In horizontal zones, up moves to previous zone
                        if (this.currentZone > 0) {
                            this.currentZone--;
                            const newZone = this.zones[this.currentZone];
                            // Try to maintain relative position or go to end
                            this.currentCol = Math.min(this.currentCol, newZone.elements.length - 1);
                        }
                    }
                    break;

                case 'down':
                    if (layout === 'vertical') {
                        // In vertical zones (episodes), down moves within the zone
                        if (this.currentCol < zone.elements.length - 1) {
                            this.currentCol++;
                        } else if (this.currentZone < this.zones.length - 1) {
                            // At bottom of zone, move to next zone
                            this.currentZone++;
                            this.currentCol = 0;
                        }
                    } else {
                        // In horizontal zones, down moves to next zone
                        if (this.currentZone < this.zones.length - 1) {
                            this.currentZone++;
                            const newZone = this.zones[this.currentZone];
                            this.currentCol = Math.min(this.currentCol, newZone.elements.length - 1);
                        }
                    }
                    break;

                case 'left':
                    if (layout === 'horizontal' || layout === 'single') {
                        // In horizontal zones, left/right moves within zone
                        if (this.currentCol > 0) {
                            this.currentCol--;
                        }
                    }
                    // In vertical zones, left does nothing (or could move to previous zone)
                    break;

                case 'right':
                    if (layout === 'horizontal' || layout === 'single') {
                        // In horizontal zones, left/right moves within zone
                        if (this.currentCol < zone.elements.length - 1) {
                            this.currentCol++;
                        }
                    }
                    // In vertical zones, right does nothing (or could move to next zone)
                    break;

                default:
                    return { success: false, message: 'Invalid direction' };
            }

            // Sync currentRow with currentZone for updateFocus compatibility
            this.currentRow = this.currentZone;

            const moved = (prevZone !== this.currentZone || prevCol !== this.currentCol);
            this.updateFocus();

            return {
                success: true,
                moved: moved,
                zone: this.currentZone,
                zoneType: this.zones[this.currentZone]?.type,
                col: this.currentCol,
                totalZones: this.zones.length,
                zoneLength: this.zones[this.currentZone]?.elements.length,
                inModalMode: true
            };
        },

        // Navigate within a season dropdown
        navigateDropdown(direction) {
            const zone = this.zones[0]; // Dropdown is always the only zone when open
            const prevCol = this.currentCol;
            
            switch (direction) {
                case 'up':
                    if (this.currentCol > 0) {
                        this.currentCol--;
                    }
                    break;
                case 'down':
                    if (this.currentCol < zone.elements.length - 1) {
                        this.currentCol++;
                    }
                    break;
                // left/right do nothing in dropdown
            }
            
            const moved = prevCol !== this.currentCol;
            this.currentRow = 0;
            this.updateFocus();
            
            return {
                success: true,
                moved: moved,
                dropdownOpen: true,
                optionIndex: this.currentCol,
                totalOptions: zone.elements.length
            };
        },

        // Standard row-based navigation (non-modal)
        navigateStandard(direction) {
            if (this.rows.length === 0) {
                return { success: false, message: 'No elements found' };
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

                const elementToClick = this.focusedElement;
                
                // Small delay then click
                setTimeout(() => {
                    // Try to find the most clickable child element
                    const clickTarget = this.findClickableChild(elementToClick) || elementToClick;
                    
                    // Focus the element first (helps with React)
                    if (clickTarget.focus) clickTarget.focus();
                    
                    // Dispatch a proper click event
                    const clickEvent = new MouseEvent('click', {
                        bubbles: true,
                        cancelable: true,
                        view: window
                    });
                    clickTarget.dispatchEvent(clickEvent);
                    
                    // Re-discover after click since content may change
                    setTimeout(() => {
                        this.discover();
                    }, 500);
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
            // Ensure overlay exists
            if (!this.overlay || !document.body.contains(this.overlay)) {
                this.createOverlay();
            }
            
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

            // Update overlay position - get fresh rect in case element moved
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
            
            // In player mode, schedule auto-hide of overlay
            this.scheduleOverlayHide();
        },

        hideFocus() {
            this.focusedElement = null;
            if (this.overlay) {
                this.overlay.style.display = 'none';
            }
            // Clear any pending hide timeout
            if (this.overlayHideTimeout) {
                clearTimeout(this.overlayHideTimeout);
                this.overlayHideTimeout = null;
            }
        },

        scheduleOverlayHide() {
            // Clear any existing timeout
            if (this.overlayHideTimeout) {
                clearTimeout(this.overlayHideTimeout);
            }
            // Schedule hiding the overlay after delay (only in player mode)
            if (this.inPlayerMode) {
                this.overlayHideTimeout = setTimeout(() => {
                    this.hideFocus();
                    this.overlayHideTimeout = null;
                }, this.OVERLAY_HIDE_DELAY);
            }
        },

        getStatus() {
            const status = {
                initialized: this.initialized,
                elementCount: this.elements.length,
                rowCount: this.rows.length,
                currentRow: this.currentRow,
                currentCol: this.currentCol,
                hasFocus: !!this.focusedElement,
                inModalMode: this.inModalMode,
                inPlayerMode: this.inPlayerMode
            };
            
            if (this.inModalMode) {
                status.zoneCount = this.zones.length;
                status.currentZone = this.currentZone;
                status.zoneType = this.zones[this.currentZone]?.type;
                status.dropdownOpen = this.dropdownOpen;
            }
            
            return status;
        },

        reset() {
            this.currentRow = 0;
            this.currentCol = 0;
            this.currentZone = 0;
            this.inModalMode = false;
            this.inPlayerMode = false;
            this.zones = [];
            this.dropdownOpen = false;
            this.dropdownOptions = [];
            this.dropdownIndex = 0;
            if (this.overlayHideTimeout) {
                clearTimeout(this.overlayHideTimeout);
                this.overlayHideTimeout = null;
            }
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


# Player control script - separate from navigation
PLAYER_CONTROL_SCRIPT = """
(function() {
    // Prevent re-initialization
    if (window.NetflixPlayer && window.NetflixPlayer.initialized) {
        return window.NetflixPlayer;
    }

    window.NetflixPlayer = {
        initialized: true,

        getVideo() {
            return document.querySelector('video');
        },

        isPlaying() {
            const video = this.getVideo();
            return video && !video.paused;
        },

        play() {
            const video = this.getVideo();
            if (video) {
                if (video.paused) {
                    video.play();
                    return { success: true, state: 'playing', method: 'video' };
                }
                return { success: true, state: 'playing', message: 'Already playing' };
            }
            // Fallback: click play button
            const btn = document.querySelector('[data-uia="player-blocked-play"]');
            if (btn) {
                btn.click();
                return { success: true, state: 'playing', method: 'button' };
            }
            return { success: false, message: 'No video or play button found' };
        },

        pause() {
            const video = this.getVideo();
            if (video) {
                if (!video.paused) {
                    video.pause();
                    return { success: true, state: 'paused', method: 'video' };
                }
                return { success: true, state: 'paused', message: 'Already paused' };
            }
            return { success: false, message: 'No video found' };
        },

        toggle() {
            const video = this.getVideo();
            if (video) {
                if (video.paused) {
                    video.play();
                    return { success: true, state: 'playing', method: 'video' };
                } else {
                    video.pause();
                    return { success: true, state: 'paused', method: 'video' };
                }
            }
            // Fallback: click play/pause button
            const btn = document.querySelector('[data-uia="player-blocked-play"]');
            if (btn) {
                btn.click();
                return { success: true, state: 'toggled', method: 'button' };
            }
            return { success: false, message: 'No video or play button found' };
        },

        getState() {
            const video = this.getVideo();
            if (!video) {
                return { found: false, playing: false };
            }
            return {
                found: true,
                playing: !video.paused,
                currentTime: video.currentTime,
                duration: video.duration,
                muted: video.muted,
                volume: video.volume
            };
        },

        stop() {
            // First pause the video
            const video = this.getVideo();
            if (video && !video.paused) {
                video.pause();
            }
            
            // Click the exit button to close the player
            const exitBtn = document.querySelector('[data-uia="nfplayer-exit"]');
            if (exitBtn) {
                exitBtn.click();
                return { success: true, message: 'Player closed' };
            }
            
            // Fallback: try pressing Escape via key event
            document.dispatchEvent(new KeyboardEvent('keydown', { key: 'Escape', code: 'Escape', bubbles: true }));
            return { success: true, message: 'Escape key sent', method: 'keyboard' };
        },

        skipForward(seconds = 10) {
            const video = this.getVideo();
            if (!video) {
                return { success: false, message: 'No video found' };
            }
            const oldTime = video.currentTime;
            video.currentTime = Math.min(video.currentTime + seconds, video.duration);
            return {
                success: true,
                message: 'Skipped forward',
                oldTime: oldTime,
                newTime: video.currentTime,
                duration: video.duration
            };
        },

        skipBackward(seconds = 10) {
            const video = this.getVideo();
            if (!video) {
                return { success: false, message: 'No video found' };
            }
            const oldTime = video.currentTime;
            video.currentTime = Math.max(video.currentTime - seconds, 0);
            return {
                success: true,
                message: 'Skipped backward',
                oldTime: oldTime,
                newTime: video.currentTime,
                duration: video.duration
            };
        }
    };

    return window.NetflixPlayer;
})();
"""


def get_player_script() -> str:
    """Get the player control script for injection.
    
    Returns:
        JavaScript code string to inject into the page.
    """
    return PLAYER_CONTROL_SCRIPT


def get_player_play_call() -> str:
    """Get JavaScript code to start playback.
    
    Returns:
        JavaScript code string.
    """
    return "window.NetflixPlayer ? window.NetflixPlayer.play() : {success: false, message: 'Not initialized'}"


def get_player_pause_call() -> str:
    """Get JavaScript code to pause playback.
    
    Returns:
        JavaScript code string.
    """
    return "window.NetflixPlayer ? window.NetflixPlayer.pause() : {success: false, message: 'Not initialized'}"


def get_player_toggle_call() -> str:
    """Get JavaScript code to toggle playback.
    
    Returns:
        JavaScript code string.
    """
    return "window.NetflixPlayer ? window.NetflixPlayer.toggle() : {success: false, message: 'Not initialized'}"


def get_player_state_call() -> str:
    """Get JavaScript code to get player state.
    
    Returns:
        JavaScript code string.
    """
    return "window.NetflixPlayer ? window.NetflixPlayer.getState() : {found: false, message: 'Not initialized'}"


def get_player_stop_call() -> str:
    """Get JavaScript code to stop playback and close player.
    
    Returns:
        JavaScript code string.
    """
    return "window.NetflixPlayer ? window.NetflixPlayer.stop() : {success: false, message: 'Not initialized'}"


def get_player_skip_forward_call(seconds: int = 10) -> str:
    """Get JavaScript code to skip forward.
    
    Args:
        seconds: Number of seconds to skip forward.
    
    Returns:
        JavaScript code string.
    """
    return f"window.NetflixPlayer ? window.NetflixPlayer.skipForward({seconds}) : {{success: false, message: 'Not initialized'}}"


def get_player_skip_backward_call(seconds: int = 10) -> str:
    """Get JavaScript code to skip backward.
    
    Args:
        seconds: Number of seconds to skip backward.
    
    Returns:
        JavaScript code string.
    """
    return f"window.NetflixPlayer ? window.NetflixPlayer.skipBackward({seconds}) : {{success: false, message: 'Not initialized'}}"
