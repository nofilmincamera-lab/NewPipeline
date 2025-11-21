"""
Test script to verify web viewer setup.
"""

import sys
from pathlib import Path

def test_imports():
    """Test if all required modules can be imported."""
    print("Testing imports...")
    
    try:
        import fastapi
        print("[OK] fastapi")
    except ImportError as e:
        print(f"[FAIL] fastapi: {e}")
        return False
    
    try:
        import uvicorn
        print("[OK] uvicorn")
    except ImportError as e:
        print(f"[FAIL] uvicorn: {e}")
        return False
    
    try:
        import jinja2
        print("[OK] jinja2")
    except ImportError as e:
        print(f"[FAIL] jinja2: {e}")
        return False
    
    try:
        import asyncpg
        print("[OK] asyncpg")
    except ImportError as e:
        print(f"[FAIL] asyncpg: {e}")
        return False
    
    try:
        import loguru
        print("[OK] loguru")
    except ImportError as e:
        print(f"[FAIL] loguru: {e}")
        return False
    
    return True


def test_templates():
    """Test if templates exist."""
    print("\nTesting templates...")
    
    base_path = Path(__file__).parent / "templates"
    required_templates = [
        "base.html",
        "index.html",
        "organization.html",
        "entities.html",
        "entity.html",
        "stats.html",
        "error.html"
    ]
    
    all_exist = True
    for template in required_templates:
        template_path = base_path / template
        if template_path.exists():
            print(f"[OK] {template}")
        else:
            print(f"[FAIL] {template} - NOT FOUND")
            all_exist = False
    
    return all_exist


def test_app_import():
    """Test if app can be imported."""
    print("\nTesting app import...")
    
    # Add project root to path
    project_root = Path(__file__).parent.parent.parent.parent
    if str(project_root) not in sys.path:
        sys.path.insert(0, str(project_root))
    
    try:
        from scraper.src.web.app import app
        print("[OK] App imported successfully")
        print(f"  App title: {app.title}")
        return True
    except Exception as e:
        print(f"[FAIL] Failed to import app: {e}")
        import traceback
        traceback.print_exc()
        return False


def main():
    """Run all tests."""
    print("=" * 50)
    print("Web Viewer Setup Test")
    print("=" * 50)
    
    results = []
    
    results.append(("Imports", test_imports()))
    results.append(("Templates", test_templates()))
    results.append(("App Import", test_app_import()))
    
    print("\n" + "=" * 50)
    print("Test Results:")
    print("=" * 50)
    
    all_passed = True
    for name, passed in results:
        status = "PASS" if passed else "FAIL"
        print(f"{name}: {status}")
        if not passed:
            all_passed = False
    
    print("=" * 50)
    
    if all_passed:
        print("\n[SUCCESS] All tests passed! The web viewer should work.")
        print("\nTo run the viewer:")
        print("  cd scraper/src/web")
        print("  python run.py")
        print("\nThen open your browser to: http://localhost:8000")
    else:
        print("\n[ERROR] Some tests failed. Please fix the issues above.")
        print("\nTo install dependencies:")
        print("  pip install -r scraper/src/web/requirements.txt")
        print("\nOr run:")
        print("  cd scraper/src/web")
        print("  pip install -r requirements.txt")
    
    return all_passed


if __name__ == "__main__":
    success = main()
    sys.exit(0 if success else 1)

