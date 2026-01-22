"""
Android 全自动刷机工具 - 核心模块

Core modules for Android auto-flashing framework.
"""

__version__ = "1.0.0"
__author__ = "Android Auto Flash Team"

from .resource_manager import ResourceManager, ResourceInfo
from .device_controller import DeviceController
from .device_adapter import DeviceAdapter, DeviceAdapterFactory
from .config_manager import ConfigManager
from .state_machine import FlashState, FlashStateMachine
from .checkpoint import Checkpoint, CheckpointManager
from .ui_automation import UIAutomation
from .root_adapter import (
    RootMethodAdapter,
    APatchAdapter,
    MagiskAdapter,
    KernelSUAdapter,
    RootMethodFactory,
    BootImageExtractor,
    APatchCLIPatcher
)
from .compatibility_validator import (
    CompatibilityValidator,
    DeviceInfo,
    BootImageInfo
)
from .auto_recovery import AutoRecoveryManager, BootBackup
from .error_handler import ErrorHandler
from .progress_display import ProgressDisplay, BatchProgressDisplay, ProgressInfo
from .flash_orchestrator import FlashOrchestrator

__all__ = [
    "ResourceManager",
    "ResourceInfo",
    "DeviceController",
    "DeviceAdapter",
    "DeviceAdapterFactory",
    "ConfigManager",
    "FlashState",
    "FlashStateMachine",
    "Checkpoint",
    "CheckpointManager",
    "UIAutomation",
    "RootMethodAdapter",
    "APatchAdapter",
    "MagiskAdapter",
    "KernelSUAdapter",
    "RootMethodFactory",
    "BootImageExtractor",
    "APatchCLIPatcher",
    "CompatibilityValidator",
    "DeviceInfo",
    "BootImageInfo",
    "AutoRecoveryManager",
    "BootBackup",
    "ErrorHandler",
    "ProgressDisplay",
    "BatchProgressDisplay",
    "ProgressInfo",
    "FlashOrchestrator",
]
