#!/usr/bin/env python3
"""
测试 boot.img 修补功能
"""

import logging
from pathlib import Path
from core.boot_patcher import BootPatcher, BootPatchConfig

# 配置日志 - 简洁格式，应用到所有 logger
logging.basicConfig(
    level=logging.INFO,
    format='%(message)s',  # 只输出消息，不要时间戳和模块名
    force=True  # 强制重新配置
)

# 确保 core.boot_patcher 的 logger 也使用相同配置
logging.getLogger('core.boot_patcher').setLevel(logging.INFO)

def main():
    # 配置
    config = BootPatchConfig(
        device_model='redfin',
        build_id='TQ3A.230901.001.C2',
        firmware_dir=Path('resources/devices/redfin/TQ3A.230901.001.C2/firmware'),
        root_dir=Path('resources/devices/redfin/TQ3A.230901.001.C2/root'),
        superkey='xiaofeng777',
        patch_tools_dir=Path('resources/common/tools'),
        binary_dir=Path('resources/common/binary'),
        kpimg_version='0.12.7',  # 使用 0.12.7 版本
        # 可选：嵌入 KPM 模块
        # kpm_modules=[
        #     Path('resources/common/modules/kpm/example.kpm'),
        # ],
        # 可选：额外参数
        # extra_args=['-a', 'custom_key=custom_value']
    )
    
    print("=" * 60)
    print("Boot.img 修补测试")
    print("=" * 60)
    print(f"设备: {config.device_model}")
    print(f"Build: {config.build_id}")
    print(f"SuperKey: {config.superkey}")
    print(f"KernelPatch 版本: {config.kpimg_version}")
    if config.kpm_modules:
        print(f"KPM 模块: {', '.join(m.name for m in config.kpm_modules)}")
    if config.extra_args:
        print(f"额外参数: {' '.join(config.extra_args)}")
    print("=" * 60)
    
    # 创建 patcher
    patcher = BootPatcher(config)
    
    print(f"\n工具检查:")
    print(f"  magiskboot: {patcher.magiskboot}")
    print(f"  kptools: {patcher.kptools}")
    print(f"  kpimg: {patcher.kpimg}")
    print(f"  检测到的版本: {patcher.kpimg_version}")
    
    # 开始修补
    print(f"\n开始修补...")
    try:
        patched_boot = patcher.get_or_create_patched_boot()
        print(f"\n✅ 修补成功!")
        print(f"   输出文件: {patched_boot}")
        print(f"   文件大小: {patched_boot.stat().st_size / 1024 / 1024:.2f} MB")
        
        # 验证
        print(f"\n验证修补...")
        if patcher.verify_patched_boot(patched_boot):
            print(f"✅ 验证通过! boot.img 已正确修补")
        else:
            print(f"❌ 验证失败! boot.img 可能未正确修补")
            
    except Exception as e:
        print(f"\n❌ 修补失败: {e}")
        import traceback
        traceback.print_exc()
        return 1
    
    return 0

if __name__ == "__main__":
    exit(main())
