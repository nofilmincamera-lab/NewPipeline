"""
Run script for the web viewer.
"""

import sys
from pathlib import Path

# Add project root to path
project_root = Path(__file__).parent.parent.parent.parent
sys.path.insert(0, str(project_root))

if __name__ == "__main__":
    import uvicorn
    from scraper.src.web.app import app
    
    print("=" * 60)
    print("Starting BPO Intelligence Web Viewer")
    print("=" * 60)
    print(f"Server will be available at:")
    print(f"  - http://localhost:8000")
    print(f"  - http://127.0.0.1:8000")
    print(f"  - http://0.0.0.0:8000 (all network interfaces)")
    print("=" * 60)
    print("Press CTRL+C to stop the server")
    print("=" * 60)
    print()
    
    uvicorn.run(
        app,
        host="0.0.0.0",  # Bind to all interfaces
        port=8000,
        reload=True,
        log_level="info"
    )


