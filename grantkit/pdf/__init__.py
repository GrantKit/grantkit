"""PDF generation module for NSF grant proposals.

This module provides NSF-compliant PDF generation with optimized formatting
to maximize content while adhering to strict formatting requirements.
"""

from .config import NSFProgramConfig, PDFConfig
from .generator import PDFGenerator
from .optimizer import ContentOptimizer
from .templates import LaTeXTemplateManager
from .validator import PDFValidator

__all__ = [
    "PDFGenerator",
    "LaTeXTemplateManager",
    "ContentOptimizer",
    "PDFValidator",
    "PDFConfig",
    "NSFProgramConfig",
]
