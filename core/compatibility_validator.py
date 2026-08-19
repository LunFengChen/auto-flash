"""
设备兼容性验证器 - 验证设备型号、Android 版本、Build 号、boot.img 是否匹配

设计原则:
1. 验证设备信息提取和验证
2. boot.img 完整性验证
3. Build 号匹配验证
4. 设备指纹验证
"""

import logging
import hashlib
import re
from dataclasses import dataclass
from pathlib import Path
from typing import Optional

logger = logging.getLogger(__name__)


@dataclass
class DeviceInfo:
    """设备信息"""
    serial: str
    model: str  # 设备代号,如 "redfin"
    brand: str  # 品牌,如 "google"
    product: str  # 产品名,如 "redfin"
    android_version: str  # Android 版本,如 "13"
    build_id: str  # Build ID,如 "TQ3A.230805.001"
    build_fingerprint: str  # 设备指纹
    security_patch: str  # 安全补丁日期


@dataclass
class BootImageInfo:
    """Boot 镜像信息"""
    file_path: Path
    sha256: str
    size: int
    build_id: Optional[str]  # 从 boot.img 提取的 Build ID
    kernel_version: Optional[str]


class CompatibilityValidator:
    """设备兼容性验证器"""
    
    def __init__(self, device_controller):
        """
        初始化验证器
        
        Args:
            device_controller: 设备控制器
        """
        self.device = device_controller
        self.device_info: Optional[DeviceInfo] = None
    
    def get_device_info(self) -> DeviceInfo:
        """
        获取设备信息
        
        Returns:
            DeviceInfo: 设备信息
        """
        if self.device_info is None:
            logger.info("正在获取设备信息...")
            
            try:
                self.device_info = DeviceInfo(
                    serial=self._get_prop("ro.serialno"),
                    model=self._get_prop("ro.product.device"),
                    brand=self._get_prop("ro.product.brand"),
                    product=self._get_prop("ro.product.name"),
                    android_version=self._get_prop("ro.build.version.release"),
                    build_id=self._get_prop("ro.build.id"),
                    build_fingerprint=self._get_prop("ro.build.fingerprint"),
                    security_patch=self._get_prop("ro.build.version.security_patch")
                )
                
                logger.info(f"设备信息:")
                logger.info(f"  型号: {self.device_info.model}")
                logger.info(f"  品牌: {self.device_info.brand}")
                logger.info(f"  Android 版本: {self.device_info.android_version}")
                logger.info(f"  Build ID: {self.device_info.build_id}")
                logger.info(f"  安全补丁: {self.device_info.security_patch}")
                
            except Exception as e:
                logger.error(f"获取设备信息失败: {e}")
                raise
        
        return self.device_info
    
    def _get_prop(self, prop_name: str) -> str:
        """
        获取设备属性
        
        Args:
            prop_name: 属性名
        
        Returns:
            str: 属性值
        """
        try:
            result = self.device.adb_shell(f"getprop {prop_name}")
            return result.strip()
        except Exception as e:
            logger.warning(f"获取属性 {prop_name} 失败: {e}")
            return ""
    
    def validate_device_model(self, expected_model: str, strict: bool = True) -> bool:
        """
        验证设备型号
        
        Args:
            expected_model: 期望的设备型号
            strict: 是否严格匹配
        
        Returns:
            bool: 是否匹配
        """
        device_info = self.get_device_info()
        
        def normalize(s: str) -> str:
            # 归一化：小写 + 去掉分隔符，使 oneplus-8t / OnePlus8T / kebab 可互比
            return re.sub(r"[^a-z0-9]", "", s.lower())
        
        expected_norm = normalize(expected_model)
        actual_norm = normalize(device_info.model)
        
        if strict:
            # 严格匹配（归一化后）
            if expected_norm != actual_norm:
                logger.error(f"❌ 设备型号不匹配:")
                logger.error(f"   期望: {expected_model}")
                logger.error(f"   实际: {device_info.model}")
                return False
        else:
            # 模糊匹配
            if expected_norm not in actual_norm:
                logger.error(f"❌ 设备型号不匹配:")
                logger.error(f"   期望包含: {expected_model}")
                logger.error(f"   实际: {device_info.model}")
                return False
        
        logger.info(f"✅ 设备型号验证通过: {device_info.model}")
        return True
    
    def validate_boot_image(
        self,
        boot_img: Path,
        expected_build: Optional[str] = None,
        verify_sha256: Optional[str] = None
    ) -> bool:
        """
        验证 boot.img 完整性和匹配性
        
        Args:
            boot_img: boot.img 路径
            expected_build: 期望的 Build ID(可选)
            verify_sha256: 期望的 SHA256(可选)
        
        Returns:
            bool: 是否验证通过
        """
        logger.info(f"正在验证 boot.img: {boot_img}")
        
        # 1. 验证文件存在
        if not boot_img.exists():
            logger.error(f"❌ boot.img 不存在: {boot_img}")
            return False
        
        # 2. 获取 boot.img 信息
        try:
            boot_info = self.get_boot_image_info(boot_img)
        except Exception as e:
            logger.error(f"❌ 获取 boot.img 信息失败: {e}")
            return False
        
        logger.info(f"boot.img 信息:")
        logger.info(f"  大小: {boot_info.size / 1024 / 1024:.2f} MB")
        logger.info(f"  SHA256: {boot_info.sha256}")
        if boot_info.build_id:
            logger.info(f"  Build ID: {boot_info.build_id}")
        
        # 3. 验证 SHA256(如果指定)
        if verify_sha256:
            if boot_info.sha256.lower() != verify_sha256.lower():
                logger.error(f"❌ boot.img SHA256 不匹配:")
                logger.error(f"   期望: {verify_sha256}")
                logger.error(f"   实际: {boot_info.sha256}")
                return False
            logger.info(f"✅ SHA256 验证通过")
        
        # 4. 验证 Build ID(如果指定)
        if expected_build and boot_info.build_id:
            if boot_info.build_id != expected_build:
                logger.error(f"❌ boot.img Build ID 不匹配:")
                logger.error(f"   期望: {expected_build}")
                logger.error(f"   实际: {boot_info.build_id}")
                return False
            logger.info(f"✅ Build ID 验证通过")
        
        # 5. 验证与设备 Build ID 是否匹配
        device_info = self.get_device_info()
        if boot_info.build_id and boot_info.build_id != device_info.build_id:
            logger.warning(f"⚠️  boot.img Build ID ({boot_info.build_id}) 与设备 Build ID ({device_info.build_id}) 不匹配")
            logger.warning(f"⚠️  这可能导致设备无法启动!")
            return False
        
        logger.info(f"✅ boot.img 验证通过")
        return True
    
    def get_boot_image_info(self, boot_img: Path) -> BootImageInfo:
        """
        获取 boot.img 信息
        
        Args:
            boot_img: boot.img 路径
        
        Returns:
            BootImageInfo: boot.img 信息
        """
        # 计算 SHA256
        sha256 = self._calculate_sha256(boot_img)
        
        # 获取文件大小
        size = boot_img.stat().st_size
        
        # 尝试提取 Build ID
        build_id = self.extract_build_id_from_boot(boot_img)
        
        return BootImageInfo(
            file_path=boot_img,
            sha256=sha256,
            size=size,
            build_id=build_id,
            kernel_version=None  # 可选: 提取内核版本
        )
    
    def _calculate_sha256(self, file_path: Path) -> str:
        """
        计算文件 SHA256
        
        Args:
            file_path: 文件路径
        
        Returns:
            str: SHA256 哈希值
        """
        sha256 = hashlib.sha256()
        with open(file_path, "rb") as f:
            for chunk in iter(lambda: f.read(4096), b""):
                sha256.update(chunk)
        return sha256.hexdigest()
    
    def extract_build_id_from_boot(self, boot_img: Path) -> Optional[str]:
        """
        从 boot.img 提取 Build ID(简化实现)
        
        Args:
            boot_img: boot.img 路径
        
        Returns:
            Optional[str]: Build ID,未找到返回 None
        """
        # 注意: 这需要解析 Android boot.img 格式
        # 简化实现: 搜索 Build ID 字符串
        try:
            with open(boot_img, "rb") as f:
                content = f.read()
                # 搜索类似 "TQ3A.230805.001" 的 Build ID 模式
                # 格式: [A-Z]{2,4}\.[0-9]{6}\.[0-9]{3}
                match = re.search(rb'[A-Z]{2,4}\.[0-9]{6}\.[0-9]{3}', content)
                if match:
                    build_id = match.group(0).decode('ascii')
                    logger.debug(f"从 boot.img 提取到 Build ID: {build_id}")
                    return build_id
        except Exception as e:
            logger.warning(f"无法从 boot.img 提取 Build ID: {e}")
        
        return None
    
    def validate_android_version(self, min_version: int) -> bool:
        """
        验证 Android 版本
        
        Args:
            min_version: 最低 Android 版本
        
        Returns:
            bool: 是否满足要求
        """
        device_info = self.get_device_info()
        
        try:
            current_version = int(device_info.android_version.split('.')[0])
            
            if current_version < min_version:
                logger.error(f"❌ Android 版本过低:")
                logger.error(f"   最低要求: Android {min_version}")
                logger.error(f"   当前版本: Android {current_version}")
                return False
            
            logger.info(f"✅ Android 版本验证通过: Android {current_version}")
            return True
            
        except Exception as e:
            logger.error(f"❌ 解析 Android 版本失败: {e}")
            return False
    
    def validate_fingerprint(self, expected_fingerprint: str) -> bool:
        """
        验证设备指纹
        
        Args:
            expected_fingerprint: 期望的设备指纹
        
        Returns:
            bool: 是否匹配
        """
        device_info = self.get_device_info()
        
        if device_info.build_fingerprint != expected_fingerprint:
            logger.error(f"❌ 设备指纹不匹配:")
            logger.error(f"   期望: {expected_fingerprint}")
            logger.error(f"   实际: {device_info.build_fingerprint}")
            return False
        
        logger.info(f"✅ 设备指纹验证通过")
        return True
    
    def validate_all(
        self,
        expected_model: str,
        boot_img: Optional[Path] = None,
        expected_build: Optional[str] = None,
        min_android_version: Optional[int] = None,
        strict: bool = False
    ) -> bool:
        """
        执行完整的兼容性验证
        
        Args:
            expected_model: 期望的设备型号
            boot_img: boot.img 路径(可选)
            expected_build: 期望的 Build ID(可选)
            min_android_version: 最低 Android 版本(可选)
            strict: 是否严格模式
        
        Returns:
            bool: 是否全部验证通过
        """
        logger.info("=" * 60)
        logger.info("开始设备兼容性验证")
        logger.info("=" * 60)
        
        all_passed = True
        
        # 1. 验证设备型号
        if not self.validate_device_model(expected_model, strict=strict):
            all_passed = False
            if strict:
                logger.error("严格模式: 设备型号验证失败,终止验证")
                return False
        
        # 2. 验证 Android 版本
        if min_android_version:
            if not self.validate_android_version(min_android_version):
                all_passed = False
                if strict:
                    logger.error("严格模式: Android 版本验证失败,终止验证")
                    return False
        
        # 3. 验证 boot.img
        if boot_img:
            if not self.validate_boot_image(boot_img, expected_build):
                all_passed = False
                if strict:
                    logger.error("严格模式: boot.img 验证失败,终止验证")
                    return False
        
        logger.info("=" * 60)
        if all_passed:
            logger.info("✅ 所有兼容性验证通过")
        else:
            logger.warning("⚠️  部分兼容性验证未通过")
        logger.info("=" * 60)
        
        return all_passed
