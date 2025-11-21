#!/bin/bash
# Validation script for WSL2 packages
# Checks all required packages from requirements.txt

set -e

echo "=== WSL2 Package Validation ==="
echo ""

# Check Python version
echo "1. Checking Python installation..."
if command -v python3 &> /dev/null; then
    PYTHON_VERSION=$(python3 --version)
    echo "   ✓ Python found: $PYTHON_VERSION"
else
    echo "   ✗ Python3 not found"
    echo "   → Install with: sudo apt update && sudo apt install -y python3 python3-pip python3-venv"
    exit 1
fi

# Check pip
echo ""
echo "2. Checking pip installation..."
if command -v pip3 &> /dev/null; then
    PIP_VERSION=$(pip3 --version)
    echo "   ✓ pip found: $PIP_VERSION"
else
    echo "   ✗ pip3 not found"
    echo "   → Install with: sudo apt install -y python3-pip"
    exit 1
fi

# Check if we're in the right directory
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REQUIREMENTS_FILE="$SCRIPT_DIR/scraper/requirements.txt"

if [ ! -f "$REQUIREMENTS_FILE" ]; then
    echo ""
    echo "✗ Requirements file not found at: $REQUIREMENTS_FILE"
    echo "  Please run this script from the project root directory"
    exit 1
fi

echo ""
echo "3. Checking required packages from $REQUIREMENTS_FILE"
echo ""

# Extract package names (remove version specifiers and comments)
PACKAGES=$(grep -v '^#' "$REQUIREMENTS_FILE" | grep -v '^$' | sed 's/==.*//' | sed 's/\[.*\]//')

MISSING_PACKAGES=()
INSTALLED_PACKAGES=()

for PACKAGE in $PACKAGES; do
    # Skip empty lines
    [ -z "$PACKAGE" ] && continue
    
    # Check if package is installed
    if python3 -c "import ${PACKAGE//-/_}" 2>/dev/null; then
        VERSION=$(python3 -c "import ${PACKAGE//-/_}; print(getattr(${PACKAGE//-/_}, '__version__', 'unknown'))" 2>/dev/null || echo "installed")
        echo "   ✓ $PACKAGE ($VERSION)"
        INSTALLED_PACKAGES+=("$PACKAGE")
    else
        echo "   ✗ $PACKAGE - NOT INSTALLED"
        MISSING_PACKAGES+=("$PACKAGE")
    fi
done

echo ""
echo "=== Summary ==="
echo "Installed: ${#INSTALLED_PACKAGES[@]} packages"
echo "Missing: ${#MISSING_PACKAGES[@]} packages"

if [ ${#MISSING_PACKAGES[@]} -gt 0 ]; then
    echo ""
    echo "✗ Missing packages:"
    for PKG in "${MISSING_PACKAGES[@]}"; do
        echo "  - $PKG"
    done
    echo ""
    echo "To install all missing packages, run:"
    echo "  cd scraper && pip3 install -r requirements.txt"
    exit 1
else
    echo ""
    echo "✓ All required packages are installed!"
    exit 0
fi

