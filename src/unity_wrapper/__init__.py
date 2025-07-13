"""Unity Package Wrapper - Automatically build Unity packages from OSS repos."""

__version__ = "0.1.0"
__author__ = "Your Name"
__email__ = "your.email@example.com"

from .core.package_builder import PackageBuilder
from .core.git_manager import GitManager
from .core.unity_generator import UnityGenerator

__all__ = ["PackageBuilder", "GitManager", "UnityGenerator"]
