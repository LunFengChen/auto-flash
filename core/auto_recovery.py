"""
自动恢复管理器 - 管理 boot.img 备份和自动恢复,防止刷机失败导致变砖

设计原则:
1. 自动备份原厂 boot.img
2. 检测设备启动失败
3. 自动刷回原厂 boot.img
4. 管理多版本备份
"""

import logging
import json
import hashlib
from dataclasses import dataclass, asdict
from datetime import datetime
from pathlib import Path
from typing import Optional, List

logger = logging.getLogger(__name__)


@dataclass
class BootBackup:
    """Boot 备份信息"""
    backup_id: str  # 备份 ID,如 "backup_20250119_153045"
    device_serial: str
    device_model: str
    build_id: str
    backup_time: str  # ISO 格式时间字符串
    boot_img_path: str  # 备份文件路径
    sha256: str
    is_stock: bool  # 是否为原厂 boot.img
    description: str  # 备份描述


class AutoRecoveryManager:
    """自动恢复管理器"""
    
    def __init__(
        self,
        device_controller,
        backup_dir: Path = Path("backups"),
        max_backups: int = 3
    ):
        """
        初始化自动恢复管理器
        
        Args:
            device_controller: 设备控制器
            backup_dir: 备份目录
            max_backups: 保留的最大备份数
        """
        self.device = device_controller
        self.backup_dir = backup_dir
        self.max_backups = max_backups
        
        # 确保备份目录存在
        self.backup_dir.mkdir(parents=True, exist_ok=True)
    
    def backup_current_boot(
        self,
        device_info: dict,
        description: str = "原厂 boot.img"
    ) -> BootBackup:
        """
        备份当前设备的 boot.img
        
        Args:
            device_info: 设备信息字典
            description: 备份描述
        
        Returns:
            BootBackup: 备份信息
        
        Raises:
            RuntimeError: 备份失败
        """
        logger.info("正在备份当前 boot.img...")
        
        try:
            # 1. 生成备份 ID
            backup_id = f"backup_{datetime.now().strftime('%Y%m%d_%H%M%S')}"
            
            # 2. 构造备份文件路径
            boot_img_path = self.backup_dir / f"{backup_id}_{device_info['model']}_{device_info['build_id']}.img"
            
            # 3. 从设备提取 boot.img
            logger.info("重启到 bootloader 模式...")
            self.device.adb_shell("reboot bootloader")
            
            # 等待进入 fastboot 模式
            if not self.device.wait_for_fastboot(timeout=30):
                raise RuntimeError("设备未进入 fastboot 模式")
            
            # 4. 获取当前活动槽位
            try:
                current_slot = self.device.fastboot_shell("getvar current-slot")
                current_slot = current_slot.strip()
                logger.info(f"当前活动槽位: {current_slot}")
            except Exception:
                current_slot = ""
                logger.warning("无法获取当前槽位,使用默认 boot 分区")
            
            # 5. 确定 boot 分区名称
            if current_slot:
                boot_partition = f"boot_{current_slot}"
            else:
                boot_partition = "boot"
            
            logger.info(f"正在提取 {boot_partition} 分区...")
            
            # 6. 使用 fastboot 提取 boot 分区
            # 注意: fastboot 不直接支持读取分区,需要使用其他方法
            # 方法 1: 使用 adb pull (需要 root)
            # 方法 2: 使用 dd 命令 (需要 root)
            # 方法 3: 从刷机包中提取 (推荐)
            
            # 这里使用简化方法: 假设用户提供了原厂 boot.img
            logger.warning("⚠️  自动提取 boot.img 需要 root 权限或从刷机包提取")
            logger.warning("⚠️  请确保已从刷机包中提取原厂 boot.img")
            
            # 重启回系统
            self.device.fastboot_shell("reboot")
            self.device.wait_for_adb(timeout=120)
            
            # 如果无法自动提取,返回空备份
            raise NotImplementedError("自动提取 boot.img 功能需要进一步实现")
            
        except NotImplementedError:
            # 提供手动备份指导
            logger.info("=" * 60)
            logger.info("手动备份 boot.img 指南:")
            logger.info("1. 从刷机包中提取 boot.img")
            logger.info("2. 将 boot.img 复制到 backups/ 目录")
            logger.info("3. 重命名为: stock_boot_{device_model}_{build_id}.img")
            logger.info("=" * 60)
            raise
        except Exception as e:
            logger.error(f"备份 boot.img 失败: {e}")
            raise
    
    def backup_from_file(
        self,
        boot_img: Path,
        device_info: dict,
        is_stock: bool = True,
        description: str = "原厂 boot.img"
    ) -> BootBackup:
        """
        从文件创建备份记录
        
        Args:
            boot_img: boot.img 文件路径
            device_info: 设备信息字典
            is_stock: 是否为原厂 boot.img
            description: 备份描述
        
        Returns:
            BootBackup: 备份信息
        """
        logger.info(f"创建备份记录: {boot_img}")
        
        if not boot_img.exists():
            raise FileNotFoundError(f"boot.img 不存在: {boot_img}")
        
        # 1. 生成备份 ID
        backup_id = f"backup_{datetime.now().strftime('%Y%m%d_%H%M%S')}"
        
        # 2. 复制到备份目录
        backup_path = self.backup_dir / f"{backup_id}_{device_info['model']}_{device_info['build_id']}.img"
        
        import shutil
        shutil.copy2(boot_img, backup_path)
        
        # 3. 计算 SHA256
        sha256 = self._calculate_sha256(backup_path)
        
        # 4. 创建备份记录
        backup = BootBackup(
            backup_id=backup_id,
            device_serial=device_info['serial'],
            device_model=device_info['model'],
            build_id=device_info['build_id'],
            backup_time=datetime.now().isoformat(),
            boot_img_path=str(backup_path),
            sha256=sha256,
            is_stock=is_stock,
            description=description
        )
        
        # 5. 保存备份元数据
        self.save_backup_metadata(backup)
        
        # 6. 清理旧备份
        self.cleanup_old_backups()
        
        logger.info(f"✅ 备份创建完成: {backup_path}")
        return backup
    
    def flash_boot_with_recovery(
        self,
        boot_img: Path,
        timeout: int = 120,
        auto_recover: bool = True
    ) -> bool:
        """
        刷入 boot.img 并监控启动,失败时自动恢复
        
        Args:
            boot_img: boot.img 路径
            timeout: 启动超时时间(秒)
            auto_recover: 是否自动恢复
        
        Returns:
            bool: 是否成功启动
        """
        logger.info(f"正在刷入 boot.img: {boot_img}")
        
        try:
            # 1. 确保设备在 fastboot 模式
            if not self.device.wait_for_fastboot(timeout=10):
                logger.info("设备不在 fastboot 模式,正在重启...")
                self.device.adb_shell("reboot bootloader")
                if not self.device.wait_for_fastboot(timeout=30):
                    raise RuntimeError("设备未进入 fastboot 模式")
            
            # 2. 刷入 boot.img
            logger.info("刷入 boot 分区...")
            self.device.fastboot_shell(f"flash boot {boot_img}")
            
            # 3. 重启设备
            logger.info("重启设备...")
            self.device.fastboot_shell("reboot")
            
            # 4. 等待设备启动
            logger.info(f"等待设备启动(超时 {timeout} 秒)...")
            boot_success = self.device.wait_for_adb(timeout=timeout)
            
            if boot_success:
                logger.info("✅ 设备启动成功")
                return True
            
            # 5. 启动失败,尝试自动恢复
            if not auto_recover:
                logger.error("❌ 设备启动失败,自动恢复已禁用")
                return False
            
            logger.warning("❌ 设备启动失败,尝试自动恢复...")
            return self.auto_recover()
            
        except Exception as e:
            logger.error(f"刷入 boot.img 失败: {e}")
            if auto_recover:
                logger.info("尝试自动恢复...")
                return self.auto_recover()
            return False
    
    def auto_recover(self) -> bool:
        """
        自动恢复到原厂 boot.img
        
        Returns:
            bool: 是否恢复成功
        """
        logger.info("=" * 60)
        logger.info("开始自动恢复流程...")
        logger.info("=" * 60)
        
        # 1. 查找最近的原厂 boot.img 备份
        stock_backup = self.find_latest_stock_backup()
        
        if not stock_backup:
            logger.error("❌ 未找到原厂 boot.img 备份,无法自动恢复")
            logger.error("请手动刷入原厂镜像")
            logger.info("=" * 60)
            return False
        
        logger.info(f"找到原厂 boot.img 备份:")
        logger.info(f"  备份 ID: {stock_backup.backup_id}")
        logger.info(f"  Build ID: {stock_backup.build_id}")
        logger.info(f"  备份时间: {stock_backup.backup_time}")
        logger.info(f"  文件路径: {stock_backup.boot_img_path}")
        
        # 2. 重启到 fastboot 模式
        # 注意: 设备可能已经卡在 bootloader,尝试检测
        if not self.device.wait_for_fastboot(timeout=10):
            logger.info("设备未在 fastboot 模式,尝试强制重启...")
            logger.warning("⚠️  如果设备无响应,请手动将设备重启到 fastboot 模式")
            input("按回车继续...")
        
        # 3. 刷回原厂 boot.img
        try:
            logger.info("正在刷回原厂 boot.img...")
            self.device.fastboot_shell(f"flash boot {stock_backup.boot_img_path}")
            
            # 4. 重启设备
            logger.info("重启设备...")
            self.device.fastboot_shell("reboot")
            
            # 5. 等待设备启动
            logger.info("等待设备启动...")
            boot_success = self.device.wait_for_adb(timeout=120)
            
            if boot_success:
                logger.info("=" * 60)
                logger.info("✅ 自动恢复成功,设备已恢复正常")
                logger.info("=" * 60)
                return True
            else:
                logger.error("=" * 60)
                logger.error("❌ 自动恢复失败,请手动刷入原厂镜像")
                logger.error("=" * 60)
                return False
                
        except Exception as e:
            logger.error(f"自动恢复失败: {e}")
            logger.error("请手动刷入原厂镜像")
            return False
    
    def find_latest_stock_backup(self) -> Optional[BootBackup]:
        """
        查找最近的原厂 boot.img 备份
        
        Returns:
            Optional[BootBackup]: 最近的原厂备份,未找到返回 None
        """
        backups = self.load_all_backups()
        stock_backups = [b for b in backups if b.is_stock]
        
        if not stock_backups:
            return None
        
        # 按时间排序,返回最新的
        stock_backups.sort(key=lambda b: b.backup_time, reverse=True)
        return stock_backups[0]
    
    def save_backup_metadata(self, backup: BootBackup):
        """
        保存备份元数据到 JSON 文件
        
        Args:
            backup: 备份信息
        """
        metadata_file = self.backup_dir / f"{backup.backup_id}.json"
        
        try:
            with open(metadata_file, "w", encoding="utf-8") as f:
                json.dump(asdict(backup), f, indent=2, ensure_ascii=False)
            logger.debug(f"备份元数据已保存: {metadata_file}")
        except Exception as e:
            logger.error(f"保存备份元数据失败: {e}")
    
    def load_all_backups(self) -> List[BootBackup]:
        """
        加载所有备份元数据
        
        Returns:
            List[BootBackup]: 备份列表
        """
        backups = []
        
        for metadata_file in self.backup_dir.glob("backup_*.json"):
            try:
                with open(metadata_file, "r", encoding="utf-8") as f:
                    data = json.load(f)
                    backups.append(BootBackup(**data))
            except Exception as e:
                logger.warning(f"加载备份元数据失败: {metadata_file}, {e}")
        
        return backups
    
    def cleanup_old_backups(self):
        """清理旧备份,只保留最近 N 次"""
        backups = self.load_all_backups()
        
        if len(backups) <= self.max_backups:
            return
        
        # 按时间排序
        backups.sort(key=lambda b: b.backup_time, reverse=True)
        
        # 删除旧备份
        for backup in backups[self.max_backups:]:
            try:
                # 删除备份文件
                boot_img_path = Path(backup.boot_img_path)
                if boot_img_path.exists():
                    boot_img_path.unlink()
                
                # 删除元数据文件
                metadata_file = self.backup_dir / f"{backup.backup_id}.json"
                if metadata_file.exists():
                    metadata_file.unlink()
                
                logger.info(f"已删除旧备份: {backup.backup_id}")
            except Exception as e:
                logger.warning(f"删除旧备份失败: {backup.backup_id}, {e}")
    
    def list_backups(self) -> List[BootBackup]:
        """
        列出所有备份
        
        Returns:
            List[BootBackup]: 备份列表
        """
        backups = self.load_all_backups()
        backups.sort(key=lambda b: b.backup_time, reverse=True)
        
        if not backups:
            logger.info("没有找到任何备份")
            return []
        
        logger.info("=" * 80)
        logger.info("Boot.img 备份列表")
        logger.info("=" * 80)
        
        for i, backup in enumerate(backups, 1):
            logger.info(f"\n{i}. {backup.backup_id}")
            logger.info(f"   设备型号: {backup.device_model}")
            logger.info(f"   Build ID: {backup.build_id}")
            logger.info(f"   备份时间: {backup.backup_time}")
            logger.info(f"   类型: {'原厂' if backup.is_stock else '修补后'}")
            logger.info(f"   描述: {backup.description}")
            logger.info(f"   文件路径: {backup.boot_img_path}")
            logger.info(f"   SHA256: {backup.sha256}")
        
        logger.info("=" * 80)
        return backups
    
    def restore_backup(self, backup_id: str) -> bool:
        """
        恢复指定的备份
        
        Args:
            backup_id: 备份 ID
        
        Returns:
            bool: 是否恢复成功
        """
        # 查找备份
        backups = self.load_all_backups()
        backup = next((b for b in backups if b.backup_id == backup_id), None)
        
        if not backup:
            logger.error(f"未找到备份: {backup_id}")
            return False
        
        # 验证备份文件存在
        boot_img_path = Path(backup.boot_img_path)
        if not boot_img_path.exists():
            logger.error(f"备份文件不存在: {boot_img_path}")
            return False
        
        # 刷入备份
        logger.info(f"正在恢复备份: {backup_id}")
        return self.flash_boot_with_recovery(boot_img_path, auto_recover=False)
    
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
