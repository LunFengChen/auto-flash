"""
设备控制器 - Device Controller

封装所有与设备交互的底层操作（ADB/Fastboot）
"""

import subprocess
import time
from pathlib import Path
from typing import Optional, List
from dataclasses import dataclass
from loguru import logger


@dataclass
class DeviceInfo:
    """设备信息"""
    serial: str
    model: str
    brand: str
    product: str
    android_version: str
    build_id: str
    build_fingerprint: str
    security_patch: str


class DeviceController:
    """设备控制器 - ADB/Fastboot 命令封装"""
    
    # 类级别的默认路径（可以被实例覆盖）
    _default_adb_path = "adb"
    _default_fastboot_path = "fastboot"
    
    @staticmethod
    def is_local_device(device_id: str) -> bool:
        """
        判断是否为本地 USB 设备
        
        本地设备特征:
        - 不包含 IP 地址和端口 (如 192.168.x.x:5555)
        - 通常是序列号格式 (如 1234567890ABCDEF)
        
        云端设备特征:
        - 包含 IP 地址和端口 (如 183.2.216.164:15502)
        
        Args:
            device_id: 设备 ID
        
        Returns:
            bool: 是否为本地设备
        """
        import re
        
        # 检查是否包含 IP 地址格式
        ip_pattern = r'\d{1,3}\.\d{1,3}\.\d{1,3}\.\d{1,3}:\d+'
        if re.match(ip_pattern, device_id):
            return False
        
        # 检查是否包含冒号（网络设备通常有端口号）
        if ':' in device_id:
            return False
        
        return True
    
    @classmethod
    def list_devices(cls, local_only: bool = True, adb_path: str = None) -> List[str]:
        """
        列出所有连接的设备（包括 ADB 和 Fastboot）
        
        Args:
            local_only: 是否只列出本地 USB 设备
            adb_path: ADB 可执行文件路径（可选，默认使用类默认值）
        
        Returns:
            List[str]: 设备序列号列表
        """
        if adb_path is None:
            adb_path = cls._default_adb_path
        
        devices = []
        
        # 1. 检查 ADB 设备
        try:
            result = subprocess.run(
                [adb_path, "devices"],
                capture_output=True,
                text=True,
                timeout=10
            )
            
            if result.returncode == 0:
                for line in result.stdout.strip().split('\n')[1:]:  # 跳过标题行
                    if '\tdevice' in line or ' device' in line:
                        device_id = line.split()[0]
                        
                        # 如果只要本地设备，过滤掉云端设备
                        if local_only and not cls.is_local_device(device_id):
                            logger.debug(f"忽略云端设备: {device_id}")
                            continue
                        
                        devices.append(device_id)
        except Exception as e:
            logger.error(f"列出 ADB 设备失败: {e}")
        
        # 2. 检查 Fastboot 设备
        try:
            result = subprocess.run(
                ["fastboot", "devices"],
                capture_output=True,
                text=True,
                timeout=10
            )
            
            if result.returncode == 0:
                for line in result.stdout.strip().split('\n'):
                    if line.strip() and '\t' in line:
                        device_id = line.split('\t')[0]
                        
                        # 如果只要本地设备，过滤掉云端设备
                        if local_only and not cls.is_local_device(device_id):
                            logger.debug(f"忽略云端设备: {device_id}")
                            continue
                        
                        # 避免重复添加
                        if device_id not in devices:
                            devices.append(device_id)
        except Exception as e:
            logger.error(f"列出 Fastboot 设备失败: {e}")
        
        logger.info(f"找到 {len(devices)} 个{'本地' if local_only else ''}设备")
        return devices
            return []
    
    def __init__(
        self,
        serial: Optional[str] = None,
        adb_path: str = None,
        fastboot_path: str = None
    ):
        """
        初始化设备控制器
        
        Args:
            serial: 设备序列号（可选，如果只有一台设备可以不指定）
            adb_path: ADB 可执行文件路径（可选，默认使用环境变量）
            fastboot_path: Fastboot 可执行文件路径（可选，默认使用环境变量）
        """
        self.serial = serial
        self.adb_path = adb_path or self._default_adb_path
        self.fastboot_path = fastboot_path or self._default_fastboot_path
        
        self.adb_prefix = [self.adb_path]
        self.fastboot_prefix = [self.fastboot_path]
        
        if serial:
            self.adb_prefix.extend(["-s", serial])
            self.fastboot_prefix.extend(["-s", serial])
        
        logger.info(f"设备控制器初始化: serial={serial or 'auto'}, adb={self.adb_path}, fastboot={self.fastboot_path}")
    
    # ==================== ADB 命令封装 ====================
    
    def adb_shell(self, command: str, timeout: int = 30) -> str:
        """
        执行 ADB shell 命令
        
        Args:
            command: shell 命令
            timeout: 超时时间（秒）
        
        Returns:
            命令输出
        """
        cmd = self.adb_prefix + ["shell", command]
        return self._run_command(cmd, timeout=timeout, capture_output=True)
    
    def adb_install(self, apk_path: Path, timeout: int = 60) -> bool:
        """
        安装 APK
        
        Args:
            apk_path: APK 文件路径
            timeout: 超时时间（秒）
        
        Returns:
            是否安装成功
        """
        cmd = self.adb_prefix + ["install", "-r", str(apk_path)]
        try:
            # 需要捕获输出来检查是否成功，但也要显示给用户
            result = subprocess.run(
                cmd,
                capture_output=True,
                text=True,
                timeout=timeout
            )
            
            # 合并 stdout 和 stderr
            output = result.stdout + result.stderr
            
            # 检查是否成功
            success = result.returncode == 0 and "Success" in output
            
            if success:
                logger.info(f"✓ APK 安装成功: {apk_path.name}")
            else:
                logger.error(f"✗ APK 安装失败: {apk_path.name}")
                logger.error(f"  返回码: {result.returncode}")
                if result.stdout:
                    logger.error(f"  输出: {result.stdout.strip()}")
                if result.stderr:
                    logger.error(f"  错误: {result.stderr.strip()}")
            
            return success
        except subprocess.TimeoutExpired:
            logger.error(f"✗ APK 安装超时: {apk_path.name}")
            return False
        except Exception as e:
            logger.error(f"✗ APK 安装异常: {apk_path.name}, {e}")
            return False
    
    def adb_push(self, local_path: Path, remote_path: str, timeout: int = 60) -> bool:
        """
        推送文件到设备
        
        Args:
            local_path: 本地文件路径
            remote_path: 设备上的路径
            timeout: 超时时间（秒）
        
        Returns:
            是否推送成功
        """
        cmd = self.adb_prefix + ["push", str(local_path), remote_path]
        try:
            # 实时显示推送进度
            self._run_command(cmd, timeout=timeout, check=True)
            logger.info(f"✓ 文件推送成功: {local_path.name} -> {remote_path}")
            return True
        except Exception as e:
            logger.error(f"✗ 文件推送失败: {e}")
            return False
    
    def adb_pull(self, remote_path: str, local_path: Path, timeout: int = 60) -> bool:
        """
        从设备拉取文件
        
        Args:
            remote_path: 设备上的路径
            local_path: 本地文件路径
            timeout: 超时时间（秒）
        
        Returns:
            是否拉取成功
        """
        cmd = self.adb_prefix + ["pull", remote_path, str(local_path)]
        try:
            # 实时显示拉取进度
            self._run_command(cmd, timeout=timeout, check=True)
            logger.info(f"✓ 文件拉取成功: {remote_path} -> {local_path.name}")
            return True
        except Exception as e:
            logger.error(f"✗ 文件拉取失败: {e}")
            return False
    
    def adb_reboot(self, mode: str = "system") -> bool:
        """
        重启设备
        
        Args:
            mode: 重启模式 - "system", "bootloader", "recovery"
        
        Returns:
            是否执行成功
        """
        if mode == "system":
            cmd = self.adb_prefix + ["reboot"]
        else:
            cmd = self.adb_prefix + ["reboot", mode]
        
        try:
            # 实时显示重启信息
            self._run_command(cmd, timeout=10, check=True)
            logger.info(f"✓ 设备重启: mode={mode}")
            return True
        except Exception as e:
            logger.error(f"✗ 设备重启失败: {e}")
            return False
    
    # ==================== Fastboot 命令封装 ====================
    
    def fastboot_shell(self, command: str, timeout: int = 30) -> str:
        """
        执行 Fastboot 命令
        
        Args:
            command: fastboot 命令
            timeout: 超时时间（秒）
        
        Returns:
            命令输出
        """
        cmd = self.fastboot_prefix + command.split()
        return self._run_command(cmd, timeout=timeout, capture_output=True)
    
    def fastboot_flash(self, partition: str, image_path: Path, timeout: int = 120) -> bool:
        """
        刷入分区
        
        Args:
            partition: 分区名称，如 "boot"
            image_path: 镜像文件路径
            timeout: 超时时间（秒）
        
        Returns:
            是否刷入成功
        """
        cmd = self.fastboot_prefix + ["flash", partition, str(image_path)]
        try:
            # 实时显示刷入进度
            self._run_command(cmd, timeout=timeout, check=True)
            logger.info(f"✓ 分区刷入成功: {partition}")
            return True
        except subprocess.CalledProcessError as e:
            logger.error(f"✗ 分区刷入失败: {partition}")
            logger.error(f"  返回码: {e.returncode}")
            if e.stdout:
                logger.error(f"  stdout: {e.stdout}")
            if e.stderr:
                logger.error(f"  stderr: {e.stderr}")
            return False
        except Exception as e:
            logger.error(f"✗ 分区刷入异常: {partition}, {e}")
            return False
    
    def fastboot_reboot(self, timeout: int = 10) -> bool:
        """
        Fastboot 重启到系统
        
        Returns:
            是否执行成功
        """
        cmd = self.fastboot_prefix + ["reboot"]
        try:
            # 实时显示重启信息
            self._run_command(cmd, timeout=timeout, check=True)
            logger.info("✓ Fastboot 重启")
            return True
        except Exception as e:
            logger.error(f"✗ Fastboot 重启失败: {e}")
            return False
    
    def fastboot_getvar(self, var_name: str) -> str:
        """
        获取 Fastboot 变量
        
        Args:
            var_name: 变量名，如 "current-slot"
        
        Returns:
            变量值
        """
        cmd = self.fastboot_prefix + ["getvar", var_name]
        try:
            # fastboot getvar 输出在 stderr
            result = subprocess.run(
                cmd,
                capture_output=True,
                text=True,
                timeout=10
            )
            # 解析输出
            for line in result.stderr.splitlines():
                if var_name in line:
                    return line.split(":")[-1].strip()
            return ""
        except Exception as e:
            logger.warning(f"获取 Fastboot 变量失败: {var_name}, {e}")
            return ""
    
    # ==================== 设备状态检测 ====================
    
    def wait_for_adb(self, timeout: int = 60) -> bool:
        """
        等待 ADB 连接
        
        Args:
            timeout: 超时时间（秒）
        
        Returns:
            是否连接成功
        """
        logger.info(f"等待 ADB 连接（超时 {timeout} 秒）...")
        deadline = time.time() + timeout
        
        while time.time() < deadline:
            try:
                # 需要捕获输出来解析设备列表
                result = subprocess.run(
                    [self.adb_path, "devices"],
                    capture_output=True,
                    text=True,
                    timeout=5
                )
                
                # 检查是否有设备连接
                for line in result.stdout.splitlines()[1:]:
                    if "\tdevice" in line and "offline" not in line:
                        # 如果指定了序列号，检查是否匹配
                        if self.serial:
                            if self.serial in line:
                                logger.info(f"✓ ADB 已连接: {self.serial}")
                                return True
                        else:
                            logger.info("✓ ADB 已连接")
                            return True
            except Exception:
                pass
            
            time.sleep(1)
        
        logger.error("✗ ADB 连接超时")
        return False
    
    def wait_for_fastboot(self, timeout: int = 30) -> bool:
        """
        等待 Fastboot 连接
        
        Args:
            timeout: 超时时间（秒）
        
        Returns:
            是否连接成功
        """
        logger.info(f"等待 Fastboot 连接（超时 {timeout} 秒）...")
        deadline = time.time() + timeout
        
        while time.time() < deadline:
            try:
                # 需要捕获输出来解析设备列表
                result = subprocess.run(
                    [self.fastboot_path, "devices"],
                    capture_output=True,
                    text=True,
                    timeout=5
                )
                
                # 检查是否有设备连接
                for line in result.stdout.splitlines():
                    if "fastboot" in line:
                        if self.serial:
                            if self.serial in line:
                                logger.info(f"✓ Fastboot 已连接: {self.serial}")
                                return True
                        else:
                            logger.info("✓ Fastboot 已连接")
                            return True
            except Exception:
                pass
            
            time.sleep(1)
        
        logger.error("✗ Fastboot 连接超时")
        return False
    
    def get_device_info(self) -> DeviceInfo:
        """
        获取设备信息
        
        Returns:
            设备信息
        """
        # 1. 先从 adb devices 获取序列号
        serial = self._get_serial_from_devices()
        
        # 2. 获取其他设备属性
        return DeviceInfo(
            serial=serial,
            model=self.adb_shell("getprop ro.product.device").strip(),
            brand=self.adb_shell("getprop ro.product.brand").strip(),
            product=self.adb_shell("getprop ro.product.name").strip(),
            android_version=self.adb_shell("getprop ro.build.version.release").strip(),
            build_id=self.adb_shell("getprop ro.build.id").strip(),
            build_fingerprint=self.adb_shell("getprop ro.build.fingerprint").strip(),
            security_patch=self.adb_shell("getprop ro.build.version.security_patch").strip(),
        )
    
    def _get_serial_from_devices(self) -> str:
        """
        从 adb devices 获取设备序列号
        
        Returns:
            设备序列号
        """
        try:
            # 需要捕获输出来解析序列号
            result = subprocess.run(
                [self.adb_path, "devices"],
                capture_output=True,
                text=True,
                timeout=5
            )
            
            # 解析输出，找到第一个连接的设备
            for line in result.stdout.splitlines()[1:]:
                if "\tdevice" in line and "offline" not in line:
                    serial = line.split("\t")[0].strip()
                    # 如果指定了序列号，检查是否匹配
                    if self.serial and self.serial != serial:
                        continue
                    logger.debug(f"从 adb devices 获取序列号: {serial}")
                    return serial
            
            # 如果没有找到，尝试从 getprop 获取（可能失败）
            logger.warning("无法从 adb devices 获取序列号，尝试 getprop")
            return self.adb_shell("getprop ro.serialno").strip()
            
        except Exception as e:
            logger.warning(f"获取序列号失败: {e}")
            return "unknown"
    
    def verify_device_model(self, expected_model: str) -> bool:
        """
        验证设备型号
        
        Args:
            expected_model: 期望的设备型号
        
        Returns:
            是否匹配
        """
        device_info = self.get_device_info()
        if device_info.model != expected_model:
            logger.error(f"✗ 设备型号不匹配: 期望 {expected_model}, 实际 {device_info.model}")
            return False
        
        logger.info(f"✓ 设备型号验证通过: {device_info.model}")
        return True
    
    def check_battery_level(self) -> int:
        """
        检测电池电量
        
        Returns:
            电池电量（百分比）
        """
        try:
            # adb_shell 已经设置了 capture_output=True
            output = self.adb_shell("dumpsys battery | grep level")
            level = int(output.split(":")[-1].strip())
            logger.info(f"电池电量: {level}%")
            return level
        except Exception as e:
            logger.warning(f"无法获取电池电量: {e}")
            return 100  # 默认返回 100
    
    def check_bootloader_status(self) -> bool:
        """
        检测 Bootloader 锁定状态
        
        Returns:
            True=已解锁, False=已锁定
        """
        try:
            # adb_shell 已经设置了 capture_output=True
            output = self.adb_shell("getprop ro.boot.flash.locked")
            is_locked = output.strip() == "1"
            
            if is_locked:
                logger.warning("⚠ Bootloader 已锁定")
            else:
                logger.info("✓ Bootloader 已解锁")
            
            return not is_locked
        except Exception as e:
            logger.warning(f"无法检测 Bootloader 状态: {e}")
            return True  # 默认假设已解锁
    
    # ==================== 工具方法 ====================
    
    def _run_command(
        self,
        cmd: List[str],
        timeout: int = 30,
        check: bool = True,
        capture_output: bool = False
    ) -> str:
        """
        执行命令（默认实时显示输出）
        
        Args:
            cmd: 命令列表
            timeout: 超时时间（秒）
            check: 是否检查返回码
            capture_output: 是否捕获输出（默认 False = 实时显示）
        
        Returns:
            命令输出（capture_output=True 时返回输出，否则返回空字符串）
        
        Raises:
            subprocess.CalledProcessError: 命令执行失败
            subprocess.TimeoutExpired: 命令超时
        """
        logger.debug(f"执行命令: {' '.join(cmd)}")
        
        if capture_output:
            # 捕获输出（用于需要解析返回值的命令）
            result = subprocess.run(
                cmd,
                capture_output=True,
                text=True,
                timeout=timeout,
                check=check
            )
            return result.stdout.strip()
        else:
            # 实时显示输出（默认行为）
            result = subprocess.run(
                cmd,
                timeout=timeout,
                check=check
            )
            return ""


# 测试代码
if __name__ == "__main__":
    logger.add("logs/device_controller_test.log", rotation="10 MB")
    
    # 测试设备控制器
    dc = DeviceController()
    
    # 等待 ADB 连接
    if dc.wait_for_adb(timeout=10):
        # 获取设备信息
        info = dc.get_device_info()
        print(f"\n设备信息:")
        print(f"  型号: {info.model}")
        print(f"  品牌: {info.brand}")
        print(f"  Android 版本: {info.android_version}")
        print(f"  Build ID: {info.build_id}")
        
        # 检查电池
        battery = dc.check_battery_level()
        print(f"  电池电量: {battery}%")
        
        # 检查 Bootloader
        unlocked = dc.check_bootloader_status()
        print(f"  Bootloader: {'已解锁' if unlocked else '已锁定'}")
    else:
        print("未检测到设备")
