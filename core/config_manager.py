"""
配置管理器 - Config Manager

加载和管理全局配置和设备配置
"""

import yaml
from pathlib import Path
from typing import Dict, Any, Optional
from dataclasses import dataclass, field
from loguru import logger


@dataclass
class GlobalConfig:
    """全局配置"""
    log_level: str = "INFO"
    max_retries: int = 3
    default_timeout: int = 30
    
    # ADB/Fastboot 路径
    adb_path: str = "adb"
    fastboot_path: str = "fastboot"
    
    # 资源路径
    common_apks: str = "resources/common/apks"
    common_modules: str = "resources/common/modules"
    common_tools: str = "resources/common/tools"
    
    # 超时设置
    adb_connect_timeout: int = 30
    fastboot_connect_timeout: int = 30
    system_boot_timeout: int = 300
    ui_operation_timeout: int = 10
    flash_system_timeout: int = 600
    boot_recovery_timeout: int = 120
    
    # 功能开关
    auto_backup_boot: bool = True
    auto_recovery: bool = True
    skip_setup_wizard: bool = False
    auto_enable_dev_mode: bool = True
    install_modules: bool = True
    dry_run: bool = False
    no_color: bool = False
    
    # 批量刷机
    batch_enabled: bool = False
    batch_max_concurrent: int = 5
    batch_auto_detect_max: bool = True
    
    # Root 方案
    root_method: str = "apatch"
    apatch_password: str = "123456"
    apatch_cli_enabled: bool = True
    apatch_cli_path: str = "resources/common/tools/apatch-cli"
    apatch_fallback_to_ui: bool = True
    
    # 备份配置
    max_backups: int = 3
    backup_dir: str = "backups"
    
    # 日志配置
    log_dir: str = "logs"
    max_log_files: int = 10


@dataclass
class DeviceConfig:
    """设备配置"""
    model: str
    codename: str
    display_name: str
    brand: str = "google"
    android_version: int = 13
    build_id: Optional[str] = None
    superkey: Optional[str] = None
    
    # 资源路径
    boot_img_source: str = "extract"  # extract, provided, patched
    boot_img: Optional[str] = None
    boot_patched_img: Optional[str] = None


class ConfigManager:
    """配置管理器"""
    
    def __init__(
        self,
        global_config_path: Path = Path("config.yaml"),
        device_model: Optional[str] = None
    ):
        """
        初始化配置管理器
        
        Args:
            global_config_path: 全局配置文件路径
            device_model: 设备型号（可选）
        """
        self.global_config_path = global_config_path
        self.device_model = device_model
        
        # 加载配置
        self.global_config = self.load_global_config()
        self.device_config = None
        
        if device_model:
            self.device_config = self.load_device_config(device_model)
        
        logger.info(f"配置管理器初始化: device={device_model or 'None'}")
    
    def load_global_config(self) -> GlobalConfig:
        """
        加载全局配置
        
        Returns:
            全局配置对象
        """
        if not self.global_config_path.exists():
            logger.warning(f"全局配置文件不存在: {self.global_config_path}")
            logger.info("使用默认配置")
            return GlobalConfig()
        
        try:
            with open(self.global_config_path, "r", encoding="utf-8") as f:
                data = yaml.safe_load(f)
            
            # 解析配置
            config = GlobalConfig()
            
            # 全局设置
            if "global" in data:
                global_data = data["global"]
                config.log_level = global_data.get("log_level", config.log_level)
                config.max_retries = global_data.get("max_retries", config.max_retries)
                config.default_timeout = global_data.get("default_timeout", config.default_timeout)
                config.adb_path = global_data.get("adb_path", config.adb_path)
                config.fastboot_path = global_data.get("fastboot_path", config.fastboot_path)
            
            # 超时设置
            if "timeouts" in data:
                timeouts = data["timeouts"]
                config.adb_connect_timeout = timeouts.get("adb_connect", config.adb_connect_timeout)
                config.fastboot_connect_timeout = timeouts.get("fastboot_connect", config.fastboot_connect_timeout)
                config.system_boot_timeout = timeouts.get("system_boot", config.system_boot_timeout)
                config.ui_operation_timeout = timeouts.get("ui_operation", config.ui_operation_timeout)
                config.flash_system_timeout = timeouts.get("flash_system", config.flash_system_timeout)
                config.boot_recovery_timeout = timeouts.get("boot_recovery", config.boot_recovery_timeout)
            
            # 功能开关
            if "features" in data:
                features = data["features"]
                config.auto_backup_boot = features.get("auto_backup_boot", config.auto_backup_boot)
                config.auto_recovery = features.get("auto_recovery", config.auto_recovery)
                config.skip_setup_wizard = features.get("skip_setup_wizard", config.skip_setup_wizard)
                config.auto_enable_dev_mode = features.get("auto_enable_dev_mode", config.auto_enable_dev_mode)
                config.install_modules = features.get("install_modules", config.install_modules)
                config.dry_run = features.get("dry_run", config.dry_run)
                config.no_color = features.get("no_color", config.no_color)
            
            # Root 配置
            if "root" in data:
                root = data["root"]
                config.root_method = root.get("method", config.root_method)
                
                if "apatch" in root:
                    apatch = root["apatch"]
                    config.apatch_password = apatch.get("password", config.apatch_password)
                    config.apatch_cli_enabled = apatch.get("cli_enabled", config.apatch_cli_enabled)
                    config.apatch_cli_path = apatch.get("cli_path", config.apatch_cli_path)
                    config.apatch_fallback_to_ui = apatch.get("fallback_to_ui", config.apatch_fallback_to_ui)
            
            logger.info("✓ 全局配置加载成功")
            return config
            
        except Exception as e:
            logger.error(f"✗ 全局配置加载失败: {e}")
            logger.info("使用默认配置")
            return GlobalConfig()
    
    def load_device_config(self, device_model: str) -> DeviceConfig:
        """
        加载设备配置（从全局配置文件的 devices 部分）
        
        Args:
            device_model: 设备型号
        
        Returns:
            设备配置对象
        """
        try:
            with open(self.global_config_path, "r", encoding="utf-8") as f:
                data = yaml.safe_load(f)
            
            # 从 devices 部分读取设备配置
            if "devices" not in data or device_model not in data["devices"]:
                logger.error(f"✗ 设备配置不存在: {device_model}")
                raise ValueError(f"设备配置不存在: {device_model}")
            
            device_data = data["devices"][device_model]
            
            # 解析设备信息
            config = DeviceConfig(
                model=device_data.get("model", device_model),
                codename=device_data.get("codename", device_model),
                display_name=device_data.get("display_name", device_model),
                brand=device_data.get("brand", "google"),
                android_version=device_data.get("android_version", 13),
                build_id=device_data.get("build_id"),
                superkey=device_data.get("superkey"),
                boot_img_source=device_data.get("boot_img_source", "extract"),
                boot_img=device_data.get("boot_img"),
                boot_patched_img=device_data.get("boot_patched_img")
            )
            
            logger.info(f"✓ 设备配置加载成功: {config.display_name}")
            return config
            
        except Exception as e:
            logger.error(f"✗ 设备配置加载失败: {e}")
            raise
    
    def get(self, key: str, default: Any = None) -> Any:
        """
        获取配置值（优先设备配置，回退到全局配置）
        
        Args:
            key: 配置键
            default: 默认值
        
        Returns:
            配置值
        """
        # 先查设备配置
        if self.device_config and hasattr(self.device_config, key):
            return getattr(self.device_config, key)
        
        # 再查全局配置
        if hasattr(self.global_config, key):
            return getattr(self.global_config, key)
        
        return default
    
    def validate_config(self) -> bool:
        """
        验证配置完整性
        
        Returns:
            是否验证通过
        """
        errors = []
        
        # 验证设备配置
        if self.device_config:
            # 检查 build_id
            if not self.device_config.build_id:
                errors.append("设备配置缺少 build_id")
            
            # 检查资源目录
            if self.device_config.build_id:
                device_resources = Path("resources/devices") / self.device_config.model / self.device_config.build_id
                if not device_resources.exists():
                    errors.append(f"设备资源目录不存在: {device_resources}")
                else:
                    # 检查 firmware 目录
                    firmware_dir = device_resources / "firmware"
                    if not firmware_dir.exists():
                        errors.append(f"固件目录不存在: {firmware_dir}")
                    
                    # 检查 root 目录
                    root_dir = device_resources / "root"
                    if not root_dir.exists():
                        logger.warning(f"Root 目录不存在（将自动创建）: {root_dir}")
            
            # 检查 boot.img
            if self.device_config.boot_img_source == "provided":
                if not self.device_config.boot_img:
                    errors.append("boot_img_source 为 'provided' 但未指定 boot_img")
                else:
                    boot_img = Path(self.device_config.boot_img)
                    if not boot_img.exists():
                        errors.append(f"boot.img 不存在: {boot_img}")
        
        if errors:
            logger.error("✗ 配置验证失败:")
            for error in errors:
                logger.error(f"  - {error}")
            return False
        
        logger.info("✓ 配置验证通过")
        return True


# 测试代码
if __name__ == "__main__":
    logger.add("logs/config_manager_test.log", rotation="10 MB")
    
    # 加载配置
    print("加载配置...")
    cm = ConfigManager(device_model="pixel5")
    
    # 显示全局配置
    print("\n全局配置:")
    print(f"  日志级别: {cm.global_config.log_level}")
    print(f"  最大重试: {cm.global_config.max_retries}")
    print(f"  Root 方案: {cm.global_config.root_method}")
    print(f"  APatch 密码: {cm.global_config.apatch_password}")
    
    # 显示设备配置
    if cm.device_config:
        print("\n设备配置:")
        print(f"  型号: {cm.device_config.model}")
        print(f"  显示名称: {cm.device_config.display_name}")
        print(f"  Android 版本: {cm.device_config.android_version}")
        print(f"  APK 列表: {cm.device_config.apks}")
        print(f"  模块列表: {cm.device_config.modules}")
    
    # 验证配置
    print("\n验证配置...")
    valid = cm.validate_config()
    print(f"验证结果: {'通过' if valid else '失败'}")
