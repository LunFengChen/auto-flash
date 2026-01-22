#!/usr/bin/env python3
"""
工具安装脚本 - 安装 APK 和推送二进制工具

用法:
    python -m core.tool_installer_cli              # 安装所有（APK + Binary + Modules）
    python -m core.tool_installer_cli --apk-only   # 只安装 APK
    python -m core.tool_installer_cli --binary-only # 只推送 Binary
    python -m core.tool_installer_cli --module-only # 只推送 Modules
"""

from pathlib import Path
from loguru import logger

from .device_controller import DeviceController
from .tool_installer import ToolInstaller
from .config_manager import ConfigManager


def main():
    """主函数"""
    import argparse
    
    parser = argparse.ArgumentParser(description="安装 APK 和推送工具到设备")
    parser.add_argument("--apk-only", action="store_true", help="只安装 APK")
    parser.add_argument("--binary-only", action="store_true", help="只推送 Binary")
    parser.add_argument("--module-only", action="store_true", help="只推送 Modules")
    parser.add_argument("--config", default="config.yaml", help="配置文件路径")
    
    args = parser.parse_args()
    
    # 配置日志
    logger.add(
        "logs/install_tools_{time}.log",
        rotation="10 MB",
        retention="7 days",
        level="INFO"
    )
    
    logger.info("=" * 60)
    logger.info("工具安装脚本启动")
    logger.info("=" * 60)
    
    try:
        # 加载配置
        config_manager = ConfigManager(
            global_config_path=Path(args.config),
            device_model="redfin"  # 这里可以改成从参数读取
        )
        
        # 创建设备控制器
        dc = DeviceController(
            adb_path=config_manager.global_config.adb_path,
            fastboot_path=config_manager.global_config.fastboot_path
        )
        
        # 等待设备连接
        logger.info("等待设备连接...")
        if not dc.wait_for_adb(timeout=30):
            logger.error("未检测到设备")
            return 1
        
        # 创建工具安装器
        installer = ToolInstaller(dc)
        
        # 确定要执行的操作
        install_apk = not args.binary_only and not args.module_only
        install_binary = not args.apk_only and not args.module_only
        install_module = not args.apk_only and not args.binary_only
        
        total_success = 0
        total_count = 0
        
        # 安装 APK
        if install_apk:
            # 从 config.yaml 读取 apk_install 配置
            with open(args.config, 'r', encoding='utf-8') as f:
                config_data = yaml.safe_load(f)
            
            apk_config = config_data.get("apk_install", {})
            root_config = config_data.get("root", {})
            
            success, count = installer.install_apks(
                install_root_apk=apk_config.get("install_root_apk", True),
                root_method=config_manager.global_config.root_method,
                root_config=root_config,
                extra_apks=apk_config.get("extra_apks", [])
            )
            total_success += success
            total_count += count
        
        # 推送二进制工具
        if install_binary:
            # 从 config.yaml 读取 binary 配置
            with open(args.config, 'r', encoding='utf-8') as f:
                config_data = yaml.safe_load(f)
            
            binary_config = config_data.get("binary", {})
            if binary_config.get("enabled", True):
                success, count = installer.push_binaries(
                    target_dir=binary_config.get("target_dir", "/data/local/tmp"),
                    set_executable=binary_config.get("set_executable", True)
                )
                total_success += success
                total_count += count
        
        # 推送并安装模块
        if install_module:
            # 从 config.yaml 读取 module_install 配置
            with open(args.config, 'r', encoding='utf-8') as f:
                config_data = yaml.safe_load(f)
            
            module_config = config_data.get("module_install", {})
            root_config = config_data.get("root", {})
            
            if module_config.get("enabled", False):
                # 1. 推送模块
                success, count = installer.push_modules()
                total_success += success
                total_count += count
                
                # 2. 使用 CLI 安装模块
                if module_config.get("install_method") == "cli":
                    logger.info("使用 Root 管理器 CLI 安装模块...")
                    success, count = installer.install_modules_via_cli(
                        root_method=config_manager.global_config.root_method,
                        root_config=root_config
                    )
                    total_success += success
                    total_count += count
                else:
                    logger.info("模块已推送，请手动在 Root 管理器中安装")
        
        # 总结
        logger.info("=" * 60)
        logger.info(f"✓ 安装完成: {total_success}/{total_count}")
        logger.info("=" * 60)
        
        return 0 if total_success == total_count else 1
        
    except Exception as e:
        logger.error(f"安装失败: {e}")
        import traceback
        traceback.print_exc()
        return 1


if __name__ == "__main__":
    sys.exit(main())
