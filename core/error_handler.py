"""
错误处理器 - Error Handler

处理刷机过程中的各种错误，提供重试和恢复机制
"""

import time
import subprocess
from typing import Callable, Any, Optional
from pathlib import Path
from datetime import datetime
from loguru import logger

from .state_machine import FlashState


class ErrorHandler:
    """错误处理器 - 提供重试和恢复机制"""
    
    def __init__(self, max_retries: int = 3):
        """
        初始化错误处理器
        
        Args:
            max_retries: 最大重试次数
        """
        self.max_retries = max_retries
        self.error_log_dir = Path("logs/errors")
        self.error_log_dir.mkdir(parents=True, exist_ok=True)
        
        logger.info(f"错误处理器初始化: max_retries={max_retries}")
    
    def retry_on_failure(
        self,
        func: Callable,
        *args,
        retry_delay: float = 2.0,
        exponential_backoff: bool = True,
        **kwargs
    ) -> Any:
        """
        失败时自动重试
        
        Args:
            func: 要执行的函数
            *args: 函数参数
            retry_delay: 重试延迟（秒）
            exponential_backoff: 是否使用指数退避
            **kwargs: 函数关键字参数
        
        Returns:
            函数返回值
        
        Raises:
            Exception: 重试次数用尽后抛出最后一次异常
        """
        last_exception = None
        
        for attempt in range(self.max_retries):
            try:
                logger.info(f"尝试 {attempt + 1}/{self.max_retries}: {func.__name__}")
                result = func(*args, **kwargs)
                
                if attempt > 0:
                    logger.info(f"✓ 重试成功: {func.__name__}")
                
                return result
                
            except Exception as e:
                last_exception = e
                logger.warning(f"✗ 尝试 {attempt + 1}/{self.max_retries} 失败: {e}")
                
                # 如果还有重试机会，等待后重试
                if attempt < self.max_retries - 1:
                    if exponential_backoff:
                        delay = retry_delay * (2 ** attempt)
                    else:
                        delay = retry_delay
                    
                    logger.info(f"等待 {delay:.1f} 秒后重试...")
                    time.sleep(delay)
        
        # 重试次数用尽，抛出异常
        logger.error(f"✗ 重试次数用尽: {func.__name__}")
        raise last_exception
    
    def handle_critical_error(
        self,
        error: Exception,
        state: FlashState,
        device_serial: Optional[str] = None
    ):
        """
        处理致命错误
        
        Args:
            error: 异常对象
            state: 发生错误的状态
            device_serial: 设备序列号（可选）
        """
        logger.error("=" * 60)
        logger.error("致命错误")
        logger.error("=" * 60)
        logger.error(f"状态: {state.value}")
        logger.error(f"错误: {error}")
        if device_serial:
            logger.error(f"设备: {device_serial}")
        logger.error("=" * 60)
        
        # 保存错误日志
        error_log_file = self.save_error_log(error, state, device_serial)
        
        # 尝试恢复设备到安全状态
        if device_serial:
            self.recover_device(device_serial)
        
        # 提示用户
        print(f"\n❌ 刷机失败: {error}")
        print(f"错误日志已保存到: {error_log_file}")
        print("请检查日志并手动恢复设备")
    
    def save_error_log(
        self,
        error: Exception,
        state: FlashState,
        device_serial: Optional[str] = None
    ) -> Path:
        """
        保存错误日志到文件
        
        Args:
            error: 异常对象
            state: 发生错误的状态
            device_serial: 设备序列号（可选）
        
        Returns:
            错误日志文件路径
        """
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        device_suffix = f"_{device_serial}" if device_serial else ""
        error_log_file = self.error_log_dir / f"error_{timestamp}{device_suffix}.log"
        
        import traceback
        
        with open(error_log_file, "w", encoding="utf-8") as f:
            f.write("=" * 80 + "\n")
            f.write("刷机错误日志\n")
            f.write("=" * 80 + "\n\n")
            
            f.write(f"时间: {datetime.now().isoformat()}\n")
            f.write(f"状态: {state.value}\n")
            if device_serial:
                f.write(f"设备: {device_serial}\n")
            f.write(f"错误类型: {type(error).__name__}\n")
            f.write(f"错误信息: {str(error)}\n\n")
            
            f.write("=" * 80 + "\n")
            f.write("堆栈跟踪\n")
            f.write("=" * 80 + "\n\n")
            f.write(traceback.format_exc())
        
        logger.info(f"错误日志已保存: {error_log_file}")
        return error_log_file
    
    def recover_device(self, device_serial: Optional[str] = None):
        """
        尝试将设备恢复到安全状态
        
        Args:
            device_serial: 设备序列号（可选）
        """
        logger.info("尝试恢复设备到安全状态...")
        
        try:
            # 构造命令前缀
            adb_prefix = ["adb"]
            fastboot_prefix = ["fastboot"]
            
            if device_serial:
                adb_prefix.extend(["-s", device_serial])
                fastboot_prefix.extend(["-s", device_serial])
            
            # 检查设备是否在 fastboot 模式
            result = subprocess.run(
                fastboot_prefix + ["devices"],
                capture_output=True,
                text=True,
                timeout=5
            )
            
            if "fastboot" in result.stdout:
                logger.info("设备在 fastboot 模式，尝试重启到系统...")
                subprocess.run(
                    fastboot_prefix + ["reboot"],
                    timeout=10
                )
                logger.info("✓ 设备已从 fastboot 模式重启")
                return
            
            # 检查设备是否在 ADB 模式
            result = subprocess.run(
                adb_prefix + ["devices"],
                capture_output=True,
                text=True,
                timeout=5
            )
            
            if "device" in result.stdout:
                logger.info("✓ 设备在 ADB 模式，状态正常")
                return
            
            logger.warning("⚠ 无法检测到设备，可能需要手动恢复")
            
        except Exception as e:
            logger.error(f"✗ 设备恢复失败: {e}")
    
    def classify_error(self, error: Exception) -> str:
        """
        错误分类
        
        Args:
            error: 异常对象
        
        Returns:
            错误类型字符串
        """
        error_type = type(error).__name__
        error_msg = str(error).lower()
        
        # 设备连接错误
        if "device" in error_msg and ("not found" in error_msg or "offline" in error_msg):
            return "DEVICE_DISCONNECTED"
        
        # 超时错误
        if "timeout" in error_msg or error_type == "TimeoutExpired":
            return "TIMEOUT"
        
        # 文件不存在
        if error_type == "FileNotFoundError":
            return "FILE_NOT_FOUND"
        
        # 权限错误
        if error_type == "PermissionError":
            return "PERMISSION_DENIED"
        
        # UI 元素未找到
        if "element" in error_msg and "not found" in error_msg:
            return "UI_ELEMENT_NOT_FOUND"
        
        # 默认
        return "UNKNOWN"


# 测试代码
if __name__ == "__main__":
    logger.add("logs/error_handler_test.log", rotation="10 MB")
    
    # 创建错误处理器
    handler = ErrorHandler(max_retries=3)
    
    # 测试重试机制
    def flaky_function(success_on_attempt: int):
        """模拟不稳定的函数"""
        if not hasattr(flaky_function, "attempt"):
            flaky_function.attempt = 0
        
        flaky_function.attempt += 1
        print(f"  尝试 {flaky_function.attempt}")
        
        if flaky_function.attempt < success_on_attempt:
            raise RuntimeError(f"失败 (尝试 {flaky_function.attempt})")
        
        return "成功!"
    
    print("\n测试 1: 第 2 次尝试成功")
    try:
        result = handler.retry_on_failure(flaky_function, 2)
        print(f"结果: {result}")
    except Exception as e:
        print(f"失败: {e}")
    
    # 重置计数器
    delattr(flaky_function, "attempt")
    
    print("\n测试 2: 所有尝试都失败")
    try:
        result = handler.retry_on_failure(flaky_function, 10)
        print(f"结果: {result}")
    except Exception as e:
        print(f"失败: {e}")
    
    print("\n测试 3: 错误分类")
    errors = [
        FileNotFoundError("boot.img not found"),
        TimeoutError("Connection timeout"),
        RuntimeError("Device not found"),
        PermissionError("Access denied"),
    ]
    
    for error in errors:
        error_type = handler.classify_error(error)
        print(f"  {type(error).__name__}: {error_type}")
