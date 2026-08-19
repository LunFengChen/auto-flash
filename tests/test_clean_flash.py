#!/usr/bin/env python3
"""测试 clean-flash 终止路径"""

from types import SimpleNamespace
from unittest.mock import patch

from core.flash_orchestrator import FlashOrchestrator
from core.state_machine import FlashState, FlashStateMachine


def test_state_machine_allows_clean_flash_terminal_transition():
    sm = FlashStateMachine(initial_state=FlashState.WAIT_BOOT)
    assert sm.transition_to(FlashState.COMPLETED) is True
    assert sm.current_state == FlashState.COMPLETED


def test_wait_boot_returns_completed_in_clean_flash_mode():
    orch = object.__new__(FlashOrchestrator)
    orch.clean_flash = True
    orch.progress_display = SimpleNamespace(update=lambda *args, **kwargs: None)
    orch.config_manager = SimpleNamespace(
        global_config=SimpleNamespace(system_boot_timeout=1)
    )
    orch.device_controller = SimpleNamespace(wait_for_adb=lambda timeout: True)

    with patch("time.sleep", return_value=None):
        assert orch._handle_wait_boot() == FlashState.COMPLETED
