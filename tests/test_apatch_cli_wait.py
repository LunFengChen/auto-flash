#!/usr/bin/env python3
"""APatch userspace CLI (apd) 就绪逻辑：不依赖真机。

覆盖刷机时反复出现的竞态：
kernel supercmd 立刻能 root，但 /data/adb/apd 要等 App 解压；
旧逻辑检查一次失败就当刷机成功，模块被跳过。
"""

import subprocess
import sys
import types
from pathlib import Path
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from loguru import logger
logger.remove()

from core.flash_orchestrator import FlashOrchestrator


def make_orch() -> FlashOrchestrator:
    orch = object.__new__(FlashOrchestrator)
    orch.device_controller = types.SimpleNamespace(adb_prefix=["adb", "-s", "TEST"])
    return orch


def test_root_shell_keeps_supercmd_as_one_adb_string():
    orch = make_orch()
    su = "/system/bin/truncate xiaofeng777"
    with patch("core.flash_orchestrator.subprocess.run") as mock_run:
        mock_run.return_value = subprocess.CompletedProcess(args=[], returncode=0, stdout="ok\n", stderr="")
        orch._root_shell(su, "test -x /data/adb/apd && echo /data/adb/apd")
    argv = mock_run.call_args[0][0]
    assert argv[:3] == ["adb", "-s", "TEST"]
    assert argv[3] == "shell"
    assert len(argv) == 5, f"adb shell 必须只跟一条命令字符串，实际 {argv}"
    cmd = argv[4]
    assert cmd.startswith("/system/bin/truncate xiaofeng777 -c ")
    assert "/data/adb/apd" in cmd
    print("✓ supercmd 作为整段 adb shell 字符串传递")


def test_find_apatch_cli_none_when_missing():
    orch = make_orch()
    missing = subprocess.CompletedProcess(args=[], returncode=1, stdout="", stderr="")
    with patch.object(orch, "_root_shell", return_value=missing):
        assert orch._find_apatch_cli("/system/bin/su") is None
    print("✓ apd 不存在时 find 返回 None")


def test_ensure_apatch_cli_uses_apk_deploy_without_waiting():
    orch = make_orch()
    finds = [None, "/data/adb/apd"]

    def fake_find(_su):
        return finds.pop(0) if finds else "/data/adb/apd"

    with patch.object(orch, "_find_apatch_cli", side_effect=fake_find), \
         patch.object(orch, "_start_apatch_app", return_value=True) as start, \
         patch.object(orch, "_deploy_apd_from_installed_apk", return_value=True) as deploy, \
         patch("core.flash_orchestrator.time.sleep") as sleep:
        path = orch._ensure_apatch_cli("/system/bin/truncate key", timeout=90)
    assert path == "/data/adb/apd"
    assert start.call_count == 1
    assert deploy.call_count == 1
    assert sleep.call_count == 0, "预置成功后不应再傻等"
    print("✓ apd 缺失时从 APK 预置，不再 10 秒盲等")


def test_ensure_apatch_cli_polls_until_app_unpacks():
    orch = make_orch()
    finds = [None, None, None, "/data/adb/ap/bin/apd"]

    def fake_find(_su):
        return finds.pop(0) if finds else "/data/adb/ap/bin/apd"

    with patch.object(orch, "_find_apatch_cli", side_effect=fake_find), \
         patch.object(orch, "_start_apatch_app", return_value=True), \
         patch.object(orch, "_deploy_apd_from_installed_apk", return_value=False), \
         patch("core.flash_orchestrator.time.sleep"):
        path = orch._ensure_apatch_cli("/system/bin/su", timeout=30)
    assert path == "/data/adb/ap/bin/apd"
    print("✓ 预置失败时轮询直到 App 解压出 apd")


def test_ensure_apatch_cli_raises_instead_of_fake_success():
    orch = make_orch()
    with patch.object(orch, "_find_apatch_cli", return_value=None), \
         patch.object(orch, "_start_apatch_app", return_value=True), \
         patch.object(orch, "_deploy_apd_from_installed_apk", return_value=False), \
         patch("core.flash_orchestrator.time.sleep"):
        try:
            orch._ensure_apatch_cli("/system/bin/su", timeout=0)
        except RuntimeError as e:
            assert "/data/adb/apd" in str(e)
            print("✓ apd 一直没有时抛错，不再当刷机成功")
            return
    raise AssertionError("应当抛 RuntimeError，而不是假装完成")


if __name__ == "__main__":
    test_root_shell_keeps_supercmd_as_one_adb_string()
    test_find_apatch_cli_none_when_missing()
    test_ensure_apatch_cli_uses_apk_deploy_without_waiting()
    test_ensure_apatch_cli_polls_until_app_unpacks()
    test_ensure_apatch_cli_raises_instead_of_fake_success()
    print("\n全部通过")
