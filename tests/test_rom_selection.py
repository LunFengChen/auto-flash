#!/usr/bin/env python3
"""
测试 ROM 选择/自动下载逻辑 - 不依赖设备连接

覆盖：
1. 清单加载：全部条目含完整 64 位 sha256、download_url 无中部 /dl/
2. 非随机模式 -> 配置 build_id
3. 随机 + 未开启自动下载 -> 本机已有 ROM
4. 随机 + 自动下载但下载失败 -> 回退本机已有 ROM
5. 随机 + 自动下载且抽中本机已有 -> 不触发下载
"""

import sys
import types
from pathlib import Path
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from loguru import logger
logger.remove()

from core.flash_orchestrator import FlashOrchestrator
from core.config_manager import ConfigManager, GlobalConfig


def make_orchestrator(random_rom: bool, auto_download_rom: bool) -> FlashOrchestrator:
    """构造最小测试对象，绕过设备检测"""
    orch = object.__new__(FlashOrchestrator)
    cfg = object.__new__(ConfigManager)
    cfg.global_config = GlobalConfig(random_rom=random_rom, auto_download_rom=auto_download_rom)
    cfg.device_config = types.SimpleNamespace(model="redfin", build_id="TP1A.221105.002")
    orch.config_manager = cfg
    orch.selected_build_id = None
    orch.state_machine = types.SimpleNamespace(config_snapshot={})
    return orch


def test_inventory_integrity():
    orch = make_orchestrator(True, True)
    roms = orch._load_rom_inventory()
    assert len(roms) == 64, f"清单应为 64 套，实际 {len(roms)}"
    for e in roms:
        assert len(e["sha256"]) == 64, f"{e['build_id']} sha256 应为 64 位"
        url = e["download_url"]
        assert "/dl/android/" not in url, f"{e['build_id']} 下载地址仍含中部 /dl/: {url}"
        assert url.endswith(f"-{e['sha256'][:8]}.zip"), f"{e['build_id']} 文件名与 sha256 前 8 位不一致"
    print("✓ 清单完整性：64 套，sha256 全 64 位，download_url 均去掉 /dl/")


def test_non_random_uses_config_build():
    orch = make_orchestrator(False, False)
    b = orch._select_new_rom_build(Path("resources/devices/redfin"))
    assert b is not None and b.name == "TP1A.221105.002", f"非随机应选配置 build_id，实际 {b.name if b else None}"
    print("✓ 非随机模式 -> 配置 build_id TP1A.221105.002")


def test_random_no_download_uses_local():
    orch = make_orchestrator(True, False)
    local = [p.name for p in orch._discover_rom_builds()]
    assert local, "测试需至少一套本机 ROM"
    b = orch._select_new_rom_build(Path("resources/devices/redfin"))
    assert b is not None and b.name in local, f"随机(不下载)应取本机 ROM，实际 {b.name if b else None}"
    print(f"✓ 随机(不下载) -> 本机 ROM {b.name}")


def test_random_download_failure_falls_back():
    orch = make_orchestrator(True, True)
    local = [p.name for p in orch._discover_rom_builds()]
    assert local, "测试需至少一套本机 ROM"
    # 固定随机抽中本机缺失的 ROM，保证两次迭代都走下载失败路径（避免抽中本机已有 ROM 提前返回）；
    # 兜底 random.choice(local_builds) 传入的是 Path 列表，直接返回第一个
    def pick_not_local(lst):
        if lst and isinstance(lst[0], Path):
            return lst[0]
        return next(e for e in lst if e["build_id"] not in local)
    with patch.object(orch, "_download_rom", return_value=False) as mock_dl, \
         patch("core.flash_orchestrator.random.choice", side_effect=pick_not_local):
        b = orch._select_new_rom_build(Path("resources/devices/redfin"))
        assert mock_dl.call_count == 2, f"应尝试 2 次下载，实际 {mock_dl.call_count}"
    assert b is not None and b.name in local, f"下载失败应回退本机 ROM，实际 {b.name if b else None}"
    print("✓ 下载失败 2 次 -> 回退本机 ROM")


def test_random_download_hits_local_no_download():
    orch = make_orchestrator(True, True)
    local = [p.name for p in orch._discover_rom_builds()]
    assert local, "测试需至少一套本机 ROM"
    with patch.object(orch, "_download_rom", return_value=True) as mock_dl:
        # 让随机抽中本机已有 ROM
        with patch("core.flash_orchestrator.random.choice",
                   side_effect=lambda lst: next(p for p in lst if p["build_id"] in local)):
            b = orch._select_new_rom_build(Path("resources/devices/redfin"))
        assert mock_dl.call_count == 0, "抽中本机已有 ROM 不应触发下载"
    assert b is not None and b.name in local
    print(f"✓ 抽中本机已有 ROM -> 不下载，直接复用 {b.name}")


def test_resolve_idempotent_and_snapshot():
    orch = make_orchestrator(True, True)
    local = [p.name for p in orch._discover_rom_builds()]
    with patch.object(orch, "_download_rom", return_value=False):
        b1 = orch._resolve_rom_build()
    b2 = orch._resolve_rom_build()
    assert b1.name == b2.name, "resolve 应幂等（同一套 ROM）"
    assert orch.selected_build_id == b1.name
    assert orch.state_machine.config_snapshot.get("rom_build_id") == b1.name, "应写入 config_snapshot"
    print(f"✓ resolve 幂等 + snapshot 写入 {b1.name}")


if __name__ == "__main__":
    test_inventory_integrity()
    test_non_random_uses_config_build()
    test_random_no_download_uses_local()
    test_random_download_failure_falls_back()
    test_random_download_hits_local_no_download()
    test_resolve_idempotent_and_snapshot()
    print("\n全部通过")
