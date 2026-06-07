"""用户界面模块"""
from .renderer import BoardRenderer
from .cli import main as cli_main

__all__ = ["BoardRenderer", "cli_main"]
