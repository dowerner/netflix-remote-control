#!/usr/bin/env python3
"""Utility script to check JavaScript syntax in js_nav.py."""

import subprocess
import sys
import tempfile
import os

def check_js_syntax(script_name: str, script_content: str) -> bool:
    """Check JavaScript syntax using Node.js.
    
    Args:
        script_name: Name for error reporting
        script_content: JavaScript code to check
        
    Returns:
        True if syntax is valid, False otherwise
    """
    # Wrap in function to avoid runtime errors from browser APIs
    wrapped = f"function __check__() {{ {script_content} }}"
    
    with tempfile.NamedTemporaryFile(mode='w', suffix='.js', delete=False) as f:
        f.write(wrapped)
        tmpfile = f.name
    
    try:
        result = subprocess.run(
            ['node', '--check', tmpfile],
            capture_output=True,
            text=True
        )
        if result.returncode == 0:
            print(f"✓ {script_name}: JavaScript syntax OK")
            return True
        else:
            print(f"✗ {script_name}: JavaScript syntax ERROR")
            print(result.stderr)
            return False
    finally:
        os.unlink(tmpfile)


def main():
    from netflix_control.js_nav import NAV_CONTROLLER_SCRIPT, PLAYER_CONTROL_SCRIPT
    
    print("Checking JavaScript syntax in js_nav.py...\n")
    
    all_ok = True
    all_ok &= check_js_syntax("NAV_CONTROLLER_SCRIPT", NAV_CONTROLLER_SCRIPT)
    all_ok &= check_js_syntax("PLAYER_CONTROL_SCRIPT", PLAYER_CONTROL_SCRIPT)
    
    print()
    if all_ok:
        print("All JavaScript syntax checks passed!")
        sys.exit(0)
    else:
        print("Some JavaScript syntax checks failed!")
        sys.exit(1)


if __name__ == "__main__":
    main()
