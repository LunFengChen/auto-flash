"""
状态机 - State Machine

管理刷机流程的状态转换，确保流程可控和可恢复
"""

from enum import Enum
from typing import Dict, Callable, Optional, List, TYPE_CHECKING
from dataclasses import dataclass
from loguru import logger

if TYPE_CHECKING:
    from .checkpoint import CheckpointManager


class FlashState(Enum):
    """刷机状态枚举"""
    INIT = "初始化"
    CHECK_DEVICE = "检测设备"
    REBOOT_BOOTLOADER = "重启到Bootloader"
    FLASH_SYSTEM = "刷入系统"
    WAIT_BOOT = "等待系统启动"
    SETUP_WIZARD = "完成初始化向导"
    ENABLE_DEV_MODE = "开启开发者模式"
    INSTALL_APATCH = "安装APatch"
    PATCH_BOOT = "修补boot.img"
    FLASH_BOOT = "刷入修补后的boot"
    INSTALL_APKS = "安装APK"
    INSTALL_MODULES = "安装模块"
    COMPLETED = "完成"
    ERROR = "错误"


@dataclass
class StateTransition:
    """状态转换规则"""
    from_state: FlashState
    to_state: FlashState
    condition: Optional[Callable[[], bool]] = None


class FlashStateMachine:
    """刷机状态机"""
    
    def __init__(
        self, 
        initial_state: FlashState = FlashState.INIT,
        checkpoint_manager: Optional['CheckpointManager'] = None,
        device_info: Optional[Dict] = None
    ):
        """
        初始化状态机
        
        Args:
            initial_state: 初始状态
            checkpoint_manager: 检查点管理器（可选）
            device_info: 设备信息（可选）
        """
        self.current_state = initial_state
        self.completed_steps: List[str] = []
        self.state_handlers: Dict[FlashState, Callable] = {}
        self.transitions: List[StateTransition] = []
        self.checkpoint_manager = checkpoint_manager
        self.device_info = device_info or {}
        
        # 定义状态转换规则
        self._define_transitions()
        
        logger.info(f"状态机初始化: 当前状态={self.current_state.value}")
        if checkpoint_manager:
            logger.info("✓ 检查点自动保存已启用")
    
    def _define_transitions(self):
        """定义状态转换规则"""
        # 标准流程
        self.transitions = [
            StateTransition(FlashState.INIT, FlashState.CHECK_DEVICE),
            StateTransition(FlashState.CHECK_DEVICE, FlashState.REBOOT_BOOTLOADER),
            StateTransition(FlashState.REBOOT_BOOTLOADER, FlashState.FLASH_SYSTEM),
            StateTransition(FlashState.FLASH_SYSTEM, FlashState.WAIT_BOOT),
            StateTransition(FlashState.WAIT_BOOT, FlashState.SETUP_WIZARD),
            StateTransition(FlashState.SETUP_WIZARD, FlashState.ENABLE_DEV_MODE),
            StateTransition(FlashState.ENABLE_DEV_MODE, FlashState.INSTALL_APATCH),
            StateTransition(FlashState.INSTALL_APATCH, FlashState.PATCH_BOOT),
            StateTransition(FlashState.PATCH_BOOT, FlashState.FLASH_BOOT),
            StateTransition(FlashState.FLASH_BOOT, FlashState.INSTALL_APKS),
            StateTransition(FlashState.INSTALL_APKS, FlashState.INSTALL_MODULES),
            StateTransition(FlashState.INSTALL_MODULES, FlashState.COMPLETED),
        ]
    
    def register_handler(self, state: FlashState, handler: Callable):
        """
        注册状态处理函数
        
        Args:
            state: 状态
            handler: 处理函数
        """
        self.state_handlers[state] = handler
        logger.debug(f"注册状态处理函数: {state.value}")
    
    def transition_to(self, next_state: FlashState) -> bool:
        """
        转换到下一个状态
        
        Args:
            next_state: 目标状态
        
        Returns:
            是否转换成功
        """
        # 检查转换是否合法
        valid_transition = False
        for transition in self.transitions:
            if transition.from_state == self.current_state and transition.to_state == next_state:
                # 检查条件（如果有）
                if transition.condition is None or transition.condition():
                    valid_transition = True
                    break
        
        # 错误状态可以从任何状态进入
        if next_state == FlashState.ERROR:
            valid_transition = True
        
        if not valid_transition:
            logger.warning(f"⚠ 非法状态转换: {self.current_state.value} -> {next_state.value}")
            return False
        
        # 执行转换
        logger.info(f"状态转换: {self.current_state.value} -> {next_state.value}")
        self.completed_steps.append(self.current_state.value)
        self.current_state = next_state
        
        # 自动保存检查点（如果启用）
        if self.checkpoint_manager and next_state not in [FlashState.ERROR, FlashState.COMPLETED]:
            try:
                self.checkpoint_manager.save_checkpoint(
                    current_state=next_state,
                    completed_steps=self.completed_steps,
                    device_info=self.device_info,
                    config_snapshot={}
                )
            except Exception as e:
                logger.warning(f"⚠ 检查点保存失败: {e}")
                # 不中断流程，继续执行
        
        return True
    
    def execute_state(self) -> Optional[FlashState]:
        """
        执行当前状态的操作
        
        Returns:
            下一个状态（如果有）
        """
        handler = self.state_handlers.get(self.current_state)
        
        if not handler:
            logger.warning(f"⚠ 未找到状态处理函数: {self.current_state.value}")
            return None
        
        try:
            logger.info(f"▶ 执行状态: {self.current_state.value}")
            next_state = handler()
            return next_state
        except Exception as e:
            logger.error(f"✗ 状态执行失败: {self.current_state.value}, {e}")
            import traceback
            traceback.print_exc()
            return FlashState.ERROR
    
    def run(self) -> bool:
        """
        运行状态机（主循环）
        
        Returns:
            是否成功完成
        """
        logger.info("=" * 60)
        logger.info("状态机开始运行")
        logger.info("=" * 60)
        
        while self.current_state not in [FlashState.COMPLETED, FlashState.ERROR]:
            # 执行当前状态
            next_state = self.execute_state()
            
            if next_state is None:
                logger.error("✗ 状态机执行中断")
                return False
            
            # 转换到下一个状态
            if not self.transition_to(next_state):
                logger.error("✗ 状态转换失败")
                return False
        
        # 检查最终状态
        if self.current_state == FlashState.COMPLETED:
            logger.info("=" * 60)
            logger.info("✓ 状态机执行完成")
            logger.info("=" * 60)
            return True
        else:
            logger.error("=" * 60)
            logger.error("✗ 状态机执行失败")
            logger.error("=" * 60)
            return False
    
    def get_progress(self) -> float:
        """
        获取当前进度
        
        Returns:
            进度百分比（0.0 - 1.0）
        """
        total_states = len([s for s in FlashState if s not in [FlashState.ERROR, FlashState.COMPLETED]])
        completed = len(self.completed_steps)
        return completed / total_states if total_states > 0 else 0.0
    
    def get_state_name(self) -> str:
        """
        获取当前状态名称
        
        Returns:
            状态名称
        """
        return self.current_state.value


# 测试代码
if __name__ == "__main__":
    logger.add("logs/state_machine_test.log", rotation="10 MB")
    
    # 创建状态机
    sm = FlashStateMachine()
    
    # 注册测试处理函数
    def handle_init():
        print("  [INIT] 初始化...")
        return FlashState.CHECK_DEVICE
    
    def handle_check_device():
        print("  [CHECK_DEVICE] 检测设备...")
        return FlashState.REBOOT_BOOTLOADER
    
    def handle_reboot_bootloader():
        print("  [REBOOT_BOOTLOADER] 重启到 Bootloader...")
        return FlashState.COMPLETED  # 测试：直接跳到完成
    
    sm.register_handler(FlashState.INIT, handle_init)
    sm.register_handler(FlashState.CHECK_DEVICE, handle_check_device)
    sm.register_handler(FlashState.REBOOT_BOOTLOADER, handle_reboot_bootloader)
    
    # 运行状态机
    print("\n开始测试状态机:")
    success = sm.run()
    print(f"\n结果: {'成功' if success else '失败'}")
    print(f"进度: {sm.get_progress() * 100:.1f}%")
    print(f"已完成步骤: {sm.completed_steps}")
