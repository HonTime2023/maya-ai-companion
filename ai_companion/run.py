#!/usr/bin/env python3
"""Simple launcher that bypasses environment issues"""
import sys
import os

# Add the current directory to path
sys.path.insert(0, os.path.dirname(__file__))

# Run main
if __name__ == "__main__":
    import main
