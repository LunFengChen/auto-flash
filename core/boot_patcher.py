"""
APatch Boot Image Patcher

This module handles automatic boot.img patching using APatch tools.
"""

import os
import shutil
import subprocess
import logging
from pathlib import Path
from typing import Optional
from dataclasses import dataclass


@dataclass
class BootPatchConfig:
    """Boot patch configuration"""
    device_model: str
    build_id: str
    firmware_dir: Path
    root_dir: Path
    superkey: str
    patch_tools_dir: Path = Path("resources/common/tools")  # Windows 工具目录 (magiskboot.exe, kptools.exe)
    binary_dir: Path = Path("resources/common/binary")  # kpimg 目录
    kpimg_version: Optional[str] = None  # 指定 kpimg 版本，None = 自动检测
    kpm_modules: list[Path] = None  # KPM 模块列表（.kpm 文件）
    extra_args: list[str] = None  # 传递给 kptools 的额外参数
    
    def __post_init__(self):
        """初始化后处理"""
        if self.kpm_modules is None:
            self.kpm_modules = []
        if self.extra_args is None:
            self.extra_args = []


class BootPatcher:
    """APatch boot image patcher"""
    
    def __init__(self, config: BootPatchConfig):
        self.config = config
        self.logger = logging.getLogger(__name__)
        
        # Tool paths - 支持 Windows 和 Linux
        # Windows: magiskboot.exe, kptools-msys2.exe (在 patch_tools_dir)
        # Linux: magiskboot, kptools (在 binary_dir)
        import platform
        is_windows = platform.system() == "Windows"
        
        if is_windows:
            self.magiskboot = config.patch_tools_dir / "magiskboot.exe"
            # 查找 kptools，支持版本化文件名
            kptools_candidates = [
                config.patch_tools_dir / "kptools-msys2-0.12.7.exe",
                config.patch_tools_dir / "kptools-msys2.exe",
                config.patch_tools_dir / "kptools.exe",
            ]
            self.kptools = None
            for candidate in kptools_candidates:
                if candidate.exists():
                    self.kptools = candidate
                    break
            if not self.kptools:
                self.kptools = kptools_candidates[1]  # 默认使用 kptools-msys2.exe
        else:
            self.magiskboot = config.binary_dir / "magiskboot"
            self.kptools = config.binary_dir / "kptools"
        
        # kpimg 路径：支持指定版本
        if config.kpimg_version:
            # 尝试多种文件名格式
            kpimg_candidates = [
                config.patch_tools_dir / f"kpimg-android-{config.kpimg_version}",
                config.patch_tools_dir / f"kpimg-{config.kpimg_version}",
                config.binary_dir / f"kpimg-{config.kpimg_version}",
                config.binary_dir / "kpimg",
            ]
            self.kpimg = None
            for candidate in kpimg_candidates:
                if candidate.exists():
                    self.kpimg = candidate
                    break
            if not self.kpimg:
                self.logger.warning(f"指定的 kpimg 版本不存在: {config.kpimg_version}")
                self.logger.info("回退到默认 kpimg")
                self.kpimg = config.binary_dir / "kpimg"
        else:
            # 自动查找最新版本的 kpimg
            kpimg_candidates = list(config.patch_tools_dir.glob("kpimg-android-*"))
            if kpimg_candidates:
                # 使用最新的（按文件名排序）
                self.kpimg = sorted(kpimg_candidates)[-1]
            else:
                self.kpimg = config.binary_dir / "kpimg"
        
        # 实际使用的 kpimg 版本（用于命名）
        self.kpimg_version = config.kpimg_version if config.kpimg_version else self._detect_kpimg_version()
        
        # 已有设备专用 patched boot 时，直接复用，不要求本机具备重新修补工具。
        # 这样 Linux 环境可以使用仓库随设备保存的成品镜像，只有确实需要新修补时
        # 才校验 magiskboot/kptools/kpimg。
        if not self._find_existing_patched_boot():
            self._validate_tools()
    
    def _validate_tools(self):
        """Validate required tools exist"""
        tools = {
            "magiskboot": self.magiskboot,
            "kptools": self.kptools,
            "kpimg": self.kpimg
        }
        
        missing = []
        for name, path in tools.items():
            if not path.exists():
                missing.append(f"{name} ({path})")
        
        if missing:
            raise FileNotFoundError(
                f"Missing required tools:\n" + "\n".join(f"  - {t}" for t in missing) +
                f"\n\nPlease extract tools from APatch APK:\n"
                f"  unzip APatch.apk -d temp/\n"
                f"  cp temp/lib/arm64-v8a/libmagiskboot.so {self.config.binary_dir}/magiskboot\n"
                f"  cp temp/lib/arm64-v8a/libkptools.so {self.config.binary_dir}/kptools\n"
                f"  cp temp/assets/kpimg {self.config.binary_dir}/kpimg\n"
                f"  chmod +x {self.config.binary_dir}/*"
            )
    
    def _detect_kpimg_version(self) -> str:
        """
        检测 kpimg 版本号
        
        Returns:
            版本号字符串，如 "0.12.7"，检测失败返回 "unknown"
        """
        # 方法1: 从文件名检测（kpimg-android-0.12.7 或 kpimg-0.12.7）
        filename = self.kpimg.name
        if "android" in filename:
            # kpimg-android-0.12.7 -> 0.12.7
            parts = filename.split("-")
            if len(parts) >= 3:
                return parts[-1]
        elif "-" in filename:
            # kpimg-0.12.7 -> 0.12.7
            version = filename.split("-", 1)[1]
            if version:
                return version
        
        # 方法2: 使用 kptools 检测版本
        try:
            result = subprocess.run(
                [str(self.kptools), "-k", str(self.kpimg), "--version"],
                capture_output=True,
                text=True,
                timeout=5
            )
            if result.returncode == 0:
                version_str = result.stdout.strip()
                # 版本格式: c02 -> 0.12.2, c07 -> 0.12.7
                if version_str.startswith('c'):
                    minor = int(version_str[1:])
                    return f"0.12.{minor}"
                return version_str
        except Exception as e:
            self.logger.debug(f"Failed to detect kpimg version: {e}")
        
        return "unknown"
    
    def get_or_create_patched_boot(self) -> Path:
        """
        Get existing patched boot.img or create new one
        
        Returns:
            Path to patched boot.img
        """
        # 1. Check for existing patched boot.img
        patched_boot = self._find_existing_patched_boot()
        if patched_boot:
            self.logger.info(f"Found existing patched boot.img: {patched_boot}")
            return patched_boot
        
        # 2. No existing patch, create new one
        self.logger.info("No patched boot.img found, starting auto-patch...")
        
        # 3. Extract original boot.img
        original_boot = self._extract_boot_img()
        
        # 4. Patch boot.img
        patched_boot = self._patch_boot_img(original_boot)
        
        self.logger.info(f"Boot.img patched successfully: {patched_boot}")
        return patched_boot
    
    def _find_existing_patched_boot(self) -> Optional[Path]:
        """Find existing patched boot.img"""
        root_dir = self.config.root_dir
        
        if not root_dir.exists():
            return None
        
        # APatch-only: never reuse Magisk-patched images or generic patched files.
        # A stale Magisk boot image here can make an APatch run look successful
        # while the device is not actually APatch-rooted.
        patterns = [
            "apatch_patched*.img",
        ]
        
        for pattern in patterns:
            matches = list(root_dir.glob(pattern))
            if matches:
                # Return newest file
                return max(matches, key=lambda p: p.stat().st_mtime)
        
        return None
    
    def _extract_boot_img(self) -> Path:
        """Extract boot.img from firmware"""
        firmware_dir = self.config.firmware_dir
        
        # 1. Check if boot.img already extracted
        boot_img = firmware_dir / "boot.img"
        if boot_img.exists():
            self.logger.info(f"Using existing boot.img: {boot_img}")
            return boot_img
        
        # 2. Extract from image-*.zip
        image_zips = list(firmware_dir.glob("image-*.zip"))
        if not image_zips:
            raise FileNotFoundError(f"No firmware package found in {firmware_dir}")
        
        image_zip = image_zips[0]
        self.logger.info(f"Extracting boot.img from: {image_zip.name}")
        
        # Use unzip command
        subprocess.run(
            ["unzip", "-j", str(image_zip), "boot.img", "-d", str(firmware_dir)],
            check=True,
            capture_output=True
        )
        
        if not boot_img.exists():
            raise FileNotFoundError(f"Failed to extract boot.img from {image_zip}")
        
        return boot_img
    
    def _patch_boot_img(self, original_boot: Path) -> Path:
        """
        Patch boot.img using APatch tools
        
        Args:
            original_boot: Path to original boot.img
            
        Returns:
            Path to patched boot.img
        """
        self.logger.info("****************************")
        self.logger.info(" APatch Boot Image Patcher")
        self.logger.info("****************************")
        
        # Create work directory (Windows-compatible)
        import tempfile
        work_dir = Path(tempfile.mkdtemp(prefix="apatch_work_"))
        
        try:
            # Copy files to work directory
            shutil.copy(original_boot, work_dir / "boot.img")
            shutil.copy(self.magiskboot, work_dir / self.magiskboot.name)
            shutil.copy(self.kptools, work_dir / self.kptools.name)
            shutil.copy(self.kpimg, work_dir / "kpimg")
            
            # Copy MSYS2 DLL files if on Windows
            import platform
            if platform.system() == "Windows":
                dll_files = list(self.config.patch_tools_dir.glob("msys-*.dll"))
                for dll in dll_files:
                    shutil.copy(dll, work_dir / dll.name)
            
            # Make tools executable (Unix-like systems only)
            if platform.system() != "Windows":
                os.chmod(work_dir / self.magiskboot.name, 0o755)
                os.chmod(work_dir / self.kptools.name, 0o755)
            
            # Tool names for commands
            magiskboot_cmd = str(work_dir / self.magiskboot.name)
            kptools_cmd = str(work_dir / self.kptools.name)
            
            # Step 1: Unpack boot.img
            self.logger.info("- Unpacking boot image")
            result = subprocess.run(
                [magiskboot_cmd, "unpack", "boot.img"],
                cwd=work_dir,
                capture_output=True,
                text=True
            )
            if result.returncode != 0:
                raise RuntimeError(f"- Unpack error: {result.returncode}")
            
            # Step 2: Check kernel config
            result = subprocess.run(
                [kptools_cmd, "-i", "kernel", "-f"],
                cwd=work_dir,
                capture_output=True,
                text=True
            )
            
            if "CONFIG_KALLSYMS=y" not in result.stdout:
                self.logger.error("- Patcher has Aborted!")
                self.logger.error("- APatch requires CONFIG_KALLSYMS to be Enabled.")
                self.logger.error("- But your kernel seems NOT enabled it.")
                raise RuntimeError(
                    "Kernel does not have CONFIG_KALLSYMS enabled!\n"
                    "APatch requires CONFIG_KALLSYMS=y in kernel config."
                )
            
            # Check if already patched
            result = subprocess.run(
                [kptools_cmd, "-i", "kernel", "-l"],
                cwd=work_dir,
                capture_output=True,
                text=True
            )
            
            if "patched=true" in result.stdout:
                self.logger.warning("- Kernel is already patched, skipping...")
                # Use original boot.img with proper naming
                output_path = self.config.root_dir / f"apatch_patched_{self.config.build_id}_{self.kpimg_version}.img"
                shutil.copy(original_boot, output_path)
                return output_path
            
            # Backup original kernel
            if "patched=false" in result.stdout:
                self.logger.info("- Backing boot.img")
                shutil.copy(work_dir / "boot.img", work_dir / "ori.img")
            
            shutil.copy(work_dir / "kernel", work_dir / "kernel.ori")
            
            # Copy KPM modules to work directory
            for kpm_module in self.config.kpm_modules:
                if kpm_module.exists():
                    shutil.copy(kpm_module, work_dir / kpm_module.name)
                    self.logger.info(f"- Embedding KPM module: {kpm_module.name}")
            
            # Step 3: Patch kernel
            self.logger.info("- Patching kernel")
            
            # Build kptools command
            kptools_args = [
                kptools_cmd, "-p",
                "-i", "kernel.ori",
                "-S", self.config.superkey,
                "-k", "kpimg",
                "-o", "kernel"
            ]
            
            # Add KPM modules
            for kpm_module in self.config.kpm_modules:
                if kpm_module.exists():
                    kptools_args.extend(["-K", kpm_module.name])
            
            # Add extra arguments
            kptools_args.extend(self.config.extra_args)
            
            result = subprocess.run(
                kptools_args,
                cwd=work_dir,
                capture_output=True,
                text=True
            )
            
            if result.returncode != 0:
                raise RuntimeError(f"- Patch kernel error: {result.returncode}")
            
            # Step 4: Repack boot.img
            self.logger.info("- Repacking boot image")
            result = subprocess.run(
                [magiskboot_cmd, "repack", "boot.img"],
                cwd=work_dir,
                capture_output=True,
                text=True
            )
            
            if result.returncode != 0:
                raise RuntimeError(f"- Repack error: {result.returncode}")
            
            # Check for CONFIG_KALLSYMS_ALL warning
            result = subprocess.run(
                [kptools_cmd, "-i", "kernel.ori", "-f"],
                cwd=work_dir,
                capture_output=True,
                text=True
            )
            
            if "CONFIG_KALLSYMS_ALL=y" not in result.stdout:
                self.logger.warning("- Detected CONFIG_KALLSYMS_ALL is not set!")
                self.logger.warning("- APatch has patched but maybe your device won't boot.")
                self.logger.warning("- Make sure you have original boot image backup.")
            
            # Move patched boot.img to destination with version in filename
            self.config.root_dir.mkdir(parents=True, exist_ok=True)
            output_path = self.config.root_dir / f"apatch_patched_{self.config.build_id}_{self.kpimg_version}.img"
            
            shutil.move(work_dir / "new-boot.img", output_path)
            
            self.logger.info("- Successfully Patched!")
            return output_path
            
        finally:
            # Cleanup work directory
            if work_dir.exists():
                shutil.rmtree(work_dir)
    
    def verify_patched_boot(self, boot_img: Path) -> bool:
        """
        Verify if boot.img is properly patched
        
        Args:
            boot_img: Path to boot.img to verify
            
        Returns:
            True if patched, False otherwise
        """
        import tempfile
        work_dir = Path(tempfile.mkdtemp(prefix="apatch_verify_"))
        
        try:
            # Copy files
            shutil.copy(boot_img, work_dir / "boot.img")
            shutil.copy(self.magiskboot, work_dir / self.magiskboot.name)
            shutil.copy(self.kptools, work_dir / self.kptools.name)
            
            # Copy MSYS2 DLL files if on Windows
            import platform
            if platform.system() == "Windows":
                dll_files = list(self.config.patch_tools_dir.glob("msys-*.dll"))
                for dll in dll_files:
                    shutil.copy(dll, work_dir / dll.name)
            
            # Make tools executable (Unix-like systems only)
            if platform.system() != "Windows":
                os.chmod(work_dir / self.magiskboot.name, 0o755)
                os.chmod(work_dir / self.kptools.name, 0o755)
            
            # Tool names for commands
            magiskboot_cmd = str(work_dir / self.magiskboot.name)
            kptools_cmd = str(work_dir / self.kptools.name)
            
            # Unpack
            subprocess.run(
                [magiskboot_cmd, "unpack", "boot.img"],
                cwd=work_dir,
                capture_output=True,
                check=True
            )
            
            # Check if patched
            result = subprocess.run(
                [kptools_cmd, "-i", "kernel", "-l"],
                cwd=work_dir,
                capture_output=True,
                text=True
            )
            
            return "patched=true" in result.stdout
            
        except Exception as e:
            self.logger.error(f"Failed to verify boot.img: {e}")
            return False
        finally:
            if work_dir.exists():
                shutil.rmtree(work_dir)
