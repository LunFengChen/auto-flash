#!/usr/bin/env python3
"""
Android 全自动刷机工具 - 主程序

Usage:
    python main.py
"""

import sys
import subprocess
from pathlib import Path
from loguru import logger

# 导入核心模块
from core.config_manager import ConfigManager
from core.device_controller import DeviceController
from core.checkpoint import CheckpointManager
from core.flash_orchestrator import FlashOrchestrator


def setup_logger(log_level: str = "INFO"):
    """配置日志系统"""
    logger.remove()
    
    # 控制台输出
    logger.add(
        sys.stderr,
        format="<green>{time:HH:mm:ss}</green> <level>[{level}]</level> <level>{message}</level>",
        level=log_level,
        colorize=True
    )
    
    # 文件输出
    log_dir = Path("logs")
    log_dir.mkdir(exist_ok=True)
    
    logger.add(
        log_dir / "flash_{time:YYYYMMDD_HHmmss}.log",
        format="{time:YYYY-MM-DD HH:mm:ss} [{level}] {name}:{line} - {message}",
        level="DEBUG",
        rotation="10 MB",
        retention=10
    )


def get_device_model(serial: str) -> str:
    """获取设备型号（支持 ADB 和 Fastboot）"""
    # 1. 尝试通过 ADB 获取
    try:
        result = subprocess.run(
            ["adb", "-s", serial, "shell", "getprop", "ro.product.device"],
            capture_output=True,
            text=True,
            timeout=5
        )
        if result.returncode == 0 and result.stdout.strip():
            return result.stdout.strip()
    except Exception as e:
        logger.debug(f"ADB 获取设备型号失败: {e}")
    
    # 2. 尝试通过 Fastboot 获取
    try:
        result = subprocess.run(
            ["fastboot", "-s", serial, "getvar", "product"],
            capture_output=True,
            text=True,
            timeout=5
        )
        # fastboot getvar 输出在 stderr 中
        output = result.stderr.strip()
        # 格式: "product: redfin"
        for line in output.split('\n'):
            if line.startswith('product:'):
                model = line.split(':', 1)[1].strip()
                if model:
                    return model
    except Exception as e:
        logger.debug(f"Fastboot 获取设备型号失败: {e}")
    
    return None


def get_connected_devices():
    """获取所有连接的本地设备（包括 ADB 和 Fastboot）"""
    devices = []
    
    # 1. 获取 ADB 设备
    try:
        result = subprocess.run(
            ["adb", "devices"],
            capture_output=True,
            text=True,
            timeout=10
        )
        
        for line in result.stdout.strip().split('\n')[1:]:
            if line.strip() and '\t' in line:
                serial, status = line.split('\t')
                # 只处理本地 USB 设备（排除网络设备）
                if status == "device" and ":" not in serial:
                    devices.append(serial)
    except Exception as e:
        logger.error(f"获取 ADB 设备列表失败: {e}")
    
    # 2. 获取 Fastboot 设备
    try:
        result = subprocess.run(
            ["fastboot", "devices"],
            capture_output=True,
            text=True,
            timeout=10
        )
        
        for line in result.stdout.strip().split('\n'):
            if line.strip() and '\t' in line:
                serial, status = line.split('\t')
                # 只处理本地 USB 设备，且不重复添加
                if "fastboot" in status and ":" not in serial and serial not in devices:
                    devices.append(serial)
    except Exception as e:
        logger.error(f"获取 Fastboot 设备列表失败: {e}")
    
    return devices


def check_device_checkpoint(serial: str) -> dict:
    """检查设备是否有检查点"""
    cm = CheckpointManager(serial)
    if cm.has_checkpoint():
        checkpoint = cm.load_checkpoint()
        if checkpoint:
            return {
                "has_checkpoint": True,
                "state": checkpoint.current_state,
                "completed": len(checkpoint.completed_steps),
                "timestamp": checkpoint.timestamp
            }
    return {"has_checkpoint": False}


def display_device_menu(devices: list):
    """显示设备选择菜单"""
    # 先收集所有设备信息，避免日志和菜单混在一起
    device_infos = []
    for serial in devices:
        checkpoint_info = check_device_checkpoint(serial)
        device_infos.append((serial, checkpoint_info))
    
    # 统一输出菜单
    print("\n" + "=" * 60)
    print("检测到以下设备:")
    print("=" * 60)
    
    for idx, (serial, checkpoint_info) in enumerate(device_infos, 1):
        if checkpoint_info["has_checkpoint"]:
            print(f"  [{idx}] {serial} (有检查点: {checkpoint_info['state']}, 已完成 {checkpoint_info['completed']} 步)")
        else:
            print(f"  [{idx}] {serial}")
    
    print()
    print("  [A] 全部设备并发刷机")
    print("  [C] 清除所有检查点并重新刷机")
    print("  [Q] 退出")
    print("=" * 60)


def flash_single_device(device_model: str, device_serial: str, resume: bool = False,
                          config_path: Path = Path("config.yaml")):
    """刷机单个设备"""
    try:
        orchestrator = FlashOrchestrator(
            device_model=device_model,
            config_path=config_path,
            resume=resume,
            boot_only=False,
            dry_run=False,
            device_serial=device_serial
        )
        
        success = orchestrator.run()
        
        if success:
            logger.info("\n" + "=" * 60)
            logger.info("✓ 刷机完成！")
            logger.info("=" * 60)
            return True
        else:
            logger.error("\n" + "=" * 60)
            logger.error("✗ 刷机失败")
            logger.error("=" * 60)
            return False
            
    except KeyboardInterrupt:
        logger.warning("\n用户中断刷机流程")
        logger.info(f"可以重新运行并选择设备 {device_serial} 从检查点恢复")
        return False
    except Exception as e:
        logger.exception(f"刷机过程中发生异常: {e}")
        return False


def flash_all_devices(device_model: str, devices: list, config_path: Path = Path("config.yaml")):
    """并发刷机所有设备"""
    import threading
    import time
    
    logger.info(f"\n将为 {len(devices)} 个设备并发刷机")
    
    results = {}
    threads = []
    
    def flash_thread(serial, config_path):
        # 检查是否有检查点
        checkpoint_info = check_device_checkpoint(serial)
        resume = checkpoint_info["has_checkpoint"]
        
        if resume:
            logger.info(f"[{serial}] 从检查点恢复: {checkpoint_info['state']}")
        
        results[serial] = flash_single_device(device_model, serial, resume, config_path)
    
    # 创建线程
    for serial in devices:
        thread = threading.Thread(target=flash_thread, args=(serial, config_path), name=f"Flash-{serial}")
        thread.start()
        threads.append(thread)
        time.sleep(2)  # 错开启动时间
    
    # 等待所有线程完成
    for thread in threads:
        thread.join()
    
    # 统计结果
    success_count = sum(1 for r in results.values() if r)
    failed_count = len(results) - success_count
    
    logger.info("\n" + "=" * 60)
    logger.info("批量刷机完成！")
    logger.info("=" * 60)
    logger.info(f"成功: {success_count}/{len(devices)}")
    logger.info(f"失败: {failed_count}/{len(devices)}")
    
    if failed_count > 0:
        logger.info("\n失败的设备:")
        for serial, success in results.items():
            if not success:
                logger.info(f"  - {serial}")
    
    logger.info("=" * 60)


def main():
    """主函数"""
    import argparse

    parser = argparse.ArgumentParser(description="Android 全自动刷机工具")
    parser.add_argument("--config-dir", default="", help="配置文件目录（如 yamls），为空则用项目根目录")
    parser.add_argument("--config", default="", help="配置文件名（如 pixel5.yaml），为空则用 config.yaml")
    args = parser.parse_args()

    config_path = Path(args.config_dir) / (args.config or "config.yaml") if args.config_dir else Path(args.config or "config.yaml")
    if not config_path.exists():
        fallback = Path("config.yaml")
        if fallback.exists():
            logger.warning(f"配置不存在: {config_path}，回退到 {fallback}")
            config_path = fallback
        else:
            logger.error(f"配置文件不存在: {config_path}")
            sys.exit(1)

    # 配置日志
    setup_logger()
    
    logger.info("=" * 60)
    logger.info("Android 全自动刷机工具")
    logger.info("=" * 60)
    
    # 获取连接的设备
    devices = get_connected_devices()
    
    if not devices:
        logger.error("未检测到本地 USB 设备")
        logger.error("请检查:")
        logger.error("  1. 设备是否已开启 USB 调试")
        logger.error("  2. USB 连接是否正常")
        logger.error("  3. ADB 驱动是否已安装")
        sys.exit(1)
    
    # 显示设备菜单
    display_device_menu(devices)
    
    # 获取用户选择
    choice = input("\n请选择设备 (输入序号/A/C/Q): ").strip().upper()
    
    if choice == 'Q':
        logger.info("已退出")
        sys.exit(0)
    
    # 处理清除检查点选项
    if choice == 'C':
        logger.info("\n清除所有检查点...")
        for serial in devices:
            cm = CheckpointManager(serial)
            if cm.has_checkpoint():
                cm.clear_checkpoint()
                logger.info(f"✓ 已清除设备 {serial} 的检查点")
            else:
                logger.info(f"  设备 {serial} 没有检查点")
        
        logger.info("\n检查点已清除，将从头开始刷机所有设备")
        
        # 直接开始并发刷机，不再询问
        choice = 'A'
    
    # 自动获取设备型号
    device_model = None
    selected_devices = []
    
    if choice == 'A':
        # 全部设备
        selected_devices = devices
    else:
        # 单个设备
        try:
            idx = int(choice) - 1
            if 0 <= idx < len(devices):
                selected_devices = [devices[idx]]
            else:
                logger.error("无效的设备序号")
                sys.exit(1)
        except ValueError:
            logger.error("无效的输入")
            sys.exit(1)
    
    # 获取第一个设备的型号（假设所有设备型号相同）
    logger.info("\n正在获取设备型号...")
    device_model = get_device_model(selected_devices[0])
    
    if not device_model:
        logger.warning("⚠ 无法自动获取设备型号")
        device_model = input("请手动输入设备型号 (如 redfin): ").strip()
        if not device_model:
            logger.error("设备型号不能为空")
            sys.exit(1)
    else:
        logger.info(f"✓ 检测到设备型号: {device_model}")
    
    # 加载配置验证
    try:
        config_manager = ConfigManager(global_config_path=config_path, device_model=device_model)
        if not config_manager.validate_config():
            logger.error("配置验证失败，退出")
            sys.exit(1)
    except Exception as e:
        logger.error(f"配置加载失败: {e}")
        sys.exit(1)
    
    # 执行刷机
    if choice == 'A':
        # 全部设备并发刷机
        flash_all_devices(device_model, selected_devices, config_path)
    else:
        # 单个设备刷机
        selected_serial = selected_devices[0]
        
        # 检查是否有检查点
        checkpoint_info = check_device_checkpoint(selected_serial)
        resume = False
        
        if checkpoint_info["has_checkpoint"]:
            resume_choice = input(f"\n检测到检查点 (状态: {checkpoint_info['state']})，是否从检查点恢复？(Y/n): ").strip().lower()
            resume = resume_choice != 'n'
        
        logger.info(f"\n开始刷机: {selected_serial}")
        if resume:
            logger.info(f"从检查点恢复: {checkpoint_info['state']}")
        
        flash_single_device(device_model, selected_serial, resume, config_path)


if __name__ == "__main__":
    main()
