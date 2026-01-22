"""
资源管理器 - Resource Manager

管理通用资源和设备特定资源，支持资源查找、去重和版本管理。
"""

import hashlib
import platform
from dataclasses import dataclass
from pathlib import Path
from typing import Dict, List, Optional
from loguru import logger


@dataclass
class ResourceInfo:
    """资源信息数据类"""
    name: str
    path: Path
    type: str  # "apk", "module", "tool", "script"
    is_device_specific: bool
    sha256: Optional[str] = None
    version: Optional[str] = None
    size: int = 0


class ResourceManager:
    """
    资源管理器 - 支持通用资源和设备特定资源
    
    资源查找优先级：设备特定 > 通用
    """
    
    def __init__(self, device_model: str):
        """
        初始化资源管理器
        
        Args:
            device_model: 设备型号，如 "redfin"
        """
        self.device_model = device_model
        self.device_dir = Path(f"devices/{device_model}")
        self.common_dir = Path("resources/common")
        self.cache: Dict[str, ResourceInfo] = {}
        
        logger.info(f"资源管理器初始化: 设备={device_model}")
        logger.debug(f"设备目录: {self.device_dir}")
        logger.debug(f"通用资源目录: {self.common_dir}")
    
    def find_apk(self, apk_name: str) -> Path:
        """
        查找 APK - 优先设备特定，回退到通用
        
        Args:
            apk_name: APK 文件名，如 "apatch.apk"
        
        Returns:
            APK 文件路径
        
        Raises:
            FileNotFoundError: 如果 APK 不存在
        """
        # 1. 先找设备特定的
        device_apk = self.device_dir / "resources/apks" / apk_name
        if device_apk.exists():
            logger.info(f"✓ 使用设备特定 APK: {device_apk}")
            return device_apk
        
        # 2. 回退到通用资源
        common_apk = self.common_dir / "apks" / apk_name
        if common_apk.exists():
            logger.info(f"✓ 使用通用 APK: {common_apk}")
            return common_apk
        
        # 3. 未找到
        logger.error(f"✗ 未找到 APK: {apk_name}")
        raise FileNotFoundError(f"未找到 APK: {apk_name}")
    
    def find_module(self, module_name: str) -> Path:
        """
        查找模块 - 优先设备特定，回退到通用
        
        Args:
            module_name: 模块文件名，如 "moveCert.zip"
        
        Returns:
            模块文件路径
        
        Raises:
            FileNotFoundError: 如果模块不存在
        """
        # 1. 设备特定模块
        device_module = self.device_dir / "resources/modules" / module_name
        if device_module.exists():
            logger.info(f"✓ 使用设备特定模块: {device_module}")
            return device_module
        
        # 2. 通用模块
        common_module = self.common_dir / "modules" / module_name
        if common_module.exists():
            logger.info(f"✓ 使用通用模块: {common_module}")
            return common_module
        
        # 3. 未找到
        logger.error(f"✗ 未找到模块: {module_name}")
        raise FileNotFoundError(f"未找到模块: {module_name}")
    
    def find_tool(self, tool_name: str) -> Path:
        """
        查找二进制工具 - 优先设备特定，回退到通用
        
        Args:
            tool_name: 工具名称，如 "r0gson.dex"
        
        Returns:
            工具文件路径
        
        Raises:
            FileNotFoundError: 如果工具不存在
        """
        # 1. 设备特定二进制工具
        device_tool = self.device_dir / "resources/binary" / tool_name
        if device_tool.exists():
            logger.info(f"✓ 使用设备特定工具: {device_tool}")
            return device_tool
        
        # 2. 通用二进制工具
        common_tool = self.common_dir / "binary" / tool_name
        if common_tool.exists():
            logger.info(f"✓ 使用通用工具: {common_tool}")
            return common_tool
        
        # 3. 未找到
        logger.error(f"✗ 未找到工具: {tool_name}")
        raise FileNotFoundError(f"未找到工具: {tool_name}")
    
    def list_all_apks(self) -> List[ResourceInfo]:
        """
        列出所有可用的 APK（通用 + 设备特定）
        
        Returns:
            APK 资源信息列表
        """
        apks = {}
        
        # 1. 加载通用 APK
        common_apk_dir = self.common_dir / "apks"
        if common_apk_dir.exists():
            for apk_path in common_apk_dir.glob("*.apk"):
                apks[apk_path.name] = ResourceInfo(
                    name=apk_path.name,
                    path=apk_path,
                    type="apk",
                    is_device_specific=False,
                    sha256=self._calculate_sha256(apk_path),
                    size=apk_path.stat().st_size
                )
        
        # 2. 加载设备特定 APK（覆盖同名的通用 APK）
        device_apk_dir = self.device_dir / "resources/apks"
        if device_apk_dir.exists():
            for apk_path in device_apk_dir.glob("*.apk"):
                apks[apk_path.name] = ResourceInfo(
                    name=apk_path.name,
                    path=apk_path,
                    type="apk",
                    is_device_specific=True,
                    sha256=self._calculate_sha256(apk_path),
                    size=apk_path.stat().st_size
                )
        
        logger.info(f"找到 {len(apks)} 个 APK")
        return list(apks.values())
    
    def list_all_modules(self) -> List[ResourceInfo]:
        """
        列出所有可用的模块（通用 + 设备特定）
        
        扫描 modules/ 下的所有子目录:
        - kpm/ - KPM 内核模块(.kpm)
        - zip/ - 通用模块(.zip)
        - lsp/ - LSP 模块(.zip)
        - zygisk/ - Zygisk 模块(.zip)
        
        Returns:
            模块资源信息列表
        """
        modules = {}
        
        # 扫描通用模块目录
        common_module_dir = self.common_dir / "modules"
        if common_module_dir.exists():
            self._scan_module_directory(common_module_dir, modules, is_device_specific=False)
        
        # 扫描设备特定模块目录
        device_module_dir = self.device_dir / "resources/modules"
        if device_module_dir.exists():
            self._scan_module_directory(device_module_dir, modules, is_device_specific=True)
        
        logger.info(f"找到 {len(modules)} 个模块")
        return list(modules.values())
    
    def list_all_binaries(self) -> List[ResourceInfo]:
        """
        列出所有可用的二进制工具（通用 + 设备特定）
        
        Returns:
            二进制工具资源信息列表
        """
        binaries = {}
        
        # 1. 加载通用二进制工具
        common_binary_dir = self.common_dir / "binary"
        if common_binary_dir.exists():
            for binary_path in common_binary_dir.iterdir():
                if binary_path.is_file() and not binary_path.name.startswith('.'):
                    binaries[binary_path.name] = ResourceInfo(
                        name=binary_path.name,
                        path=binary_path,
                        type="binary",
                        is_device_specific=False,
                        sha256=self._calculate_sha256(binary_path),
                        size=binary_path.stat().st_size
                    )
        
        # 2. 加载设备特定二进制工具（覆盖同名的通用工具）
        device_binary_dir = self.device_dir / "resources/binary"
        if device_binary_dir.exists():
            for binary_path in device_binary_dir.iterdir():
                if binary_path.is_file() and not binary_path.name.startswith('.'):
                    binaries[binary_path.name] = ResourceInfo(
                        name=binary_path.name,
                        path=binary_path,
                        type="binary",
                        is_device_specific=True,
                        sha256=self._calculate_sha256(binary_path),
                        size=binary_path.stat().st_size
                    )
        
        logger.info(f"找到 {len(binaries)} 个二进制工具")
        return list(binaries.values())
    
    def _scan_module_directory(
        self,
        base_dir: Path,
        modules: Dict[str, ResourceInfo],
        is_device_specific: bool
    ):
        """
        递归扫描模块目录
        
        Args:
            base_dir: 基础目录
            modules: 模块字典(用于去重)
            is_device_specific: 是否为设备特定资源
        """
        # 扫描 .zip 和 .kpm 文件
        for pattern in ["**/*.zip", "**/*.kpm"]:
            for module_path in base_dir.glob(pattern):
                # 跳过隐藏文件和临时文件
                if module_path.name.startswith('.') or module_path.name.endswith('.tmp'):
                    continue
                
                # 设备特定资源优先级更高,覆盖同名的通用资源
                if module_path.name not in modules or is_device_specific:
                    modules[module_path.name] = ResourceInfo(
                        name=module_path.name,
                        path=module_path,
                        type="module",
                        is_device_specific=is_device_specific,
                        sha256=self._calculate_sha256(module_path),
                        size=module_path.stat().st_size
                    )
    
    def verify_resource_integrity(
        self,
        resource: ResourceInfo,
        expected_sha256: str
    ) -> bool:
        """
        验证资源完整性
        
        Args:
            resource: 资源信息
            expected_sha256: 期望的 SHA256 值
        
        Returns:
            验证是否通过
        """
        actual_sha256 = self._calculate_sha256(resource.path)
        
        if actual_sha256 != expected_sha256:
            logger.error(f"✗ 资源完整性验证失败: {resource.name}")
            logger.error(f"  期望: {expected_sha256}")
            logger.error(f"  实际: {actual_sha256}")
            return False
        
        logger.info(f"✓ 资源完整性验证通过: {resource.name}")
        return True
    
    def get_flash_script(self) -> Path:
        """
        获取刷机脚本（根据操作系统）
        
        支持新的目录结构：devices/{model}/{build}/firmware/flash-all.{bat|sh}
        
        Returns:
            刷机脚本路径
        
        Raises:
            FileNotFoundError: 如果刷机脚本不存在
        """
        system = platform.system()
        
        if system == "Windows":
            script_name = "flash-all.bat"
        else:
            script_name = "flash-all.sh"
        
        # 在设备目录下递归查找刷机脚本
        # 支持新结构: devices/redfin/TQ3A.230901.001.C2/firmware/flash-all.sh
        for script_path in self.device_dir.rglob(script_name):
            logger.info(f"✓ 找到刷机脚本: {script_path}")
            return script_path
        
        # 未找到
        logger.error(f"✗ 刷机脚本不存在: {script_name}")
        raise FileNotFoundError(f"刷机脚本不存在: {script_name}")
    
    def _calculate_sha256(self, file_path: Path) -> str:
        """
        计算文件 SHA256
        
        Args:
            file_path: 文件路径
        
        Returns:
            SHA256 哈希值（十六进制字符串）
        """
        sha256 = hashlib.sha256()
        
        try:
            with open(file_path, "rb") as f:
                for chunk in iter(lambda: f.read(4096), b""):
                    sha256.update(chunk)
            return sha256.hexdigest()
        except Exception as e:
            logger.warning(f"计算 SHA256 失败: {file_path}, {e}")
            return ""
    
    def get_resource_info(self, resource_path: Path) -> ResourceInfo:
        """
        获取资源详细信息
        
        Args:
            resource_path: 资源文件路径
        
        Returns:
            资源信息
        """
        # 判断资源类型
        suffix = resource_path.suffix.lower()
        if suffix == ".apk":
            resource_type = "apk"
        elif suffix in [".zip", ".kpm"]:
            resource_type = "module"
        elif suffix in [".bat", ".sh"]:
            resource_type = "script"
        else:
            resource_type = "binary"
        
        # 判断是否为设备特定资源
        is_device_specific = str(self.device_dir) in str(resource_path)
        
        return ResourceInfo(
            name=resource_path.name,
            path=resource_path,
            type=resource_type,
            is_device_specific=is_device_specific,
            sha256=self._calculate_sha256(resource_path),
            size=resource_path.stat().st_size if resource_path.exists() else 0
        )


# 测试代码
if __name__ == "__main__":
    # 配置日志
    logger.add("logs/resource_manager_test.log", rotation="10 MB")
    
    # 测试资源管理器
    rm = ResourceManager("pixel5")
    
    # 列出所有 APK
    apks = rm.list_all_apks()
    print(f"\n找到 {len(apks)} 个 APK:")
    for apk in apks:
        print(f"  - {apk.name} ({'设备特定' if apk.is_device_specific else '通用'})")
    
    # 列出所有模块
    modules = rm.list_all_modules()
    print(f"\n找到 {len(modules)} 个模块:")
    for module in modules:
        print(f"  - {module.name} ({'设备特定' if module.is_device_specific else '通用'})")
    
    # 列出所有二进制工具
    binaries = rm.list_all_binaries()
    print(f"\n找到 {len(binaries)} 个二进制工具:")
    for binary in binaries:
        print(f"  - {binary.name} ({'设备特定' if binary.is_device_specific else '通用'})")
