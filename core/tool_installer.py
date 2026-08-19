"""
工具安装器 - Tool Installer

负责安装 APK 和推送二进制工具到设备
"""

from pathlib import Path
from typing import List, Optional
from loguru import logger

from .device_controller import DeviceController


class ToolInstaller:
    """工具安装器 - 安装 APK 和推送二进制工具"""
    
    def __init__(
        self,
        device_controller: DeviceController,
        common_resources_dir: Path = Path("resources/common")
    ):
        """
        初始化工具安装器
        
        Args:
            device_controller: 设备控制器
            common_resources_dir: 通用资源目录
        """
        self.device_controller = device_controller
        self.common_resources_dir = common_resources_dir
        
        logger.info("工具安装器初始化完成")
    
    def install_apks(
        self,
        install_root_apk: bool = True,
        root_method: str = "apatch",
        root_config: dict = None,
        extra_apks: List[str] = None
    ) -> tuple[int, int]:
        """
        安装 APK
        
        策略：
        1. Root APK（APatch/Magisk）- 根据 root_method 选择
        2. common/apks/ 下的所有 APK - 全装
        3. 额外指定的 APK - 可选
        
        Args:
            install_root_apk: 是否安装 Root APK
            root_method: Root 方案（apatch/magisk）
            root_config: Root 配置
            extra_apks: 额外的 APK 路径列表（相对于 common_resources_dir）
        
        Returns:
            (成功数, 总数)
        """
        logger.info("=" * 60)
        logger.info("开始安装 APK")
        logger.info("=" * 60)
        
        apks_to_install = []
        
        # 1. Root APK（根据 root_method 选择）
        if install_root_apk and root_config:
            if root_method == "apatch":
                apk_path = root_config.get("apatch", {}).get("apk_path")
                if apk_path:
                    full_path = self.common_resources_dir / apk_path
                    if full_path.exists():
                        logger.info(f"添加 APatch APK: {apk_path}")
                        apks_to_install.append(full_path)
                    else:
                        logger.warning(f"APatch APK 不存在: {full_path}")
            
            elif root_method == "magisk":
                apk_path = root_config.get("magisk", {}).get("apk_path")
                if apk_path:
                    full_path = self.common_resources_dir / apk_path
                    if full_path.exists():
                        logger.info(f"添加 Magisk APK: {apk_path}")
                        apks_to_install.append(full_path)
                    else:
                        logger.warning(f"Magisk APK 不存在: {full_path}")
        
        # 2. common/apks/ 下的所有 APK（全装）
        apks_dir = self.common_resources_dir / "apks"
        if apks_dir.exists():
            logger.info(f"扫描 apks/ 目录: {apks_dir}")
            for apk_file in apks_dir.glob("*.apk"):
                if apk_file.name != ".gitkeep":
                    logger.info(f"  添加 APK: {apk_file.name}")
                    apks_to_install.append(apk_file)
        
        # 3. 额外指定的 APK
        if extra_apks:
            logger.info("添加额外指定的 APK:")
            for apk_path in extra_apks:
                full_path = self.common_resources_dir / apk_path
                if full_path.exists():
                    logger.info(f"  添加 APK: {apk_path}")
                    apks_to_install.append(full_path)
                else:
                    logger.warning(f"  额外 APK 不存在: {full_path}")
        
        # 去重
        apks_to_install = list(set(apks_to_install))
        
        if not apks_to_install:
            logger.info("没有需要安装的 APK")
            return 0, 0
        
        # 安装
        logger.info(f"准备安装 {len(apks_to_install)} 个 APK")
        success_count = 0
        
        for apk_path in apks_to_install:
            logger.info(f"安装: {apk_path.name}")
            
            if self.device_controller.adb_install(apk_path):
                success_count += 1
            else:
                logger.warning(f"⚠ {apk_path.name} 安装失败")
        
        logger.info("=" * 60)
        logger.info(f"✓ APK 安装完成: {success_count}/{len(apks_to_install)}")
        logger.info("=" * 60)
        
        return success_count, len(apks_to_install)
    
    def push_binaries(
        self,
        target_dir: str = "/data/local/tmp",
        set_executable: bool = True
    ) -> tuple[int, int]:
        """
        推送二进制工具到设备
        
        策略：common/binary/ 下的所有文件 - 全推
        
        Args:
            target_dir: 目标目录
            set_executable: 是否设置可执行权限
        
        Returns:
            (成功数, 总数)
        """
        logger.info("=" * 60)
        logger.info("开始推送二进制工具")
        logger.info("=" * 60)
        
        binaries_to_push = []
        
        # 扫描 binary/ 目录（全推）
        binary_dir = self.common_resources_dir / "binary"
        if binary_dir.exists():
            logger.info(f"扫描 binary/ 目录: {binary_dir}")
            for binary_file in binary_dir.iterdir():
                if binary_file.is_file() and binary_file.name != ".gitkeep":
                    logger.info(f"  添加工具: {binary_file.name}")
                    binaries_to_push.append(binary_file)
        else:
            logger.warning(f"binary/ 目录不存在: {binary_dir}")
        
        if not binaries_to_push:
            logger.info("没有需要推送的二进制工具")
            return 0, 0
        
        # 推送
        logger.info(f"准备推送 {len(binaries_to_push)} 个工具到 {target_dir}")
        success_count = 0
        pushed_files = []
        
        for binary_path in binaries_to_push:
            logger.info(f"推送: {binary_path.name}")
            remote_path = f"{target_dir}/{binary_path.name}"
            
            if self.device_controller.adb_push(binary_path, remote_path):
                success_count += 1
                pushed_files.append(remote_path)
            else:
                logger.warning(f"⚠ {binary_path.name} 推送失败")
        
        # 设置可执行权限
        if set_executable and pushed_files:
            logger.info("设置可执行权限...")
            
            # 过滤出需要执行权限的文件（排除 .dex 等）
            executable_files = [
                f for f in pushed_files 
                if not f.endswith(('.dex', '.jar', '.apk'))
            ]
            
            if executable_files:
                chmod_cmd = f"chmod 755 {' '.join(executable_files)}"
                try:
                    self.device_controller.adb_shell(chmod_cmd)
                    logger.info(f"✓ 已设置 {len(executable_files)} 个文件的可执行权限")
                except Exception as e:
                    logger.warning(f"⚠ 设置可执行权限失败: {e}")
        
        logger.info("=" * 60)
        logger.info(f"✓ 二进制工具推送完成: {success_count}/{len(binaries_to_push)}")
        logger.info("=" * 60)
        
        return success_count, len(binaries_to_push)
    
    def push_modules(
        self,
        target_dir: str = "/sdcard/Download"
    ) -> tuple[int, int]:
        """
        推送模块（ZIP）到设备
        
        策略：common/modules/zip/ 下的所有 ZIP - 全推
        
        Args:
            target_dir: 目标目录
        
        Returns:
            (成功数, 总数)
        """
        logger.info("=" * 60)
        logger.info("开始推送模块")
        logger.info("=" * 60)
        
        modules_to_push = []
        
        # 扫描 modules/zip/ 目录（全推）
        zip_dir = self.common_resources_dir / "modules" / "zip"
        if zip_dir.exists():
            logger.info(f"扫描 modules/zip/ 目录: {zip_dir}")
            for zip_file in zip_dir.glob("*.zip"):
                logger.info(f"  添加模块: {zip_file.name}")
                modules_to_push.append(zip_file)
        else:
            logger.warning(f"modules/zip/ 目录不存在: {zip_dir}")
        
        if not modules_to_push:
            logger.info("没有需要推送的模块")
            return 0, 0
        
        # 推送
        logger.info(f"准备推送 {len(modules_to_push)} 个模块到 {target_dir}")
        success_count = 0
        
        for module_path in modules_to_push:
            logger.info(f"推送: {module_path.name}")
            remote_path = f"{target_dir}/{module_path.name}"
            
            if self.device_controller.adb_push(module_path, remote_path):
                success_count += 1
            else:
                logger.warning(f"⚠ {module_path.name} 推送失败")
        
        logger.info("=" * 60)
        logger.info(f"✓ 模块推送完成: {success_count}/{len(modules_to_push)}")
        logger.info("=" * 60)
        
        return success_count, len(modules_to_push)
    
    def install_modules_via_cli(
        self,
        root_method: str = "apatch",
        root_config: dict = None,
        module_dir: str = "/sdcard/Download"
    ) -> tuple[int, int]:
        """
        使用 Root 管理器 CLI 安装模块
        
        Magisk: 使用 `magisk --install-module <path>` 命令
        APatch: 使用 `apd module install <path>` 命令（apd 位于 /data/adb/apd）
        
        Args:
            root_method: Root 方案（apatch/magisk）
            root_config: Root 配置
            module_dir: 模块所在目录
        
        Returns:
            (成功数, 总数)
        """
        logger.info("=" * 60)
        logger.info("使用 Root 管理器 CLI 安装模块")
        logger.info("=" * 60)
        
        # 获取模块列表
        try:
            output = self.device_controller.adb_shell(f"ls {module_dir}/*.zip 2>/dev/null")
            module_files = [f.strip() for f in output.split('\n') if f.strip() and f.strip().endswith('.zip')]
        except Exception as e:
            logger.error(f"获取模块列表失败: {e}")
            return 0, 0
        
        if not module_files:
            logger.info("没有需要安装的模块")
            return 0, 0
        
        logger.info(f"找到 {len(module_files)} 个模块:")
        for module_file in module_files:
            logger.info(f"  - {Path(module_file).name}")
        
        success_count = 0
        
        if root_method == "magisk":
            # Magisk CLI 安装 - 使用官方命令
            logger.info("使用 Magisk CLI 安装模块")
            
            for module_file in module_files:
                module_name = Path(module_file).name
                logger.info(f"安装模块: {module_name}")
                
                try:
                    # Magisk CLI 命令: magisk --install-module <path>
                    cmd = f"su -c 'magisk --install-module {module_file}'"
                    output = self.device_controller.adb_shell(cmd, timeout=60)
                    
                    # Magisk 成功时通常输出包含 "Done" 或没有错误信息
                    if "error" not in output.lower() and "fail" not in output.lower():
                        logger.info(f"✓ {module_name} 安装成功")
                        success_count += 1
                    else:
                        logger.warning(f"⚠ {module_name} 安装失败: {output}")
                except Exception as e:
                    logger.error(f"✗ {module_name} 安装失败: {e}")
        
        elif root_method == "apatch":
            # APatch CLI 安装 - 使用 apd 命令
            logger.info("使用 APatch CLI (apd) 安装模块")
            
            for module_file in module_files:
                module_name = Path(module_file).name
                logger.info(f"安装模块: {module_name}")
                
                try:
                    # APatch CLI 命令: apd module install <path>
                    # 当前机型验证可用路径: /data/adb/apd
                    cmd = f'su -c "/data/adb/apd module install {module_file}"'
                    output = self.device_controller.adb_shell(cmd, timeout=60)
                    
                    # APatch 成功时通常输出包含 "success" 或没有错误信息
                    if "error" not in output.lower() and "fail" not in output.lower():
                        logger.info(f"✓ {module_name} 安装成功")
                        success_count += 1
                    else:
                        logger.warning(f"⚠ {module_name} 安装失败: {output}")
                except Exception as e:
                    logger.error(f"✗ {module_name} 安装失败: {e}")
        
        else:
            logger.error(f"不支持的 Root 方案: {root_method}")
            return 0, len(module_files)
        
        logger.info("=" * 60)
        logger.info(f"✓ 模块安装完成: {success_count}/{len(module_files)}")
        if success_count < len(module_files):
            logger.warning("部分模块安装失败，可能需要重启设备后生效")
        logger.info("=" * 60)
        
        return success_count, len(module_files)


# 测试代码
if __name__ == "__main__":
    logger.add("logs/tool_installer_test.log", rotation="10 MB")
    
    from .device_controller import DeviceController
    
    # 创建设备控制器
    dc = DeviceController()
    
    # 等待设备连接
    if dc.wait_for_adb(timeout=10):
        # 创建工具安装器
        installer = ToolInstaller(dc)
        
        # 测试安装 APK
        print("\n测试安装 APK:")
        success, total = installer.install_apks(
            install_root_apk=True,
            root_method="apatch",
            root_config={
                "apatch": {
                    "apk_path": "root/APatch_11142_166daa0_on_HEAD-release-signed.apk"
                }
            }
        )
        print(f"结果: {success}/{total}")
        
        # 测试推送二进制工具
        print("\n测试推送二进制工具:")
        success, total = installer.push_binaries()
        print(f"结果: {success}/{total}")
        
        # 测试推送模块
        print("\n测试推送模块:")
        success, total = installer.push_modules()
        print(f"结果: {success}/{total}")
    else:
        print("未检测到设备")
