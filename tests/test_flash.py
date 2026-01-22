#!/usr/bin/env python3
"""
测试刷机流程 - 简化版

用于测试基础刷机功能
"""

import sys
from pathlib import Path
from loguru import logger

# 配置日志
logger.remove()
logger.add(
    sys.stderr,
    format="<green>{time:HH:mm:SS}</green> <level>[{level}]</level> <level>{message}</level>",
    level="INFO",
    colorize=True
)

logger.add(
    Path("logs") / "test_flash_{time:YYYYMMDD_HHmmss}.log",
    format="{time:YYYY-MM-DD HH:mm:ss} [{level}] {name}:{line} - {message}",
    level="DEBUG",
    rotation="10 MB"
)

from core.flash_orchestrator import FlashOrchestrator

def main():
    """主函数"""
    logger.info("=" * 60)
    logger.info("Android 全自动刷机工具 - 测试版")
    logger.info("=" * 60)
    
    # 创建刷机编排器
    orchestrator = FlashOrchestrator(
        device_model="redfin",  # 使用设备代号
        config_path=Path("config.yaml"),
        resume=False,
        boot_only=False,
        dry_run=False
    )
    
    try:
        # 执行刷机流程
        success = orchestrator.run()
        
        if success:
            logger.info("\n" + "=" * 60)
            logger.info("✓ 刷机完成！")
            logger.info("=" * 60)
            return 0
        else:
            logger.error("\n" + "=" * 60)
            logger.error("✗ 刷机失败")
            logger.error("=" * 60)
            return 1
            
    except KeyboardInterrupt:
        logger.warning("\n用户中断刷机流程")
        return 130
    except Exception as e:
        logger.exception(f"刷机过程中发生异常: {e}")
        return 1

if __name__ == "__main__":
    sys.exit(main())
