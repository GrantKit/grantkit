"""PDF generation module for NSF grant proposals.

This module provides NSF-compliant PDF generation with optimized formatting
to maximize content while adhering to strict formatting requirements.
"""

from .generator import PDFGenerator
from .templates import LaTeXTemplateManager
from .optimizer import ContentOptimizer
from .validator import PDFValidator
from .config import PDFConfig, NSFProgramConfig

__all__ = [
    "PDFGenerator",
    "LaTeXTemplateManager",
    "ContentOptimizer",
    "PDFValidator",
    "PDFConfig",
    "NSFProgramConfig",
]