"""Adapters for normalizing external formats."""

# Progress adapter is already in progress_parser.py, so we'll just re-export it
from ..progress_parser import parse_progress, is_completion_marker

__all__ = ["parse_progress", "is_completion_marker"]
