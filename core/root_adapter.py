"""
Root 方案适配层 - 支持多种 Root 方案(APatch、Magisk、KernelSU)

设计原则:
1. 策略模式: 不同 Root 方案使用不同的适配器
2. 工厂模式: 根据配置自动选择适配器
3. 统一接口: 所有适配器实现相同的接口
"""

import logging
import subprocess
import time
import zipfile
import re
from abc import ABC, abstractmethod
from pathlib import Path
from typing import Optional, List
from datetime import datetime

logger = logging.getLogger(__name__)


class RootMethodAdapter(ABC):
    """Root 方案适配器基类"""
    
    @abstractmethod
    def install_app(self, device_controller) -> bool:
        """
        安装 Root 应用
        
        Args:
            device_controller: 设备控制器
        
        Returns:
            bool: 是否安装成功
        """
        pass
    
    @abstractmethod
    def patch_boot(self, boot_img: Path, output_dir: Path) -> Path:
        """
        修补 boot.img
        
        Args:
            boot_img: 原始 boot.img 路径
            output_dir: 输出目录
        
        Returns:
            Path: 修补后的 boot.img 路径
        """
        pass
    
    @abstractmethod
    def install_modules(self, device_controller, modules: List[Path]) -> bool:
        """
        安装模块
        
        Args:
            device_controller: 设备控制器
            modules: 模块文件路径列表
        
        Returns:
            bool: 是否全部安装成功
        """
        pass


class BootImageExtractor:
    """从刷机包中提取 boot.img"""
    
    def __init__(self, flash_package: Path):
        """
        初始化提取器
        
        Args:
            flash_package: 刷机包路径
        """
        self.flash_package = flash_package
    
    def extract_boot_img(self, output_dir: Path) -> Path:
        """
        从刷机包中提取 boot.img
        
        Args:
            output_dir: 输出目录
        
        Returns:
            Path: 提取的 boot.img 路径
        
        Raises:
            FileNotFoundError: 刷机包或 boot.img 不存在
            RuntimeError: 提取失败
        """
        logger.info(f"正在从刷机包提取 boot.img: {self.flash_package}")
        
        # 1. 验证刷机包存在
        if not self.flash_package.exists():
            raise FileNotFoundError(f"刷机包不存在: {self.flash_package}")
        
        # 确保输出目录存在
        output_dir.mkdir(parents=True, exist_ok=True)
        
        try:
            # 2. 打开刷机包(通常是 .zip 格式)
            with zipfile.ZipFile(self.flash_package, 'r') as zip_ref:
                # 3. 查找 boot.img
                # Google 刷机包结构: redfin-xxx/image-redfin-xxx.zip/boot.img
                boot_img_candidates = [
                    name for name in zip_ref.namelist()
                    if 'boot.img' in name.lower() and not name.startswith('__MACOSX')
                ]
                
                if not boot_img_candidates:
                    raise FileNotFoundError("刷机包中未找到 boot.img")
                
                # 4. 如果有多个候选,选择最可能的
                boot_img_path = self._select_boot_img(boot_img_candidates)
                logger.info(f"找到 boot.img: {boot_img_path}")
                
                # 5. 提取 boot.img
                # 注意: Google 刷机包是嵌套 zip,需要先提取内层 zip
                if boot_img_path.endswith('.zip'):
                    # 提取内层 zip
                    inner_zip_path = output_dir / "image.zip"
                    with zip_ref.open(boot_img_path) as inner_zip_file:
                        with open(inner_zip_path, 'wb') as f:
                            f.write(inner_zip_file.read())
                    
                    # 从内层 zip 提取 boot.img
                    with zipfile.ZipFile(inner_zip_path, 'r') as inner_zip:
                        boot_candidates = [n for n in inner_zip.namelist() if 'boot.img' in n.lower()]
                        if boot_candidates:
                            boot_img_name = boot_candidates[0]
                            inner_zip.extract(boot_img_name, output_dir)
                            extracted_boot = output_dir / boot_img_name
                        else:
                            raise FileNotFoundError("内层 zip 中未找到 boot.img")
                    
                    # 清理临时文件
                    inner_zip_path.unlink()
                else:
                    # 直接提取 boot.img
                    zip_ref.extract(boot_img_path, output_dir)
                    extracted_boot = output_dir / boot_img_path
                
                # 6. 重命名为标准名称
                final_boot = output_dir / "boot.img"
                if extracted_boot != final_boot:
                    if final_boot.exists():
                        final_boot.unlink()
                    extracted_boot.rename(final_boot)
                
                logger.info(f"✅ boot.img 提取完成: {final_boot}")
                return final_boot
                
        except zipfile.BadZipFile:
            raise RuntimeError(f"刷机包格式错误: {self.flash_package}")
        except Exception as e:
            raise RuntimeError(f"提取 boot.img 失败: {e}")
    
    def _select_boot_img(self, candidates: List[str]) -> str:
        """
        从多个候选中选择正确的 boot.img
        
        Args:
            candidates: 候选文件列表
        
        Returns:
            str: 选中的文件路径
        """
        # 优先级:
        # 1. image-xxx.zip (Google 刷机包的内层 zip)
        # 2. boot.img (直接的 boot.img)
        # 3. boot_a.img 或 boot_b.img (A/B 分区)
        
        for pattern in ['image-', 'boot.img', 'boot_a.img', 'boot_b.img']:
            for candidate in candidates:
                if pattern in candidate:
                    return candidate
        
        # 如果都不匹配,返回第一个
        return candidates[0]


class APatchCLIPatcher:
    """使用 APatch CLI 工具修补 boot.img"""
    
    def __init__(self, cli_path: Path, password: str):
        """
        初始化 CLI 修补器
        
        Args:
            cli_path: CLI 工具路径
            password: APatch 密码
        """
        self.cli_path = cli_path
        self.password = password
    
    def is_available(self) -> bool:
        """
        检查 CLI 工具是否可用
        
        Returns:
            bool: 是否可用
        """
        if not self.cli_path.exists():
            logger.warning(f"APatch CLI 工具不存在: {self.cli_path}")
            return False
        
        # 测试 CLI 工具是否可执行
        try:
            result = subprocess.run(
                [str(self.cli_path), "--version"],
                capture_output=True,
                text=True,
                timeout=5
            )
            if result.returncode == 0:
                logger.info(f"APatch CLI 版本: {result.stdout.strip()}")
                return True
        except Exception as e:
            logger.warning(f"APatch CLI 工具不可用: {e}")
        
        return False
    
    def patch_boot(self, boot_img: Path, output_dir: Path) -> Path:
        """
        使用 CLI 工具修补 boot.img
        
        Args:
            boot_img: 原始 boot.img 路径
            output_dir: 输出目录
        
        Returns:
            Path: 修补后的 boot.img 路径
        
        Raises:
            RuntimeError: 修补失败
        """
        logger.info(f"使用 APatch CLI 修补 boot.img: {boot_img}")
        
        # 确保输出目录存在
        output_dir.mkdir(parents=True, exist_ok=True)
        
        # 1. 构造输出文件名
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        patched_boot = output_dir / f"apatch_patched_{timestamp}.img"
        
        # 2. 构造 CLI 命令
        # 注意: 这里的命令格式需要根据 APatch CLI 的实际接口调整
        cmd = [
            str(self.cli_path),
            "patch",
            "--input", str(boot_img),
            "--output", str(patched_boot),
            "--password", self.password,
            "--superkey", self.password,  # 可选: 超级密钥
        ]
        
        logger.info(f"执行命令: {' '.join(cmd[:6])} [密码已隐藏]")
        
        # 3. 执行修补
        try:
            result = subprocess.run(
                cmd,
                capture_output=True,
                text=True,
                timeout=300  # 5 分钟超时
            )
            
            # 4. 检查结果
            if result.returncode != 0:
                logger.error(f"APatch CLI 修补失败: {result.stderr}")
                raise RuntimeError(f"APatch CLI 修补失败: {result.stderr}")
            
            # 5. 验证输出文件
            if not patched_boot.exists():
                raise FileNotFoundError(f"修补后的 boot.img 不存在: {patched_boot}")
            
            logger.info(f"✅ boot.img 修补完成: {patched_boot}")
            logger.info(f"修补输出: {result.stdout}")
            
            return patched_boot
            
        except subprocess.TimeoutExpired:
            logger.error("APatch CLI 修补超时(5 分钟)")
            raise RuntimeError("APatch CLI 修补超时")
        except Exception as e:
            logger.error(f"APatch CLI 修补失败: {e}")
            raise
    
    def get_version(self) -> str:
        """
        获取 APatch CLI 版本
        
        Returns:
            str: 版本号
        """
        try:
            result = subprocess.run(
                [str(self.cli_path), "--version"],
                capture_output=True,
                text=True,
                timeout=5
            )
            return result.stdout.strip()
        except Exception:
            return "unknown"


class APatchAdapter(RootMethodAdapter):
    """APatch 适配器"""
    
    def __init__(
        self,
        apk_path: Path,
        password: str,
        cli_path: Optional[Path] = None,
        use_cli: bool = True,
        fallback_to_ui: bool = True
    ):
        """
        初始化 APatch 适配器
        
        Args:
            apk_path: APatch APK 路径
            password: APatch 密码
            cli_path: CLI 工具路径(可选)
            use_cli: 是否优先使用 CLI 工具
            fallback_to_ui: CLI 失败时是否回退到 UI 自动化
        """
        # 确保 apk_path 是 Path 对象
        self.apk_path = Path(apk_path) if isinstance(apk_path, str) else apk_path
        self.password = password
        # 确保 cli_path 是 Path 对象（如果提供）
        self.cli_path = Path(cli_path) if isinstance(cli_path, str) else cli_path
        self.use_cli = use_cli
        self.fallback_to_ui = fallback_to_ui
        
        # 初始化 CLI 修补器
        self.cli_patcher = None
        if cli_path and use_cli:
            self.cli_patcher = APatchCLIPatcher(self.cli_path, password)
    
    def install_app(self, device_controller) -> bool:
        """
        安装 APatch 应用
        
        Args:
            device_controller: 设备控制器
        
        Returns:
            bool: 是否安装成功
        """
        logger.info(f"安装 APatch: {self.apk_path}")
        
        if not self.apk_path.exists():
            logger.error(f"APatch APK 不存在: {self.apk_path}")
            return False
        
        try:
            return device_controller.adb_install(str(self.apk_path))
        except Exception as e:
            logger.error(f"安装 APatch 失败: {e}")
            return False
    
    def patch_boot(self, boot_img: Path, output_dir: Path) -> Path:
        """
        修补 boot.img
        
        Args:
            boot_img: 原始 boot.img 路径
            output_dir: 输出目录
        
        Returns:
            Path: 修补后的 boot.img 路径
        
        Raises:
            RuntimeError: 修补失败
        """
        # 1. 尝试使用 CLI 工具修补
        if self.cli_patcher and self.cli_patcher.is_available():
            try:
                logger.info("使用 APatch CLI 工具修补 boot.img")
                return self.cli_patcher.patch_boot(boot_img, output_dir)
            except Exception as e:
                logger.warning(f"CLI 修补失败: {e}")
                if not self.fallback_to_ui:
                    raise
                logger.info("回退到 UI 自动化修补")
        
        # 2. 回退到 UI 自动化修补
        return self._patch_boot_via_ui(boot_img, output_dir)
    
    def _patch_boot_via_ui(self, boot_img: Path, output_dir: Path) -> Path:
        """
        通过 UI 自动化修补 boot.img
        
        Args:
            boot_img: 原始 boot.img 路径
            output_dir: 输出目录
        
        Returns:
            Path: 修补后的 boot.img 路径
        
        Raises:
            RuntimeError: 修补失败
        """
        logger.info("使用 UI 自动化修补 boot.img")
        
        # 注意: 这里需要设备控制器和 UI 自动化模块
        # 由于循环依赖问题,这里只提供接口,实际实现在调用方
        raise NotImplementedError("UI 自动化修补需要在调用方实现")
    
    def install_modules(self, device_controller, modules: List[Path]) -> bool:
        """
        安装 APatch 模块
        
        Args:
            device_controller: 设备控制器
            modules: 模块文件路径列表
        
        Returns:
            bool: 是否全部安装成功
        """
        logger.info(f"安装 {len(modules)} 个 APatch 模块")
        
        # 1. 推送模块到设备
        success_count = 0
        for module in modules:
            if not module.exists():
                logger.error(f"模块不存在: {module}")
                continue
            
            try:
                # 推送到 /sdcard/Download/
                device_path = f"/sdcard/Download/{module.name}"
                if device_controller.adb_push(str(module), device_path):
                    logger.info(f"✅ 模块已推送: {module.name}")
                    success_count += 1
                else:
                    logger.error(f"❌ 模块推送失败: {module.name}")
            except Exception as e:
                logger.error(f"推送模块失败: {module.name}, {e}")
        
        logger.info(f"模块推送完成: {success_count}/{len(modules)}")
        
        # 2. UI 自动化安装(需要在调用方实现)
        logger.info("请使用 UI 自动化模块完成模块安装")
        
        return success_count == len(modules)


class MagiskAdapter(RootMethodAdapter):
    """Magisk 适配器(未来扩展)"""
    
    def __init__(self, apk_path: Path, version: str = "27.0"):
        """
        初始化 Magisk 适配器
        
        Args:
            apk_path: Magisk APK 路径
            version: Magisk 版本
        """
        # 确保 apk_path 是 Path 对象
        self.apk_path = Path(apk_path) if isinstance(apk_path, str) else apk_path
        self.version = version
    
    def install_app(self, device_controller) -> bool:
        """安装 Magisk 应用"""
        logger.info(f"安装 Magisk: {self.apk_path}")
        
        if not self.apk_path.exists():
            logger.error(f"Magisk APK 不存在: {self.apk_path}")
            return False
        
        try:
            return device_controller.adb_install(str(self.apk_path))
        except Exception as e:
            logger.error(f"安装 Magisk 失败: {e}")
            return False
    
    def patch_boot(self, boot_img: Path, output_dir: Path) -> Path:
        """修补 boot.img"""
        # TODO: 实现 Magisk 修补逻辑
        raise NotImplementedError("Magisk 修补功能尚未实现")
    
    def install_modules(self, device_controller, modules: List[Path]) -> bool:
        """安装 Magisk 模块"""
        # TODO: 实现 Magisk 模块安装逻辑
        raise NotImplementedError("Magisk 模块安装功能尚未实现")


class KernelSUAdapter(RootMethodAdapter):
    """KernelSU 适配器(未来扩展)"""
    
    def __init__(self):
        """初始化 KernelSU 适配器"""
        pass
    
    def install_app(self, device_controller) -> bool:
        """安装 KernelSU 应用"""
        # TODO: 实现 KernelSU 安装逻辑
        raise NotImplementedError("KernelSU 安装功能尚未实现")
    
    def patch_boot(self, boot_img: Path, output_dir: Path) -> Path:
        """修补 boot.img"""
        # TODO: 实现 KernelSU 修补逻辑
        raise NotImplementedError("KernelSU 修补功能尚未实现")
    
    def install_modules(self, device_controller, modules: List[Path]) -> bool:
        """安装 KernelSU 模块"""
        # TODO: 实现 KernelSU 模块安装逻辑
        raise NotImplementedError("KernelSU 模块安装功能尚未实现")


class RootMethodFactory:
    """Root 方案工厂"""
    
    # 支持的 Root 方案
    SUPPORTED_METHODS = {"apatch"}
    
    @staticmethod
    def create(config: dict) -> RootMethodAdapter:
        """
        根据配置创建 Root 适配器
        
        Args:
            config: 配置字典
        
        Returns:
            RootMethodAdapter: Root 适配器实例
        
        Raises:
            ValueError: 不支持的 Root 方案
        """
        method = config.get("method", "apatch").lower()
        
        # 检查是否支持
        if method not in RootMethodFactory.SUPPORTED_METHODS:
            raise ValueError(
                f"不支持的 Root 方案: {method}\n"
                f"当前仅支持: {', '.join(RootMethodFactory.SUPPORTED_METHODS)}\n"
                f"Magisk 和 KernelSU 支持正在开发中"
            )
        
        if method == "apatch":
            apatch_config = config.get("apatch", {})
            return APatchAdapter(
                apk_path=Path(apatch_config.get("apk_path", "resources/apks/apatch.apk")),
                password=apatch_config.get("password", ""),
                cli_path=Path(config.get("apatch_cli", {}).get("cli_path", "resources/tools/apatch-cli")),
                use_cli=config.get("apatch_cli", {}).get("enabled", True),
                fallback_to_ui=config.get("apatch_cli", {}).get("fallback_to_ui", True)
            )
        
        # 不应该执行到这里
        raise ValueError(f"未知的 Root 方案: {method}")
