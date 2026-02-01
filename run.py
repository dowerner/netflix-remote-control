#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Launch script for Netflix Control."""

import sys


def main():
    """Main entry point."""
    from netflix_control.main import run
    run()


if __name__ == "__main__":
    sys.exit(main() or 0)
