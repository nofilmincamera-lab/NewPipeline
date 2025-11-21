"""
Content parsers for extracted web pages
"""

from .link_extractor import LinkExtractor
from .boilerplate_detector import BoilerplateDetector

__all__ = ["LinkExtractor", "BoilerplateDetector"]
