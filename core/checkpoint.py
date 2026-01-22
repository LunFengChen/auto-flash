"""
检查点管理器 - Checkpoint Manager

管理刷机流程的检查点，支持断点续传
"""

import json
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Optional, Any
from dataclasses import dataclass, asdict
from loguru import logger

from .state_machine import FlashState


@dataclass
class Checkpoint:
    """检查点数据类"""
    timestamp: str
    current_state: str  # FlashState 的值
    completed_steps: List[str]
    device_info: Dict[str, str]
    config_snapshot: Dict[str, Any]


class CheckpointManager:
    """检查点管理器"""
    
    def __init__(self, device_serial: str, checkpoint_dir: Path = Path("logs")):
        """
        初始化检查点管理器
        
        Args:
            device_serial: 设备序列号
            checkpoint_dir: 检查点目录
        """
        self.device_serial = device_serial
        self.checkpoint_dir = checkpoint_dir
        self.checkpoint_dir.mkdir(exist_ok=True)
        
        self.checkpoint_file = self.checkpoint_dir / f"checkpoint_{device_serial}.json"
        
        logger.info(f"检查点管理器初始化: device={device_serial}")
    
    def save_checkpoint(
        self,
        current_state: FlashState,
        completed_steps: List[str],
        device_info: Dict[str, str],
        config_snapshot: Dict[str, Any]
    ) -> bool:
        """
        保存检查点
        
        Args:
            current_state: 当前状态
            completed_steps: 已完成的步骤
            device_info: 设备信息
            config_snapshot: 配置快照
        
        Returns:
            是否保存成功
        """
        checkpoint = Checkpoint(
            timestamp=datetime.now().isoformat(),
            current_state=current_state.value,
            completed_steps=completed_steps,
            device_info=device_info,
            config_snapshot=config_snapshot
        )
        
        try:
            with open(self.checkpoint_file, "w", encoding="utf-8") as f:
                json.dump(asdict(checkpoint), f, indent=2, ensure_ascii=False)
            
            logger.info(f"✓ 检查点已保存: {current_state.value}")
            return True
        except Exception as e:
            logger.error(f"✗ 检查点保存失败: {e}")
            return False
    
    def load_checkpoint(self) -> Optional[Checkpoint]:
        """
        加载检查点
        
        Returns:
            检查点数据（如果存在）
        """
        if not self.checkpoint_file.exists():
            logger.info("未找到检查点文件")
            return None
        
        try:
            with open(self.checkpoint_file, "r", encoding="utf-8") as f:
                data = json.load(f)
            
            checkpoint = Checkpoint(**data)
            logger.info(f"✓ 检查点已加载: {checkpoint.current_state}")
            logger.info(f"  时间: {checkpoint.timestamp}")
            logger.info(f"  已完成步骤: {len(checkpoint.completed_steps)}")
            
            return checkpoint
        except Exception as e:
            logger.error(f"✗ 检查点加载失败: {e}")
            return None
    
    def get_state_from_checkpoint(self, checkpoint: Checkpoint) -> 'FlashState':
        """
        从检查点获取 FlashState 枚举
        
        Args:
            checkpoint: 检查点对象
        
        Returns:
            FlashState 枚举
        """
        from .state_machine import FlashState
        
        # 将字符串转换为枚举
        for state in FlashState:
            if state.value == checkpoint.current_state:
                return state
        
        # 如果找不到匹配的状态，返回初始化状态
        logger.warning(f"未找到匹配的状态: {checkpoint.current_state}，使用初始化状态")
        return FlashState.INIT
    
    def clear_checkpoint(self) -> bool:
        """
        清除检查点
        
        Returns:
            是否清除成功
        """
        if not self.checkpoint_file.exists():
            return True
        
        try:
            self.checkpoint_file.unlink()
            logger.info("✓ 检查点已清除")
            return True
        except Exception as e:
            logger.error(f"✗ 检查点清除失败: {e}")
            return False
    
    def has_checkpoint(self) -> bool:
        """
        检查是否存在检查点
        
        Returns:
            是否存在检查点
        """
        return self.checkpoint_file.exists()
    
    def get_checkpoint_age(self) -> Optional[float]:
        """
        获取检查点年龄（秒）
        
        Returns:
            检查点年龄（秒），如果不存在返回 None
        """
        checkpoint = self.load_checkpoint()
        if not checkpoint:
            return None
        
        try:
            checkpoint_time = datetime.fromisoformat(checkpoint.timestamp)
            age = (datetime.now() - checkpoint_time).total_seconds()
            return age
        except Exception:
            return None


# 测试代码
if __name__ == "__main__":
    logger.add("logs/checkpoint_test.log", rotation="10 MB")
    
    # 创建检查点管理器
    cm = CheckpointManager("test_device_123")
    
    # 保存检查点
    print("保存检查点...")
    cm.save_checkpoint(
        current_state=FlashState.INSTALL_APATCH,
        completed_steps=["初始化", "检测设备", "刷入系统"],
        device_info={"model": "redfin", "build": "TQ3A.230805.001"},
        config_snapshot={"apatch_password": "123456"}
    )
    
    # 加载检查点
    print("\n加载检查点...")
    checkpoint = cm.load_checkpoint()
    if checkpoint:
        print(f"  当前状态: {checkpoint.current_state}")
        print(f"  已完成步骤: {checkpoint.completed_steps}")
        print(f"  设备信息: {checkpoint.device_info}")
    
    # 检查年龄
    age = cm.get_checkpoint_age()
    if age is not None:
        print(f"\n检查点年龄: {age:.1f} 秒")
    
    # 清除检查点
    print("\n清除检查点...")
    cm.clear_checkpoint()
    print(f"检查点是否存在: {cm.has_checkpoint()}")
