"""
进度显示 - Progress Display

显示刷机进度、预估时间和步骤信息
"""

import time
from typing import Optional, List
from datetime import datetime, timedelta
from dataclasses import dataclass
from loguru import logger

from .state_machine import FlashState


@dataclass
class ProgressInfo:
    """进度信息"""
    current_step: int
    total_steps: int
    current_state: FlashState
    start_time: datetime
    elapsed_time: float
    estimated_remaining: Optional[float]
    completed_steps: List[str]


class ProgressDisplay:
    """进度显示器"""
    
    def __init__(self, total_steps: int = 12):
        """
        初始化进度显示器
        
        Args:
            total_steps: 总步骤数
        """
        self.total_steps = total_steps
        self.current_step = 0
        self.start_time = datetime.now()
        self.step_times: List[float] = []
        self.completed_steps: List[str] = []
        
        logger.info(f"进度显示器初始化: total_steps={total_steps}")
    
    def update(self, state: FlashState, step_name: Optional[str] = None):
        """
        更新进度
        
        Args:
            state: 当前状态
            step_name: 步骤名称（可选）
        """
        self.current_step += 1
        
        # 记录步骤完成时间
        if self.current_step > 1:
            step_time = time.time() - self.start_time.timestamp()
            self.step_times.append(step_time)
        
        # 记录已完成步骤
        if step_name:
            self.completed_steps.append(step_name)
        
        # 显示进度
        self.display(state)
    
    def display(self, state: FlashState):
        """
        显示当前进度
        
        Args:
            state: 当前状态
        """
        # 计算进度百分比
        progress = (self.current_step / self.total_steps) * 100
        
        # 计算已用时间
        elapsed = (datetime.now() - self.start_time).total_seconds()
        
        # 估算剩余时间
        estimated_remaining = self.estimate_remaining_time()
        
        # 构造进度条
        bar_length = 40
        filled_length = int(bar_length * self.current_step / self.total_steps)
        bar = "█" * filled_length + "░" * (bar_length - filled_length)
        
        # 显示进度信息
        logger.info("=" * 60)
        logger.info(f"进度: [{bar}] {progress:.1f}%")
        logger.info(f"当前状态: {state.value}")
        logger.info(f"步骤: {self.current_step}/{self.total_steps}")
        logger.info(f"已用时间: {self.format_time(elapsed)}")
        
        if estimated_remaining:
            logger.info(f"预计剩余: {self.format_time(estimated_remaining)}")
            eta = datetime.now() + timedelta(seconds=estimated_remaining)
            logger.info(f"预计完成: {eta.strftime('%H:%M:%S')}")
        
        logger.info("=" * 60)
    
    def estimate_remaining_time(self) -> Optional[float]:
        """
        估算剩余时间
        
        Returns:
            剩余时间（秒），如果无法估算返回 None
        """
        if len(self.step_times) < 2:
            return None
        
        # 计算平均每步时间
        avg_step_time = sum(self.step_times) / len(self.step_times)
        
        # 估算剩余时间
        remaining_steps = self.total_steps - self.current_step
        estimated_remaining = avg_step_time * remaining_steps
        
        return estimated_remaining
    
    def format_time(self, seconds: float) -> str:
        """
        格式化时间
        
        Args:
            seconds: 秒数
        
        Returns:
            格式化的时间字符串
        """
        if seconds < 60:
            return f"{seconds:.0f}秒"
        elif seconds < 3600:
            minutes = seconds / 60
            return f"{minutes:.1f}分钟"
        else:
            hours = seconds / 3600
            return f"{hours:.1f}小时"
    
    def get_progress_info(self, state: FlashState) -> ProgressInfo:
        """
        获取进度信息
        
        Args:
            state: 当前状态
        
        Returns:
            进度信息对象
        """
        elapsed = (datetime.now() - self.start_time).total_seconds()
        estimated_remaining = self.estimate_remaining_time()
        
        return ProgressInfo(
            current_step=self.current_step,
            total_steps=self.total_steps,
            current_state=state,
            start_time=self.start_time,
            elapsed_time=elapsed,
            estimated_remaining=estimated_remaining,
            completed_steps=self.completed_steps.copy()
        )
    
    def display_summary(self, success: bool):
        """
        显示完成总结
        
        Args:
            success: 是否成功完成
        """
        elapsed = (datetime.now() - self.start_time).total_seconds()
        
        logger.info("=" * 60)
        if success:
            logger.info("✓ 刷机完成")
        else:
            logger.error("✗ 刷机失败")
        
        logger.info(f"总耗时: {self.format_time(elapsed)}")
        logger.info(f"完成步骤: {len(self.completed_steps)}/{self.total_steps}")
        logger.info("=" * 60)
        
        if self.completed_steps:
            logger.info("已完成步骤:")
            for i, step in enumerate(self.completed_steps, 1):
                logger.info(f"  {i}. {step}")
            logger.info("=" * 60)


class BatchProgressDisplay:
    """批量刷机进度显示器"""
    
    def __init__(self, device_serials: List[str]):
        """
        初始化批量进度显示器
        
        Args:
            device_serials: 设备序列号列表
        """
        self.device_serials = device_serials
        self.device_progress: dict = {serial: 0.0 for serial in device_serials}
        self.device_status: dict = {serial: "pending" for serial in device_serials}
        self.device_state: dict = {serial: FlashState.INIT for serial in device_serials}
        self.start_time = datetime.now()
        
        logger.info(f"批量进度显示器初始化: {len(device_serials)} 台设备")
    
    def update_device(
        self,
        serial: str,
        progress: float,
        status: str,
        state: FlashState
    ):
        """
        更新设备进度
        
        Args:
            serial: 设备序列号
            progress: 进度（0.0 - 1.0）
            status: 状态字符串
            state: 当前状态
        """
        self.device_progress[serial] = progress
        self.device_status[serial] = status
        self.device_state[serial] = state
    
    def display_dashboard(self):
        """显示进度仪表盘"""
        import os
        
        # 清屏
        os.system('cls' if os.name == 'nt' else 'clear')
        
        # 计算统计信息
        completed = sum(1 for status in self.device_status.values() if status == "completed")
        failed = sum(1 for status in self.device_status.values() if status == "failed")
        running = sum(1 for status in self.device_status.values() if status == "running")
        pending = sum(1 for status in self.device_status.values() if status == "pending")
        
        # 计算总进度
        total_progress = sum(self.device_progress.values()) / len(self.device_serials) * 100
        
        # 计算已用时间
        elapsed = (datetime.now() - self.start_time).total_seconds()
        
        # 显示标题
        print("=" * 80)
        print(f"批量刷机进度监控 - {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
        print("=" * 80)
        
        # 显示统计信息
        print(f"总进度: {total_progress:.1f}%")
        print(f"总计: {len(self.device_serials)} | 完成: {completed} | 失败: {failed} | 进行中: {running} | 等待: {pending}")
        print(f"已用时间: {self.format_time(elapsed)}")
        print("-" * 80)
        
        # 显示每台设备的进度
        for serial in self.device_serials:
            status = self.device_status[serial]
            progress = self.device_progress[serial]
            state = self.device_state[serial]
            
            # 状态图标
            status_icon = {
                "completed": "✅",
                "failed": "❌",
                "running": "🔄",
                "pending": "⏳"
            }.get(status, "❓")
            
            # 进度条
            bar_length = 20
            filled = int(bar_length * progress)
            bar = "█" * filled + "░" * (bar_length - filled)
            
            print(f"{status_icon} {serial}: [{bar}] {progress*100:.0f}% - {state.value}")
        
        print("=" * 80)
    
    def format_time(self, seconds: float) -> str:
        """格式化时间"""
        if seconds < 60:
            return f"{seconds:.0f}秒"
        elif seconds < 3600:
            minutes = seconds / 60
            return f"{minutes:.1f}分钟"
        else:
            hours = seconds / 3600
            return f"{hours:.1f}小时"


# 测试代码
if __name__ == "__main__":
    logger.add("logs/progress_display_test.log", rotation="10 MB")
    
    print("\n测试 1: 单设备进度显示")
    progress = ProgressDisplay(total_steps=5)
    
    states = [
        FlashState.INIT,
        FlashState.CHECK_DEVICE,
        FlashState.REBOOT_BOOTLOADER,
        FlashState.FLASH_SYSTEM,
        FlashState.COMPLETED
    ]
    
    for state in states:
        progress.update(state, state.value)
        time.sleep(0.5)
    
    progress.display_summary(success=True)
    
    print("\n测试 2: 批量进度显示")
    batch_progress = BatchProgressDisplay(["device1", "device2", "device3"])
    
    # 模拟进度更新
    for i in range(5):
        batch_progress.update_device("device1", i * 0.2, "running", FlashState.FLASH_SYSTEM)
        batch_progress.update_device("device2", i * 0.15, "running", FlashState.WAIT_BOOT)
        batch_progress.update_device("device3", i * 0.1, "running", FlashState.CHECK_DEVICE)
        
        batch_progress.display_dashboard()
        time.sleep(1)
    
    # 标记完成
    batch_progress.update_device("device1", 1.0, "completed", FlashState.COMPLETED)
    batch_progress.update_device("device2", 1.0, "completed", FlashState.COMPLETED)
    batch_progress.update_device("device3", 0.5, "failed", FlashState.ERROR)
    
    batch_progress.display_dashboard()
