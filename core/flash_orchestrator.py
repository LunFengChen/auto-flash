"""
刷机流程编排器 - Flash Orchestrator

编排完整的刷机流程，连接所有核心模块
"""

from pathlib import Path
from typing import Optional
from loguru import logger
import subprocess

from .state_machine import FlashState, FlashStateMachine
from .device_controller import DeviceController
from .config_manager import ConfigManager
from .checkpoint import CheckpointManager
from .resource_manager import ResourceManager
from .device_adapter import DeviceAdapterFactory
from .ui_automation import UIAutomation
from .root_adapter import RootMethodFactory
from .compatibility_validator import CompatibilityValidator
from .auto_recovery import AutoRecoveryManager
from .error_handler import ErrorHandler
from .progress_display import ProgressDisplay


class FlashOrchestrator:
    """刷机流程编排器 - 连接所有模块，执行完整刷机流程"""
    
    def __init__(
        self,
        device_model: str,
        config_path: Path = Path("config.yaml"),
        resume: bool = False,
        boot_only: bool = False,
        dry_run: bool = False,
        device_serial: Optional[str] = None
    ):
        """
        初始化刷机编排器
        
        Args:
            device_model: 设备型号
            config_path: 配置文件路径
            resume: 是否从检查点恢复
            boot_only: 只刷 boot.img（保留数据）
            dry_run: 模拟运行（不执行实际操作）
            device_serial: 指定设备序列号（可选，用于多设备场景）
        """
        logger.info("=" * 60)
        logger.info("初始化刷机流程编排器")
        logger.info("=" * 60)
        
        # 加载配置
        self.config_manager = ConfigManager(
            global_config_path=config_path,
            device_model=device_model
        )
        
        # 获取本地设备列表
        adb_path = self.config_manager.global_config.adb_path
        fastboot_path = self.config_manager.global_config.fastboot_path
        
        # 先检查是否有 fastboot 设备
        self.is_in_fastboot_mode = False
        try:
            result = subprocess.run(
                [fastboot_path, "devices"],
                capture_output=True,
                text=True,
                timeout=10
            )
            
            fastboot_devices = []
            for line in result.stdout.strip().split('\n'):
                if 'fastboot' in line:
                    device_id = line.split()[0]
                    if DeviceController.is_local_device(device_id):
                        fastboot_devices.append(device_id)
            
            if fastboot_devices:
                device_serial = fastboot_devices[0]
                logger.info(f"检测到 Fastboot 设备: {device_serial}")
                logger.info("设备已在 Bootloader 模式，将跳过前置步骤直接刷机")
                self.is_in_fastboot_mode = True
                
                # 创建设备控制器
                self.device_controller = DeviceController(
                    serial=device_serial,
                    adb_path=adb_path,
                    fastboot_path=fastboot_path
                )
                self.resource_manager = ResourceManager(device_model)
                self.device_adapter = DeviceAdapterFactory.create(device_model)
                self.error_handler = ErrorHandler(
                    max_retries=self.config_manager.global_config.max_retries
                )
                
                # 初始化其他必要组件（fastboot 模式下需要）
                self.device_info = None
                self.checkpoint_manager = None
                self.compatibility_validator = None
                self.auto_recovery_manager = None
                self.ui_automation = None
                self.root_adapter = None
                self.state_machine = None
                self.progress_display = None
                
                # 运行模式
                self.resume = resume
                self.boot_only = boot_only
                self.dry_run = dry_run
                
                logger.info("✓ 刷机编排器初始化完成")
                return
        except subprocess.TimeoutExpired:
            logger.warning("Fastboot 设备检测超时，尝试检测 ADB 设备")
        except Exception as e:
            logger.warning(f"Fastboot 设备检测失败: {e}，尝试检测 ADB 设备")
        
        # 检查 ADB 设备
        local_devices = DeviceController.list_devices(
            local_only=True,
            adb_path=adb_path
        )
        
        if not local_devices:
            logger.error("未检测到本地 USB 设备")
            raise RuntimeError("未检测到本地 USB 设备")
        
        # 如果指定了设备序列号，验证它是否存在
        if device_serial:
            if device_serial not in local_devices:
                logger.error(f"指定的设备 {device_serial} 未连接")
                logger.info(f"可用设备: {local_devices}")
                raise RuntimeError(f"设备 {device_serial} 未连接")
            selected_device = device_serial
            logger.info(f"使用指定设备: {selected_device}")
        else:
            # 未指定设备，使用第一个
            if len(local_devices) > 1:
                logger.warning(f"检测到多个本地设备: {local_devices}")
                logger.info(f"使用第一个设备: {local_devices[0]}")
            selected_device = local_devices[0]
            logger.info(f"选择设备: {selected_device}")
        
        # 创建核心组件
        self.device_controller = DeviceController(
            serial=selected_device,
            adb_path=self.config_manager.global_config.adb_path,
            fastboot_path=self.config_manager.global_config.fastboot_path
        )
        self.resource_manager = ResourceManager(device_model)
        self.device_adapter = DeviceAdapterFactory.create(device_model)
        self.error_handler = ErrorHandler(
            max_retries=self.config_manager.global_config.max_retries
        )
        
        # 设备信息（稍后获取）
        self.device_info = None
        self.checkpoint_manager = None
        self.compatibility_validator = None
        self.auto_recovery_manager = None
        self.ui_automation = None
        self.root_adapter = None
        self.state_machine = None
        self.progress_display = None
        
        # 运行模式
        self.resume = resume
        self.boot_only = boot_only
        self.dry_run = dry_run
        # is_in_fastboot_mode 已在第 62 行初始化为 False，Fastboot 模式会设置为 True
        
        logger.info("✓ 刷机编排器初始化完成")
    
    def run(self) -> bool:
        """
        执行完整刷机流程
        
        Returns:
            是否成功完成
        """
        try:
            # 如果设备已在 fastboot 模式，跳过前置步骤
            if self.is_in_fastboot_mode:
                logger.info("=" * 60)
                logger.info("设备已在 Bootloader 模式，直接开始刷机")
                logger.info("=" * 60)
                
                # 创建状态机，从刷机步骤开始
                self._create_state_machine_for_flash_only()
                
                # 创建进度显示器
                self.progress_display = ProgressDisplay(total_steps=12)
                
                # 执行刷机流程
                success = self.state_machine.run()
                
                # 显示总结
                self.progress_display.display_summary(success)
                
                return success
            
            # 正常流程
            # 1. 检查设备连接
            if not self._check_device_connection():
                return False
            
            # 2. 获取设备信息
            if not self._get_device_info():
                return False
            
            # 3. 初始化其他组件
            self._initialize_components()
            
            # 4. 验证配置
            if not self._validate_configuration():
                return False
            
            # 5. 执行兼容性验证
            if not self._validate_compatibility():
                return False
            
            # 6. 检查检查点（如果恢复模式）
            checkpoint = None
            if self.resume:
                checkpoint = self.checkpoint_manager.load_checkpoint()
                if checkpoint:
                    initial_state = self.checkpoint_manager.get_state_from_checkpoint(checkpoint)
                    logger.info(f"从检查点恢复: {initial_state.value}")
            
            # 7. 创建状态机
            self._create_state_machine(checkpoint)
            
            # 8. 创建进度显示器
            self.progress_display = ProgressDisplay(total_steps=12)
            
            # 9. 执行刷机流程
            logger.info("=" * 60)
            logger.info("开始刷机流程")
            logger.info("=" * 60)
            
            success = self.state_machine.run()
            
            # 10. 显示总结
            self.progress_display.display_summary(success)
            
            return success
            
        except Exception as e:
            logger.error(f"刷机流程异常: {e}")
            self.error_handler.handle_critical_error(
                e,
                self.state_machine.current_state if self.state_machine else FlashState.INIT,
                self.device_info.serial if self.device_info else None
            )
            return False
    
    def _check_device_connection(self) -> bool:
        """检查设备连接"""
        logger.info("检查设备连接...")
        
        timeout = self.config_manager.global_config.adb_connect_timeout
        
        if not self.device_controller.wait_for_adb(timeout=timeout):
            logger.error("未检测到设备，请检查:")
            logger.error("  1. 设备是否已开启 USB 调试")
            logger.error("  2. USB 连接是否正常")
            logger.error("  3. ADB 驱动是否已安装")
            return False
        
        logger.info("✓ 设备已连接")
        return True
    
    def _get_device_info(self) -> bool:
        """获取设备信息"""
        logger.info("获取设备信息...")
        
        try:
            self.device_info = self.device_controller.get_device_info()
            
            logger.info("设备信息:")
            logger.info(f"  型号: {self.device_info.model}")
            logger.info(f"  品牌: {self.device_info.brand}")
            logger.info(f"  Android 版本: {self.device_info.android_version}")
            logger.info(f"  Build ID: {self.device_info.build_id}")
            logger.info(f"  序列号: {self.device_info.serial}")
            
            return True
            
        except Exception as e:
            logger.error(f"获取设备信息失败: {e}")
            return False
    
    def _initialize_components(self):
        """初始化其他组件"""
        logger.info("初始化组件...")
        
        # 检查点管理器
        self.checkpoint_manager = CheckpointManager(self.device_info.serial)
        
        # 兼容性验证器
        self.compatibility_validator = CompatibilityValidator(self.device_controller)
        
        # 自动恢复管理器
        if self.config_manager.global_config.auto_backup_boot:
            backup_dir = Path(self.config_manager.global_config.backup_dir)
            self.auto_recovery_manager = AutoRecoveryManager(
                self.device_controller,
                backup_dir
            )
        
        # UI 自动化（延迟初始化，只在需要时创建）
        self.ui_automation = None
        
        # Root 适配器 - 从配置文件读取 APK 路径
        try:
            with open(self.config_manager.global_config_path, "r", encoding="utf-8") as f:
                import yaml
                config_data = yaml.safe_load(f)
            
            root_method = self.config_manager.global_config.root_method
            apk_path = "resources/common/apks/apatch.apk"  # 默认值
            
            if root_method == "apatch":
                root_config_data = config_data.get("root", {}).get("apatch", {})
                configured_apk_path = root_config_data.get("apk_path")
                if configured_apk_path:
                    apk_path = f"resources/common/{configured_apk_path}"
            elif root_method == "magisk":
                root_config_data = config_data.get("root", {}).get("magisk", {})
                configured_apk_path = root_config_data.get("apk_path")
                if configured_apk_path:
                    apk_path = f"resources/common/{configured_apk_path}"
        except Exception as e:
            logger.warning(f"读取 Root APK 配置失败: {e}，使用默认路径")
            apk_path = "resources/common/apks/apatch.apk"
        
        root_config = {
            "method": self.config_manager.global_config.root_method,
            "apatch": {
                "apk_path": Path(apk_path),  # 转换为 Path 对象
                "password": self.config_manager.global_config.apatch_password
            },
            "apatch_cli": {
                "enabled": self.config_manager.global_config.apatch_cli_enabled,
                "cli_path": self.config_manager.global_config.apatch_cli_path,
                "fallback_to_ui": self.config_manager.global_config.apatch_fallback_to_ui
            }
        }
        self.root_adapter = RootMethodFactory.create(root_config)
        
        logger.info("✓ 组件初始化完成")
    
    def _validate_configuration(self) -> bool:
        """验证配置"""
        logger.info("验证配置...")
        
        if not self.config_manager.validate_config():
            logger.error("配置验证失败")
            return False
        
        logger.info("✓ 配置验证通过")
        return True
    
    def _validate_compatibility(self) -> bool:
        """验证兼容性"""
        logger.info("验证设备兼容性...")
        
        # 验证设备型号
        expected_model = self.config_manager.device_config.model
        if not self.compatibility_validator.validate_device_model(expected_model):
            logger.error("设备型号不匹配")
            return False
        
        # 检查电池电量
        battery = self.device_controller.check_battery_level()
        if battery < 20:
            logger.error(f"电池电量过低 ({battery}%)，请充电后再试")
            return False
        elif battery < 30:
            logger.warning(f"电池电量较低 ({battery}%)，建议充电")
        
        # 检查 Bootloader
        if not self.device_controller.check_bootloader_status():
            logger.error("Bootloader 已锁定，请先解锁")
            return False
        
        logger.info("✓ 兼容性验证通过")
        return True
    
    def _create_state_machine(self, checkpoint: Optional = None):
        """创建状态机并注册处理函数"""
        logger.info("创建状态机...")
        
        # 确定初始状态
        if checkpoint:
            initial_state = self.checkpoint_manager.get_state_from_checkpoint(checkpoint)
        elif self.boot_only:
            # boot-only 模式：跳过系统刷入，直接从修补 boot 开始
            initial_state = FlashState.PATCH_BOOT
        else:
            initial_state = FlashState.INIT
        
        # 创建状态机（传入 checkpoint_manager 和 device_info）
        self.state_machine = FlashStateMachine(
            initial_state=initial_state,
            checkpoint_manager=self.checkpoint_manager,
            device_info={
                "model": self.device_info.model,
                "serial": self.device_info.serial,
                "build_id": self.device_info.build_id
            } if self.device_info else {}
        )
        
        # 注册状态处理函数
        self.state_machine.register_handler(FlashState.INIT, self._handle_init)
        self.state_machine.register_handler(FlashState.CHECK_DEVICE, self._handle_check_device)
        self.state_machine.register_handler(FlashState.REBOOT_BOOTLOADER, self._handle_reboot_bootloader)
        self.state_machine.register_handler(FlashState.FLASH_SYSTEM, self._handle_flash_system)
        self.state_machine.register_handler(FlashState.WAIT_BOOT, self._handle_wait_boot)
        self.state_machine.register_handler(FlashState.SETUP_WIZARD, self._handle_setup_wizard)
        self.state_machine.register_handler(FlashState.ENABLE_DEV_MODE, self._handle_enable_dev_mode)
        self.state_machine.register_handler(FlashState.INSTALL_APATCH, self._handle_install_apatch)
        self.state_machine.register_handler(FlashState.PATCH_BOOT, self._handle_patch_boot)
        self.state_machine.register_handler(FlashState.FLASH_BOOT, self._handle_flash_boot)
        self.state_machine.register_handler(FlashState.INSTALL_APKS, self._handle_install_apks)
        self.state_machine.register_handler(FlashState.INSTALL_MODULES, self._handle_install_modules)
        
        logger.info("✓ 状态机创建完成")
    
    def _create_state_machine_for_flash_only(self):
        """创建状态机（仅刷机模式，跳过前置步骤）"""
        logger.info("创建状态机（Fastboot 模式）...")
        
        # 从刷机步骤开始
        # 注意：Fastboot 模式下没有 device_info 和 checkpoint_manager
        self.state_machine = FlashStateMachine(
            initial_state=FlashState.FLASH_SYSTEM,
            checkpoint_manager=None,  # Fastboot 模式不支持 checkpoint
            device_info={}
        )
        
        # 只注册刷机及后续步骤的处理函数
        self.state_machine.register_handler(FlashState.FLASH_SYSTEM, self._handle_flash_system)
        self.state_machine.register_handler(FlashState.WAIT_BOOT, self._handle_wait_boot)
        self.state_machine.register_handler(FlashState.SETUP_WIZARD, self._handle_setup_wizard)
        self.state_machine.register_handler(FlashState.ENABLE_DEV_MODE, self._handle_enable_dev_mode)
        self.state_machine.register_handler(FlashState.INSTALL_APATCH, self._handle_install_apatch)
        self.state_machine.register_handler(FlashState.PATCH_BOOT, self._handle_patch_boot)
        self.state_machine.register_handler(FlashState.FLASH_BOOT, self._handle_flash_boot)
        self.state_machine.register_handler(FlashState.INSTALL_APKS, self._handle_install_apks)
        self.state_machine.register_handler(FlashState.INSTALL_MODULES, self._handle_install_modules)
        
        logger.info("✓ 状态机创建完成")
    
    # ==================== 状态处理函数 ====================
    
    def _wait_for_package_manager(self, timeout: int = 120) -> bool:
        """
        等待 package manager 服务就绪
        
        Args:
            timeout: 超时时间（秒）
        
        Returns:
            是否就绪
        """
        import time
        deadline = time.time() + timeout
        check_interval = 3
        
        while time.time() < deadline:
            try:
                # 检查 package manager 服务是否可用
                result = subprocess.run(
                    self.device_controller.adb_prefix + ["shell", "pm list packages -s"],
                    capture_output=True,
                    text=True,
                    timeout=5
                )
                if result.returncode == 0 and result.stdout.strip():
                    elapsed = int(timeout - (deadline - time.time()))
                    logger.info(f"✓ package manager 服务已就绪（等待 {elapsed} 秒）")
                    return True
            except Exception as e:
                logger.debug(f"package manager 检查失败: {e}")
            
            remaining = int(deadline - time.time())
            if remaining > 0:
                logger.debug(f"  等待 package manager 服务... (剩余 {remaining} 秒)")
            time.sleep(check_interval)
        
        logger.debug("package manager 服务等待超时")
        return False
    
    def _wait_for_storage_ready(self, timeout: int = 60) -> bool:
        """
        等待存储服务就绪
        
        Args:
            timeout: 超时时间（秒）
        
        Returns:
            是否就绪
        """
        import time
        deadline = time.time() + timeout
        check_interval = 2
        
        while time.time() < deadline:
            try:
                # 检查是否能访问 /sdcard
                result = subprocess.run(
                    self.device_controller.adb_prefix + ["shell", "test -d /sdcard && echo 'ready'"],
                    capture_output=True,
                    text=True,
                    timeout=5
                )
                if result.returncode == 0 and "ready" in result.stdout:
                    elapsed = int(timeout - (deadline - time.time()))
                    logger.info(f"✓ 存储服务已就绪（等待 {elapsed} 秒）")
                    return True
            except Exception as e:
                logger.debug(f"存储服务检查失败: {e}")
            
            remaining = int(deadline - time.time())
            if remaining > 0:
                logger.debug(f"  等待存储服务... (剩余 {remaining} 秒)")
            time.sleep(check_interval)
        
        logger.debug("存储服务等待超时")
        return False
    
    def _handle_init(self) -> FlashState:
        """处理初始化状态"""
        logger.info("初始化刷机流程...")
        self.progress_display.update(FlashState.INIT, "初始化")
        
        # 列出可用资源
        apks = self.resource_manager.list_all_apks()
        modules = self.resource_manager.list_all_modules()
        
        logger.info(f"可用 APK: {len(apks)} 个")
        logger.info(f"可用模块: {len(modules)} 个")
        
        return FlashState.CHECK_DEVICE
    
    def _handle_check_device(self) -> FlashState:
        """处理设备检测状态"""
        logger.info("检测设备状态...")
        self.progress_display.update(FlashState.CHECK_DEVICE, "检测设备")
        
        # 检查点会在状态转换时自动保存，这里不需要手动保存
        
        return FlashState.REBOOT_BOOTLOADER
    
    def _handle_reboot_bootloader(self) -> FlashState:
        """处理重启到 Bootloader 状态"""
        logger.info("重启到 Bootloader 模式...")
        self.progress_display.update(FlashState.REBOOT_BOOTLOADER, "重启到 Bootloader")
        
        # 重启到 bootloader
        if not self.device_controller.adb_reboot("bootloader"):
            raise RuntimeError("重启到 Bootloader 失败")
        
        # 等待 fastboot 连接
        timeout = self.config_manager.global_config.fastboot_connect_timeout
        if not self.device_controller.wait_for_fastboot(timeout=timeout):
            raise RuntimeError("Fastboot 连接超时")
        
        logger.info("✓ 已进入 Bootloader 模式")
        return FlashState.FLASH_SYSTEM
    
    def _handle_flash_system(self) -> FlashState:
        """处理刷入系统状态"""
        logger.info("刷入系统...")
        self.progress_display.update(FlashState.FLASH_SYSTEM, "刷入系统")
        
        logger.warning("这可能需要 5-10 分钟，请耐心等待...")
        logger.info("=" * 60)
        
        # 获取刷机包目录（在 resources/devices/{model}/ 下查找）
        device_resources_dir = Path("resources/devices") / self.config_manager.device_config.model
        firmware_dir = None
        
        if device_resources_dir.exists():
            for build_dir in device_resources_dir.iterdir():
                if build_dir.is_dir() and not build_dir.name.startswith('.'):
                    firmware_path = build_dir / "firmware"
                    if firmware_path.exists():
                        firmware_dir = firmware_path
                        logger.info(f"找到刷机包: {build_dir.name}")
                        break
        
        if not firmware_dir:
            raise RuntimeError(f"未找到刷机包目录: {device_resources_dir}")
        
        logger.info(f"刷机包目录: {firmware_dir}")
        
        # 直接调用 fastboot 命令刷机
        import os
        env = os.environ.copy()
        
        try:
            # 1. 刷入 bootloader
            bootloader_img = list(firmware_dir.glob("bootloader-*.img"))
            if bootloader_img:
                logger.info(f"刷入 Bootloader: {bootloader_img[0].name}")
                self.device_controller.fastboot_flash("bootloader", bootloader_img[0])
                logger.info("重启到 Bootloader...")
                subprocess.run(
                    [self.device_controller.fastboot_path, "-s", self.device_controller.serial, "reboot-bootloader"],
                    timeout=10
                )
                import time
                time.sleep(5)
            
            # 2. 刷入 radio
            radio_img = list(firmware_dir.glob("radio-*.img"))
            if radio_img:
                logger.info(f"刷入 Radio: {radio_img[0].name}")
                self.device_controller.fastboot_flash("radio", radio_img[0])
                logger.info("重启到 Bootloader...")
                subprocess.run(
                    [self.device_controller.fastboot_path, "-s", self.device_controller.serial, "reboot-bootloader"],
                    timeout=10
                )
                time.sleep(5)
            
            # 3. 刷入系统镜像（-w 会清除数据）
            system_zip = list(firmware_dir.glob("image-*.zip"))
            if not system_zip:
                raise RuntimeError("未找到系统镜像文件")
            
            logger.info(f"刷入系统镜像: {system_zip[0].name}")
            logger.info("正在刷入系统，请耐心等待...")
            
            # 不捕获输出，让 fastboot 的进度直接显示在终端
            result = subprocess.run(
                [
                    self.device_controller.fastboot_path,
                    "-s", self.device_controller.serial,
                    "-w",  # 清除数据
                    "update",
                    system_zip[0].name  # 只使用文件名，因为 cwd 已经设置为 firmware_dir
                ],
                cwd=str(firmware_dir),
                timeout=self.config_manager.global_config.flash_system_timeout
            )
            
            if result.returncode != 0:
                logger.error(f"系统镜像刷入失败，返回码: {result.returncode}")
                raise RuntimeError("刷机失败")
            
            logger.info("=" * 60)
            logger.info("✓ 系统刷入完成")
            
        except subprocess.TimeoutExpired:
            logger.error("刷机超时")
            raise RuntimeError("刷机超时")
        except Exception as e:
            logger.error(f"刷机失败: {e}")
            raise
        
        return FlashState.WAIT_BOOT
    
    def _handle_wait_boot(self) -> FlashState:
        """处理等待系统启动状态"""
        logger.info("等待系统启动...")
        self.progress_display.update(FlashState.WAIT_BOOT, "等待系统启动")
        
        timeout = self.config_manager.global_config.system_boot_timeout
        logger.info(f"等待 ADB 连接（超时 {timeout} 秒）...")
        
        if not self.device_controller.wait_for_adb(timeout=timeout):
            raise RuntimeError("系统启动超时")
        
        logger.info("✓ 系统启动完成")
        
        # 等待系统稳定
        import time
        logger.info("等待系统稳定...")
        time.sleep(10)
        
        return FlashState.SETUP_WIZARD
    
    def _handle_setup_wizard(self) -> FlashState:
        """处理初始化向导状态"""
        logger.info("完成初始化向导...")
        self.progress_display.update(FlashState.SETUP_WIZARD, "完成初始化向导")
        
        if self.config_manager.global_config.skip_setup_wizard:
            logger.info("跳过初始化向导（配置已禁用）")
            return FlashState.ENABLE_DEV_MODE
        
        # 初始化 UI 自动化（如果还未初始化）
        if self.ui_automation is None:
            try:
                self.ui_automation = UIAutomation()
            except RuntimeError as e:
                logger.warning(f"⚠ UI 自动化初始化失败: {e}")
                logger.warning("⚠ 跳过初始化向导，请手动完成")
                return FlashState.ENABLE_DEV_MODE
        
        # 连接 UI 自动化
        d = self.ui_automation.connect()
        
        # 完成初始化向导
        if self.ui_automation.complete_setup_wizard(d):
            logger.info("✓ 初始化向导完成")
        else:
            logger.warning("⚠ 初始化向导可能未完全完成，请手动检查")
        
        return FlashState.ENABLE_DEV_MODE
    
    def _handle_enable_dev_mode(self) -> FlashState:
        """处理开启开发者模式状态"""
        logger.info("开启开发者模式...")
        self.progress_display.update(FlashState.ENABLE_DEV_MODE, "开启开发者模式")
        
        if not self.config_manager.global_config.auto_enable_dev_mode:
            logger.info("跳过开发者模式（配置已禁用）")
            return FlashState.INSTALL_APATCH
        
        # 初始化 UI 自动化（如果还未初始化）
        if self.ui_automation is None:
            try:
                self.ui_automation = UIAutomation()
            except RuntimeError as e:
                logger.warning(f"⚠ UI 自动化初始化失败: {e}")
                logger.warning("⚠ 跳过开发者模式，请手动开启")
                return FlashState.INSTALL_APATCH
        
        # 连接 UI 自动化
        d = self.ui_automation.connect()
        
        # 开启开发者模式
        if self.ui_automation.enable_developer_mode(d):
            logger.info("✓ 开发者模式已开启")
        else:
            logger.warning("⚠ 开发者模式开启可能失败，请手动检查")
        
        return FlashState.INSTALL_APATCH
    
    def _handle_install_apatch(self) -> FlashState:
        """处理安装 APatch 状态"""
        logger.info("安装 APatch...")
        self.progress_display.update(FlashState.INSTALL_APATCH, "安装 APatch")
        
        # 检查 root 方案
        root_method = self.config_manager.global_config.root_method
        if root_method != "apatch":
            logger.info(f"Root 方案不是 APatch ({root_method})，跳过安装")
            return FlashState.PATCH_BOOT
        
        # 安装 APatch（APK 路径已在 root_adapter 初始化时配置）
        if self.root_adapter.install_app(self.device_controller):
            logger.info("✓ APatch 安装完成")
        else:
            logger.error("✗ APatch 安装失败")
            raise RuntimeError("APatch 安装失败")
        
        return FlashState.PATCH_BOOT
    
    def _handle_patch_boot(self) -> FlashState:
        """处理修补 boot.img 状态"""
        logger.info("修补 boot.img...")
        self.progress_display.update(FlashState.PATCH_BOOT, "修补 boot.img")
        
        # 获取 boot.img
        boot_img_source = self.config_manager.device_config.boot_img_source
        
        if boot_img_source == "patched":
            logger.info("使用已修补的 boot.img，跳过修补步骤")
            return FlashState.FLASH_BOOT
        
        # 使用 BootPatcher 修补 boot.img
        try:
            from .boot_patcher import BootPatcher, BootPatchConfig
            
            # 构建配置
            device_config = self.config_manager.device_config
            global_config = self.config_manager.global_config
            
            # 获取设备资源路径
            device_resources = Path("resources/devices") / self.config_manager.device_model
            firmware_dir = device_resources / device_config.build_id / "firmware"
            root_dir = device_resources / device_config.build_id / "root"
            
            patch_config = BootPatchConfig(
                device_model=self.config_manager.device_model,
                build_id=device_config.build_id,
                firmware_dir=firmware_dir,
                root_dir=root_dir,
                superkey=device_config.superkey,
                patch_tools_dir=Path("resources/common/tools"),
                binary_dir=Path("resources/common/binary"),
                kpimg_version=None  # 自动检测版本
            )
            
            patcher = BootPatcher(patch_config)
            patched_boot = patcher.get_or_create_patched_boot()
            
            logger.info(f"✓ boot.img 修补完成: {patched_boot}")
            
            # 保存修补后的路径
            self._patched_boot_path = patched_boot
            
        except Exception as e:
            logger.error(f"✗ boot.img 修补失败: {e}")
            raise
        
        return FlashState.FLASH_BOOT
    
    def _handle_flash_boot(self) -> FlashState:
        """处理刷入 boot.img 状态"""
        logger.info("刷入修补后的 boot.img...")
        self.progress_display.update(FlashState.FLASH_BOOT, "刷入 boot.img")
        
        # 重启到 bootloader
        self.device_controller.adb_reboot("bootloader")
        self.device_controller.wait_for_fastboot(timeout=30)
        
        # 获取 boot.img 路径
        if hasattr(self, '_patched_boot_path'):
            # 使用刚修补的 boot.img
            boot_img = self._patched_boot_path
        else:
            # 查找已存在的修补后的 boot.img
            device_config = self.config_manager.device_config
            device_resources = Path("resources/devices") / self.config_manager.device_model
            root_dir = device_resources / device_config.build_id / "root"
            
            # 查找修补后的 boot.img
            patched_boots = list(root_dir.glob("*patched*.img"))
            if not patched_boots:
                raise RuntimeError(f"未找到修补后的 boot.img: {root_dir}")
            
            # 使用最新的
            boot_img = max(patched_boots, key=lambda p: p.stat().st_mtime)
            logger.info(f"使用已存在的修补后 boot.img: {boot_img.name}")
        
        if self.auto_recovery_manager and self.config_manager.global_config.auto_recovery:
            # 使用自动恢复管理器刷入
            success = self.auto_recovery_manager.flash_boot_with_recovery(
                boot_img,
                timeout=self.config_manager.global_config.boot_recovery_timeout,
                auto_recover=True
            )
            
            if not success:
                raise RuntimeError("boot.img 刷入失败")
        else:
            # 直接刷入
            if not self.device_controller.fastboot_flash("boot", boot_img):
                raise RuntimeError("boot.img 刷入失败")
            
            self.device_controller.fastboot_reboot()
            
            if not self.device_controller.wait_for_adb(timeout=120):
                raise RuntimeError("系统启动失败")
        
        logger.info("✓ boot.img 刷入完成")
        return FlashState.INSTALL_APKS
    
    def _handle_install_apks(self) -> FlashState:
        """处理安装 APK 状态"""
        logger.info("安装 APK...")
        self.progress_display.update(FlashState.INSTALL_APKS, "安装 APK")
        
        # 等待系统服务就绪
        logger.info("等待系统服务就绪...")
        import time
        time.sleep(10)  # 初始等待 10 秒
        
        logger.info("检查 package manager 服务...")
        if not self._wait_for_package_manager(timeout=60):
            logger.warning("⚠ package manager 服务未完全就绪，但继续尝试安装 APK")
        
        # 检查存储服务
        logger.info("检查存储服务...")
        if not self._wait_for_storage_ready(timeout=30):
            logger.warning("⚠ 存储服务未就绪，但继续尝试安装 APK")
        
        logger.info("=" * 60)
        
        apks_to_install = []
        
        # 1. 检查是否需要安装 Root APK（从 config.yaml 读取）
        try:
            with open(self.config_manager.global_config_path, "r", encoding="utf-8") as f:
                import yaml
                config_data = yaml.safe_load(f)
            
            apk_config = config_data.get("apk_install", {})
            if apk_config.get("install_root_apk", True):
                root_method = self.config_manager.global_config.root_method
                
                if root_method == "apatch":
                    root_config = config_data.get("root", {}).get("apatch", {})
                    apk_path = root_config.get("apk_path")
                    if apk_path:
                        full_path = Path("resources/common") / apk_path
                        if full_path.exists():
                            logger.info(f"添加 APatch APK: {apk_path}")
                            apks_to_install.append(full_path)
                        else:
                            logger.warning(f"APatch APK 不存在: {full_path}")
                
                elif root_method == "magisk":
                    root_config = config_data.get("root", {}).get("magisk", {})
                    apk_path = root_config.get("apk_path")
                    if apk_path:
                        full_path = Path("resources/common") / apk_path
                        if full_path.exists():
                            logger.info(f"添加 Magisk APK: {apk_path}")
                            apks_to_install.append(full_path)
                        else:
                            logger.warning(f"Magisk APK 不存在: {full_path}")
            
            # 2. 安装额外的 APK
            extra_apks = apk_config.get("extra_apks", [])
            
            if extra_apks:
                # 如果指定了列表，只安装列表中的 APK
                logger.info(f"使用配置的 APK 列表: {len(extra_apks)} 个")
                for apk_path in extra_apks:
                    full_path = Path("resources/common") / apk_path
                    if full_path.exists():
                        apks_to_install.append(full_path)
                    else:
                        logger.warning(f"APK 不存在: {full_path}")
            else:
                # 如果没有指定列表，安装 apks/ 目录下的所有 APK
                logger.info("扫描 apks/ 目录...")
                apks = self.resource_manager.list_all_apks()
                for apk in apks:
                    apks_to_install.append(apk.path)
            
            # 3. 安装 LSP 模块 APK（如果启用了 LSP）
            module_config = config_data.get("module_install", {})
            if module_config.get("install_lsp", False):
                lsp_modules_dir = Path("resources/common") / module_config.get("lsp_modules_dir", "modules/lsp")
                if lsp_modules_dir.exists():
                    logger.info(f"扫描 LSP 模块 APK: {lsp_modules_dir}")
                    for apk_path in lsp_modules_dir.glob("*.apk"):
                        logger.info(f"  添加 LSP 模块 APK: {apk_path.name}")
                        apks_to_install.append(apk_path)
            
            # 4. 安装 Zygisk 管理器 APK（如果启用了 Zygisk）
            if module_config.get("install_zygisk", False):
                zygisk_modules_dir = Path("resources/common") / module_config.get("zygisk_modules_dir", "modules/zygisk")
                if zygisk_modules_dir.exists():
                    logger.info(f"扫描 Zygisk 管理器 APK: {zygisk_modules_dir}")
                    for apk_path in zygisk_modules_dir.glob("*.apk"):
                        logger.info(f"  添加 Zygisk 管理器 APK: {apk_path.name}")
                        apks_to_install.append(apk_path)
        
        except Exception as e:
            logger.error(f"读取 APK 配置失败: {e}")
            logger.info("使用默认策略：安装所有 APK")
            apks = self.resource_manager.list_all_apks()
            for apk in apks:
                apks_to_install.append(apk.path)
        
        # 5. 去重
        apks_to_install = list(set(apks_to_install))
        
        if not apks_to_install:
            logger.info("没有需要安装的 APK")
            return FlashState.INSTALL_MODULES
        
        # 6. 逐个安装（失败的 APK 会重试）
        logger.info(f"准备安装 {len(apks_to_install)} 个 APK")
        success_count = 0
        failed_apks = []
        retry_apks = []
        
        for apk_path in apks_to_install:
            logger.info(f"安装: {apk_path.name}")
            
            if self.device_controller.adb_install(apk_path):
                success_count += 1
            else:
                # 第一次失败，加入重试列表
                retry_apks.append(apk_path)
        
        # 重试失败的 APK（可能是系统服务还没完全就绪）
        if retry_apks:
            logger.info(f"等待 10 秒后重试失败的 APK...")
            import time
            time.sleep(10)
            
            for apk_path in retry_apks:
                logger.info(f"重试安装: {apk_path.name}")
                if self.device_controller.adb_install(apk_path):
                    success_count += 1
                else:
                    failed_apks.append(apk_path.name)
        
        # 报告结果
        if success_count == len(apks_to_install):
            logger.info(f"✓ 所有 APK 安装成功: {success_count}/{len(apks_to_install)}")
        elif success_count > 0:
            logger.warning(f"⚠ 部分 APK 安装成功: {success_count}/{len(apks_to_install)}")
            if failed_apks:
                logger.warning(f"  失败的 APK: {', '.join(failed_apks)}")
        else:
            logger.error(f"✗ 所有 APK 安装失败: 0/{len(apks_to_install)}")
        
        # 如果安装了 APatch，需要启动应用以激活 root 环境
        root_method = self.config_manager.global_config.root_method
        if root_method == "apatch":
            logger.info("=" * 60)
            logger.info("启动 APatch 应用以激活 root 环境...")
            logger.info("=" * 60)
            
            try:
                # 启动 APatch 主 Activity
                result = subprocess.run(
                    self.device_controller.adb_prefix + ["shell", "am", "start", "-n", "me.bmax.apatch/.ui.MainActivity"],
                    capture_output=True,
                    text=True,
                    timeout=10
                )
                
                if result.returncode == 0:
                    logger.info("✓ APatch 应用已启动")
                    logger.info("等待 APatch 初始化（10 秒）...")
                    import time
                    time.sleep(10)
                else:
                    logger.warning(f"⚠ 启动 APatch 失败: {result.stderr}")
            except Exception as e:
                logger.warning(f"⚠ 启动 APatch 异常: {e}")
        
        return FlashState.INSTALL_MODULES
    
    def _handle_install_modules(self) -> FlashState:
        """处理安装模块状态"""
        logger.info("安装模块...")
        self.progress_display.update(FlashState.INSTALL_MODULES, "安装模块")
        
        # 1. 先推送 binary 文件到设备（此时 root 已激活）
        logger.info("=" * 60)
        logger.info("推送 binary 文件到设备...")
        logger.info("=" * 60)
        
        binary_dir = Path("resources/common/binary")
        if binary_dir.exists():
            binaries_to_push = []
            for binary_file in binary_dir.iterdir():
                if binary_file.is_file() and not binary_file.name.startswith('.'):
                    binaries_to_push.append(binary_file)
            
            if binaries_to_push:
                logger.info(f"找到 {len(binaries_to_push)} 个 binary 文件")
                push_success = 0
                
                for binary_file in binaries_to_push:
                    logger.info(f"推送: {binary_file.name}")
                    remote_path = f"/data/local/tmp/{binary_file.name}"
                    
                    if self.device_controller.adb_push(binary_file, remote_path):
                        push_success += 1
                    else:
                        logger.warning(f"⚠ {binary_file.name} 推送失败")
                
                logger.info(f"Binary 文件推送完成: {push_success}/{len(binaries_to_push)}")
                
                # 使用 root 权限设置可执行权限
                executable_files = [
                    f"/data/local/tmp/{f.name}" for f in binaries_to_push 
                    if not f.name.endswith(('.dex', '.jar', '.apk'))
                ]
                
                if executable_files:
                    logger.info("使用 root 权限设置可执行权限...")
                    
                    # 尝试多种 su 路径
                    su_paths = ["/system/xbin/su", "/system/bin/su"]
                    su_success = False
                    
                    for su_path in su_paths:
                        try:
                            chmod_cmd = f"chmod 755 {' '.join(executable_files)}"
                            result = subprocess.run(
                                self.device_controller.adb_prefix + ["shell", su_path, "-c", chmod_cmd],
                                capture_output=True,
                                text=True,
                                timeout=10
                            )
                            
                            if result.returncode == 0:
                                logger.info(f"✓ 已设置 {len(executable_files)} 个文件的可执行权限")
                                su_success = True
                                break
                        except Exception as e:
                            logger.debug(f"su 路径 {su_path} 不可用: {e}")
                            continue
                    
                    if not su_success:
                        logger.warning("⚠ 无法使用 root 权限设置可执行权限")
                        logger.warning("  提示：请手动设置或检查 APatch 是否已激活")
            else:
                logger.info("没有需要推送的 binary 文件")
        else:
            logger.info(f"Binary 目录不存在: {binary_dir}")
        
        logger.info("=" * 60)
        
        # 2. 等待存储服务就绪
        logger.info("等待存储服务就绪...")
        if not self._wait_for_storage_ready(timeout=60):
            logger.error("✗ 存储服务未就绪，跳过模块安装")
            return FlashState.COMPLETED
        
        # 读取配置
        try:
            with open(self.config_manager.global_config_path, "r", encoding="utf-8") as f:
                import yaml
                config_data = yaml.safe_load(f)
            
            module_config = config_data.get("module_install", {})
        except Exception as e:
            logger.error(f"读取模块配置失败: {e}")
            logger.info("跳过模块安装")
            return FlashState.COMPLETED
        
        # 检查是否启用模块安装
        if not module_config.get("enabled", True):
            logger.info("跳过模块安装（配置已禁用）")
            return FlashState.COMPLETED
        
        # 获取安装方式
        install_method = module_config.get("install_method", "cli")
        
        # 收集需要安装的模块
        modules_to_install = []
        
        # 1. ZIP 通用模块（APatch 和 Magisk 都支持）
        if module_config.get("install_zip", False):
            zip_dir = Path("resources/common") / "modules/zip"
            if zip_dir.exists():
                logger.info(f"扫描 ZIP 模块: {zip_dir}")
                for zip_file in zip_dir.glob("*.zip"):
                    logger.info(f"  添加 ZIP 模块: {zip_file.name}")
                    modules_to_install.append(zip_file)
        
        # 2. LSP 功能（可选）
        if module_config.get("install_lsp", False):
            # LSP 框架
            lsp_framework = module_config.get("lsp_framework")
            if lsp_framework:
                lsp_path = Path("resources/common") / lsp_framework
                if lsp_path.exists():
                    logger.info(f"添加 LSP 框架: {lsp_path.name}")
                    modules_to_install.append(lsp_path)
                else:
                    logger.warning(f"LSP 框架不存在: {lsp_path}")
        
        # 去重
        modules_to_install = list(set(modules_to_install))
        
        if not modules_to_install:
            logger.info("没有需要安装的模块")
            return FlashState.COMPLETED
        
        logger.info(f"准备安装 {len(modules_to_install)} 个模块")
        
        # 1. 创建目标目录
        logger.info("创建 /sdcard/Download 目录...")
        try:
            # 创建目录（不检查返回码，因为目录可能已存在）
            subprocess.run(
                self.device_controller.adb_prefix + ["shell", "mkdir -p /sdcard/Download"],
                capture_output=True,
                text=True,
                timeout=10
            )
            
            # 验证目录是否存在
            check_result = subprocess.run(
                self.device_controller.adb_prefix + ["shell", "test -d /sdcard/Download && echo 'exists'"],
                capture_output=True,
                text=True,
                timeout=10
            )
            
            if "exists" not in check_result.stdout:
                logger.error("✗ 目录创建失败: 目录不存在")
                logger.error("无法推送模块，跳过模块安装")
                return FlashState.COMPLETED
            
            logger.info("✓ 目录创建成功")
            
        except Exception as e:
            logger.error(f"✗ 目录创建失败: {e}")
            logger.error("无法推送模块，跳过模块安装")
            return FlashState.COMPLETED
        
        # 2. 推送模块到设备
        push_success_count = 0
        for module in modules_to_install:
            logger.info(f"推送模块: {module.name}")
            if self.device_controller.adb_push(module, f"/sdcard/Download/{module.name}"):
                push_success_count += 1
            else:
                logger.warning(f"⚠ {module.name} 推送失败")
        
        if push_success_count == 0:
            logger.error("✗ 所有模块推送失败")
            return FlashState.COMPLETED
        
        logger.info(f"模块推送完成: {push_success_count}/{len(modules_to_install)}")
        
        # 3. 根据安装方式处理
        if install_method == "cli":
            # 使用 CLI 自动安装
            logger.info("使用 CLI 自动安装模块...")
            
            root_method = self.config_manager.global_config.root_method
            
            if root_method == "apatch":
                # 验证 APatch CLI 是否可用
                logger.info("检查 APatch root 环境...")
                
                # 获取 superkey
                superkey = self.config_manager.device_config.superkey
                if not superkey:
                    logger.warning("⚠ 未配置 superkey，使用默认密码")
                    superkey = "xiaofeng777"
                
                logger.info(f"使用 superkey: {superkey}")
                
                # 方法1: 尝试使用 kpatch su（不需要应用启动）
                # 从 APatch 源码看，可以直接用 libkpatch.so 执行 su
                kpatch_paths = [
                    "/data/adb/ap/bin/kpatch",
                    "/system/lib64/libkpatch.so",
                    "/data/app/*/me.bmax.apatch-*/lib/arm64/libkpatch.so"
                ]
                
                su_available = False
                working_su_method = None
                
                # 先尝试 kpatch su
                for kpatch_path in kpatch_paths:
                    try:
                        # 使用 kpatch 的 su 命令格式：kpatch <superkey> su -c 'command'
                        result = subprocess.run(
                            self.device_controller.adb_prefix + ["shell", f"{kpatch_path} {superkey} su -c 'echo test'"],
                            capture_output=True,
                            text=True,
                            timeout=5
                        )
                        if result.returncode == 0 and "test" in result.stdout:
                            su_available = True
                            working_su_method = f"{kpatch_path} {superkey} su"
                            logger.info(f"✓ kpatch su 可用: {kpatch_path}")
                            break
                    except Exception as e:
                        logger.debug(f"kpatch 路径 {kpatch_path} 不可用: {e}")
                        continue
                
                # 如果 kpatch 不可用，尝试标准 su 路径
                if not su_available:
                    logger.info("kpatch su 不可用，尝试标准 su 路径...")
                    
                    # 启动 APatch 应用以激活 root 环境
                    logger.info("启动 APatch 应用...")
                    try:
                        result = subprocess.run(
                            self.device_controller.adb_prefix + ["shell", "am", "start", "-n", "me.bmax.apatch/.ui.MainActivity"],
                            capture_output=True,
                            text=True,
                            timeout=10
                        )
                        if result.returncode == 0:
                            logger.info("✓ APatch 应用已启动")
                        else:
                            logger.warning(f"⚠ 启动 APatch 失败: {result.stderr}")
                    except Exception as e:
                        logger.warning(f"⚠ 启动 APatch 异常: {e}")
                    
                    # 等待应用初始化
                    logger.info("等待 APatch 初始化（30 秒）...")
                    import time
                    time.sleep(30)
                    
                    # 尝试标准 su 路径，并重试多次
                    su_paths = ["/system/xbin/su", "/system/bin/su"]
                    max_retries = 5
                    retry_interval = 10
                    
                    for retry in range(max_retries):
                        if retry > 0:
                            logger.info(f"重试 {retry}/{max_retries}，等待 {retry_interval} 秒...")
                            time.sleep(retry_interval)
                        
                        for su_path in su_paths:
                            try:
                                result = subprocess.run(
                                    self.device_controller.adb_prefix + ["shell", su_path, "-c", "echo test"],
                                    capture_output=True,
                                    text=True,
                                    timeout=5
                                )
                                if result.returncode == 0 and "test" in result.stdout:
                                    su_available = True
                                    working_su_method = su_path
                                    logger.info(f"✓ su 可用: {su_path}")
                                    break
                            except Exception:
                                continue
                        
                        if su_available:
                            break
                        else:
                            logger.info(f"  su 仍不可用，尝试 {retry + 1}/{max_retries}")
                
                if not su_available:
                    logger.warning("⚠ su 命令不可用")
                    logger.warning("⚠ 可能原因: APatch 还未激活 root 环境")
                    logger.info("=" * 60)
                    logger.info("⚠ 需要手动激活 APatch")
                    logger.info("=" * 60)
                    logger.info("请在设备上执行以下操作：")
                    logger.info("  1. 打开 APatch 应用")
                    logger.info("  2. 等待应用初始化完成（可能需要几秒钟）")
                    logger.info("  3. 授予必要的权限")
                    logger.info("")
                    logger.info("完成后，按 Enter 键继续模块安装...")
                    logger.info("（或按 Ctrl+C 跳过模块安装）")
                    logger.info("=" * 60)
                    
                    try:
                        input()  # 等待用户按 Enter
                        logger.info("继续检查 su 命令...")
                        
                        # 重新检查 su 是否可用
                        for su_path in su_paths:
                            try:
                                result = subprocess.run(
                                    self.device_controller.adb_prefix + ["shell", f"{su_path} -c 'echo test'"],
                                    capture_output=True,
                                    text=True,
                                    timeout=5
                                )
                                if result.returncode == 0 and "test" in result.stdout:
                                    su_available = True
                                    working_su_method = su_path
                                    logger.info(f"✓ su 现在可用了: {su_path}")
                                    break
                            except Exception:
                                continue
                        
                        if not su_available:
                            logger.error("✗ su 命令仍然不可用")
                            logger.info("=" * 60)
                            logger.info("模块已推送到设备 /sdcard/Download/ 目录")
                            logger.info("请手动打开 APatch 管理器安装以下模块:")
                            for module in modules_to_install:
                                logger.info(f"  - {module.name}")
                            logger.info("=" * 60)
                            return FlashState.COMPLETED
                    
                    except KeyboardInterrupt:
                        logger.warning("\n用户跳过模块安装")
                        logger.info("=" * 60)
                        logger.info("模块已推送到设备 /sdcard/Download/ 目录")
                        logger.info("请手动打开 APatch 管理器安装以下模块:")
                        for module in modules_to_install:
                            logger.info(f"  - {module.name}")
                        logger.info("=" * 60)
                        return FlashState.COMPLETED
                
                # 检查 APatch CLI 是否存在
                try:
                    cli_check = subprocess.run(
                        self.device_controller.adb_prefix + ["shell", working_su_method, "-c", "test -f /data/adb/ap/bin/apd && echo exists"],
                        capture_output=True,
                        text=True,
                        timeout=5
                    )
                    if "exists" not in cli_check.stdout:
                        logger.warning("⚠ APatch CLI 不可用: /data/adb/ap/bin/apd 不存在")
                        logger.warning("⚠ 可能原因: APatch 应用未完成初始化")
                        logger.info("=" * 60)
                        logger.info("模块已推送到设备 /sdcard/Download/ 目录")
                        logger.info("请手动打开 APatch 管理器安装以下模块:")
                        for module in modules_to_install:
                            logger.info(f"  - {module.name}")
                        logger.info("=" * 60)
                        return FlashState.COMPLETED
                except Exception as e:
                    logger.error(f"✗ 检查 APatch CLI 失败: {e}")
                    logger.info("回退到手动安装模式")
                    logger.info("=" * 60)
                    logger.info("模块已推送到设备 /sdcard/Download/ 目录")
                    logger.info("请手动打开 APatch 管理器安装以下模块:")
                    for module in modules_to_install:
                        logger.info(f"  - {module.name}")
                    logger.info("=" * 60)
                    return FlashState.COMPLETED
                
                # APatch CLI: su -c "/data/adb/ap/bin/apd -s <superkey> module install <path>"
                
                # 获取 superkey
                superkey = self.config_manager.device_config.superkey
                if not superkey:
                    logger.warning("⚠ 未配置 superkey，使用默认密码")
                    superkey = "xiaofeng777"
                
                logger.info(f"使用 superkey: {superkey}")
                
                # 1. 先安装模块
                install_success_count = 0
                for module in modules_to_install:
                    module_path = f"/sdcard/Download/{module.name}"
                    logger.info(f"安装模块: {module.name}")
                    try:
                        output = subprocess.run(
                            self.device_controller.adb_prefix + ["shell", working_su_method, "-c", f"/data/adb/ap/bin/apd -s {superkey} module install {module_path}"],
                            capture_output=True,
                            text=True,
                            timeout=30
                        )
                        if output.returncode == 0 or "success" in output.stdout.lower() or "installed" in output.stdout.lower():
                            logger.info(f"✓ {module.name} 安装成功")
                            install_success_count += 1
                        else:
                            logger.warning(f"⚠ {module.name} 安装可能失败")
                            logger.warning(f"  输出: {output.stdout}")
                            if output.stderr:
                                logger.warning(f"  错误: {output.stderr}")
                    except Exception as e:
                        logger.error(f"✗ {module.name} 安装失败: {e}")
                
                logger.info(f"模块安装完成: {install_success_count}/{len(modules_to_install)}")
                
                # 2. 重启设备使模块生效（只有在模块安装成功时才重启）
                if install_success_count > 0:
                    logger.info("=" * 60)
                    logger.info("模块安装完成，重启设备使模块生效...")
                    logger.info("=" * 60)
                    
                    if self.device_controller.adb_reboot("system"):
                        logger.info("等待设备重启...")
                        if self.device_controller.wait_for_adb(timeout=120):
                            logger.info("✓ 设备重启完成，模块已生效")
                        else:
                            logger.warning("⚠ 设备重启超时")
                    else:
                        logger.warning("⚠ 设备重启失败")
            
            elif root_method == "magisk":
                # Magisk CLI: magisk --install-module <path>
                install_success_count = 0
                for module in modules_to_install:
                    module_path = f"/sdcard/Download/{module.name}"
                    logger.info(f"安装模块: {module.name}")
                    try:
                        output = self.device_controller.adb_shell(
                            f"magisk --install-module {module_path}"
                        )
                        if "success" in output.lower() or "installed" in output.lower():
                            logger.info(f"✓ {module.name} 安装成功")
                            install_success_count += 1
                        else:
                            logger.warning(f"⚠ {module.name} 安装可能失败")
                            logger.warning(f"  输出: {output}")
                    except Exception as e:
                        logger.error(f"✗ {module.name} 安装失败: {e}")
                
                logger.info(f"模块安装完成: {install_success_count}/{len(modules_to_install)}")
        
        elif install_method == "manual":
            # 手动安装模式
            logger.info("=" * 60)
            logger.info("模块已推送到设备 /sdcard/Download/ 目录")
            logger.info("请手动打开 Root 管理器安装以下模块:")
            for module in modules_to_install:
                logger.info(f"  - {module.name}")
            logger.info("=" * 60)
        
        return FlashState.COMPLETED


# 测试代码
if __name__ == "__main__":
    logger.add("logs/flash_orchestrator_test.log", rotation="10 MB")
    
    print("\n测试刷机编排器（Dry-run 模式）:")
    print("=" * 60)
    
    # 创建编排器
    orchestrator = FlashOrchestrator(
        device_model="pixel5",
        resume=False
    )
    
    print("\n编排器创建成功")
    print("注意：实际刷机需要连接设备并准备好资源文件")
