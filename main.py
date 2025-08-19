#!/usr/bin/env python3
"""Main entry point for the eBay Draft Maker application."""

import asyncio
import os
import sys
from pathlib import Path

# Add project root to path
sys.path.insert(0, str(Path(__file__).parent))

from src.orchestrator import main as batch_main


def run_web_server():
    """Run the FastAPI web server for OAuth and API endpoints."""
    import uvicorn
    from app import app
    
    port = int(os.getenv("PORT", 8080))
    host = os.getenv("HOST", "0.0.0.0")
    
    print(f"Starting web server on {host}:{port}")
    uvicorn.run(app, host=host, port=port)


def run_batch_processing():
    """Run the batch processing for UPC codes."""
    try:
        asyncio.run(batch_main())
    except KeyboardInterrupt:
        print("\n\nProcess interrupted by user")
        sys.exit(0)
    except Exception as e:
        print(f"\nError: {e}", file=sys.stderr)
        sys.exit(1)


if __name__ == "__main__":
    # Determine which mode to run in
    mode = os.getenv("APP_MODE", "web").lower()
    
    # Check for command-line arguments that indicate batch mode
    if len(sys.argv) > 1 and not sys.argv[1].startswith("-"):
        # If there are arguments that look like file paths, run in batch mode
        mode = "batch"
    
    # Also check for explicit mode flag
    if "--batch" in sys.argv:
        mode = "batch"
    elif "--web" in sys.argv:
        mode = "web"
    
    print(f"Running in {mode} mode")
    
    if mode == "web":
        run_web_server()
    else:
        run_batch_processing()
