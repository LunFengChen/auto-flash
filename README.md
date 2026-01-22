# Android 全自动刷机工具

[English](#english) | [中文](#中文)

---

## 中文

一个通用的 Android 自动刷机框架，支持多设备型号，最小化人工干预，实现从原始系统到完整 Root 环境的一键部署。

作者主要是为了解决繁琐重复的刷机过程，为了后续拿来群控刷机和后续rom批量改机而写；只适配了windows，其他平台自己配置环境变量就行；有其他问题可以提交issue和pr，也可以fork后自行修改；

> 注意证书是嵌入模块了的可以参考：https://github.com/LunFengChen/MoveCertificate 

### ✨ 核心特性

**已实现功能** ✅：
- **自动刷机**：自动刷入系统、boot.img、安装 APK、安装模块
- **多设备支持**：支持 Google Pixel 5 (redfin)，可扩展其他设备
- **并发刷机**：同时刷机多台设备，节省时间
- **断点续传**：支持中断后从检查点继续执行
- **自动恢复**：刷机失败自动恢复到原厂 boot.img
- **Boot.img 修补**：使用 KernelPatch 工具修补 boot.img（Windows 平台）
- **模块安装**：自动安装 LSPosed、Zygisk 等模块
- **APK 安装**：自动安装 Root APK、通用 APK、LSP 模块 APK、Zygisk 模块 APK
- **自动获取设备型号**：通过 ADB/Fastboot 自动识别设备型号，无需手动输入

**未实现功能** ⚠️：
- **UI 自动化**：初始化向导、开发者模式等需要手动完成
  - `skip_setup_wizard: true` - 配置已禁用，需手动完成初始化
  - `auto_enable_dev_mode: false` - 配置已禁用，需手动开启开发者模式
- **Magisk 支持**：代码框架已有，但未实现
- **KernelSU 支持**：代码框架已有，但未实现

### 📱 支持的设备

**首批支持**：
- Google Pixel 5 (redfin)

**可扩展**：通过编写设备适配器支持更多设备

### 🔧 Root 方案支持

| Root 方案 | 状态 | 说明 |
|----------|------|------|
| **APatch** | ✅ 已支持 | 完整支持，包括 boot.img 修补、模块安装 |
| **Magisk** | 🚧 开发中 | 计划支持 |
| **KernelSU** | 🚧 开发中 | 计划支持 |

**当前推荐使用 APatch**

### 🚀 快速开始

#### 1. 安装

```bash
# 克隆项目
git clone https://github.com/yourusername/android-auto-flash.git
cd android-auto-flash

# 安装依赖
pip install -r requirements.txt
```

#### 2. 准备资源

**资源目录结构说明**：

```bash
# 通用资源（所有设备共享）
resources/common/
├── apks/                       # 通用 APK（会自动安装）
│   ├── APatch_xxx.apk          # Root 管理器 APK
│   ├── reqable-app-android-arm64.apk
│   ├── clashmi_xxx.apk
│   └── ...
├── modules/                    # 模块目录（按类型分类）
│   ├── zip/                    # Magisk/APatch 模块（.zip 格式）
│   │   ├── LSPosed-v1.9.2-7058-zygisk-release.zip
│   │   ├── ZygiskNext-1.2.9.1-534-b8e7e21-release.zip
│   │   ├── MoveCertificate-v1.0.1-xxx-withCert.zip
│   │   └── zygisk-gadget-xiaojia.zip
│   ├── lsp/                    # LSPosed 模块（.apk 格式）
│   │   ├── BlackDex64.apk
│   │   ├── HideMyApp-V3.6.1.r462.4524dde-release.apk
│   │   ├── 我不是开发者_1.6.1.apk
│   │   ├── 截屏录屏绕过.apk
│   │   └── 算法助手Pro_1.0.9.apk
│   ├── zygisk/                 # Zygisk 模块（.apk 格式）
│   │   └── 小佳gadget小工具.apk
│   └── kpm/                    # KernelPatch 模块（.kpm 格式）
│       └── (暂无，预留)
└── tools/                      # 修补工具（Windows 平台）
    ├── kptools-msys2-0.12.7.exe
    ├── kpimg-android-0.12.7
    ├── magiskboot.exe
    ├── msys-2.0.dll
    └── msys-z.dll

# 设备特定资源
resources/devices/redfin/TQ3A.230901.001.C2/
├── firmware/                   # 原厂固件
│   ├── boot.img                # 原厂 boot 镜像
│   ├── bootloader-redfin-r3-0.5-9825705.img
│   ├── radio-redfin-g7250-00258-230518-b-10157620.img
│   └── image-redfin-tq3a.230901.001.c2.zip
└── root/                       # Root 相关文件
    └── apatch_patched_TQ3A.230901.001.C2_0.12.7.img  # 修补后的 boot.img
```

**模块安装说明**：

工具会按以下顺序自动安装模块：

1. **安装 zip 模块** (`modules/zip/`)
   - LSPosed、ZygiskNext、MoveCertificate 等
   - 通过 APatch 管理器安装
   - 需要重启生效

2. **安装 LSP 模块 APK** (`modules/lsp/`)
   - BlackDex64、HideMyApp、算法助手 Pro 等
   - 通过 `adb install` 安装到系统
   - 需要在 LSPosed 管理器中激活

3. **安装 Zygisk 模块 APK** (`modules/zygisk/`)
   - 小佳 gadget 小工具等
   - 通过 `adb install` 安装到系统
   - 需要在 Zygisk 管理器中激活

4. **安装 KPM 模块** (`modules/kpm/`)
   - KernelPatch 模块（如果有）
   - 通过 KernelPatch 工具安装

**实际例子**（当前配置）：

```bash
# 1. zip 模块（4 个）
LSPosed-v1.9.2-7058-zygisk-release.zip          # LSPosed 框架
ZygiskNext-1.2.9.1-534-b8e7e21-release.zip      # Zygisk 实现
MoveCertificate-v1.0.1-xxx-withCert.zip         # 证书移动模块
zygisk-gadget-xiaojia.zip                       # Gadget 工具

# 2. LSP 模块（5 个）
BlackDex64.apk                                  # 脱壳工具
HideMyApp-V3.6.1.r462.4524dde-release.apk      # 隐藏应用
我不是开发者_1.6.1.apk                          # 开发者选项隐藏
截屏录屏绕过.apk                                # 截屏检测绕过
算法助手Pro_1.0.9.apk                           # 算法助手

# 3. Zygisk 模块（1 个）
小佳gadget小工具.apk                            # Gadget 小工具

# 4. 通用 APK（会自动安装到系统）
reqable-app-android-arm64.apk                   # 抓包工具
clashmi_xxx.apk                                 # 代理工具
frida环境检测.apk                               # Frida 检测
环境检测-by小枫.apk                             # 环境检测
```

#### 3. 配置

编辑 `config.yaml`：

```yaml
# 全局配置
adb_path: "adb"
fastboot_path: "fastboot"

# Root 方案（当前仅支持 apatch）
root_method: "apatch"

# 设备配置
devices:
  redfin:
    model: "redfin"
    build_id: "TQ3A.230901.001.C2"
    superkey: "your_superkey_here"
    boot_img_source: "firmware"  # 或 "patched"
```

#### 4. 运行刷机

```bash
# 直接运行，交互式选择设备
python main.py

# 会自动检测设备并显示:
# ============================================================
# 检测到以下设备:
# ============================================================
#   [1] 0A281FDD40024G (有检查点: 安装APatch, 已完成 7 步)
#   [2] 13081FDD4002VL
#   [A] 全部设备并发刷机
#   [Q] 退出
# ============================================================
# 请选择设备 (输入序号/A/Q): 
#
# 正在获取设备型号...
# ✓ 检测到设备型号: redfin
```

**使用说明**:
- 输入 `1` 或 `2` 刷机单个设备
- 输入 `A` 并发刷机所有设备（推荐，节省时间）
- 输入 `Q` 退出
- 如果设备有检查点，会自动询问是否恢复
- 设备型号会自动通过 ADB/Fastboot 获取，无需手动输入

**刷机流程**:
1. ✅ 自动检测设备并获取型号
2. ✅ 验证配置和兼容性
3. ✅ 重启到 Bootloader 模式
4. ✅ 刷入系统（bootloader、radio、system）
5. ✅ 等待系统启动
6. ✋ **手动完成初始化向导**（选择语言、WiFi 等）
7. ✋ **手动开启开发者模式**（设置 → 关于手机 → 连续点击版本号 7 次）
8. ✋ **手动开启 USB 调试**（开发者选项 → USB 调试）
9. ✅ 安装 APatch APK
10. ✅ 修补 boot.img
11. ✅ 刷入修补后的 boot.img
12. ✅ 安装所有 APK（通用 APK + LSP 模块 APK + Zygisk 模块 APK）
13. ✋ **手动打开 APatch 应用并授予权限** （如果是我改的apatch是可以自动化完成这一步的）
14. ✅ 安装模块（LSPosed、Zygisk 等）
15. ✅ 重启设备使模块生效
16. ✅ 完成！

### 📁 项目结构

```
android-auto-flash/
├── core/                       # 核心框架
│   ├── device_controller.py    # 设备控制器（ADB/Fastboot 封装）
│   ├── flash_orchestrator.py   # 刷机流程编排器
│   ├── state_machine.py        # 状态机
│   ├── boot_patcher.py         # Boot.img 修补器
│   ├── device_adapter.py       # 设备适配器基类
│   ├── root_adapter.py         # Root 方案适配器
│   ├── resource_manager.py     # 资源管理器
│   ├── config_manager.py       # 配置管理器
│   ├── checkpoint.py           # 检查点管理
│   ├── auto_recovery.py        # 自动恢复
│   ├── error_handler.py        # 错误处理
│   ├── ui_automation.py        # UI 自动化
│   ├── tool_installer.py       # 工具安装器
│   └── ...
├── resources/                  # 资源目录
│   ├── common/                 # 通用资源
│   │   ├── apks/               # APK 文件
│   │   ├── modules/            # 模块文件
│   │   └── tools/              # 修补工具
│   └── devices/                # 设备资源
│       └── redfin/             # Pixel 5
├── tests/                      # 测试文件
│   ├── test_flash.py
│   ├── test_boot_patch.py
│   └── ...
├── docs/                       # 文档
├── examples/                   # 示例代码
├── main.py                     # 主程序入口
├── config.yaml                 # 全局配置
├── requirements.txt            # Python 依赖
├── setup.py                    # 安装脚本
├── pyproject.toml              # 项目配置
└── README.md                   # 本文件
```

### 🔧 高级功能

#### 自动检查点恢复

- 刷机过程中每个状态自动保存检查点
- 中断后重新运行会自动询问是否恢复
- 检查点文件: `logs/checkpoint_{设备序列号}.json`

#### 并发刷机

- 选择 `A` 可以同时刷机所有连接的设备
- 每个设备独立线程，互不干扰
- 自动从各自的检查点恢复

#### 资源管理

工具自动管理通用资源和设备特定资源：

- **通用资源**：`resources/common/` - 所有设备共享
- **设备资源**：`resources/devices/{model}/` - 设备专用
- **优先级**：设备特定 > 通用

#### 自动恢复

刷入修补后的 boot.img 失败时，工具会自动：
1. 检测设备启动超时
2. 刷回原厂 boot.img
3. 验证设备恢复正常

#### Boot.img 修补

工具内置 Windows 平台的 boot.img 修补功能：
- 自动检测 KernelPatch 版本
- 支持嵌入 KPM 模块
- APatch 兼容的日志格式
- 自动处理 MSYS2 依赖

### 📚 文档

- [APatch 定制说明](docs/APATCH_CUSTOMIZATION.md)
- [代码质量报告](CODE_QUALITY_REPORT.md)

### ⚠️ 注意事项

1. **数据备份**：刷机会清空所有用户数据，请提前备份
2. **Bootloader 解锁**：刷机前必须解锁 Bootloader
3. **电量要求**：设备电量至少 30%
4. **USB 连接**：使用原装数据线，确保连接稳定
5. **风险提示**：刷机有变砖风险，请谨慎操作
6. **Root 方案**：当前仅支持 APatch，Magisk/KernelSU 正在开发中
7. **手动操作**：以下步骤需要手动完成：
   - ✋ **初始化向导**：系统首次启动后，需手动完成初始化向导（选择语言、WiFi 等）
   - ✋ **开发者模式**：需手动进入"设置 → 关于手机 → 连续点击版本号 7 次"开启开发者模式
   - ✋ **USB 调试**：需手动在"开发者选项"中开启"USB 调试"
   - ✋ **APatch 激活**：首次安装 APatch 后，需手动打开应用并授予权限
   - ✋ **模块安装**：如果自动安装失败，需手动在 APatch 管理器中安装模块

### 🛠️ 开发

#### 安装开发依赖

```bash
pip install -e ".[dev]"
```

#### 代码质量检查

```bash
# 格式化代码
black core/ tests/ *.py

# 检查代码风格
flake8 core/ tests/ *.py

# 类型检查
mypy core/

# 排序导入
isort core/ tests/ *.py
```

#### 运行测试

```bash
# 运行所有测试
pytest tests/

# 运行特定测试
pytest tests/test_device_controller.py

# 查看覆盖率
pytest --cov=core tests/
```

### 🤝 贡献

欢迎贡献代码、报告 Bug 或提出建议！

1. Fork 本项目
2. 创建特性分支 (`git checkout -b feature/AmazingFeature`)
3. 提交更改 (`git commit -m 'feat: Add some AmazingFeature'`)
4. 推送到分支 (`git push origin feature/AmazingFeature`)
5. 提交 Pull Request

### 📄 许可证

MIT License

---

## English

A universal Android auto-flashing framework that supports multiple device models, minimizes manual intervention, and enables one-click deployment from stock system to full Root environment.

### ✨ Key Features

- **Multi-Device Support**: Supports Pixel, Xiaomi, OPPO and more via device adapter pattern
- **Resource Sharing**: Common modules (APatch, LSPosed, etc.) shared across devices
- **Full Automation**: Auto-complete flashing, initialization, Root, and module installation
- **Resume Support**: Continue from checkpoint after interruption
- **Auto Recovery**: Automatically recover to stock boot.img on failure

### 📱 Supported Devices

**Initial Support**:
- Google Pixel 5 (redfin)

**Extensible**: Support more devices by writing device adapters

### 🔧 Root Method Support

| Root Method | Status | Notes |
|------------|--------|-------|
| **APatch** | ✅ Supported | Full support including boot.img patching and module installation |
| **Magisk** | 🚧 In Development | Planned |
| **KernelSU** | 🚧 In Development | Planned |

**Currently recommend using APatch**

### 🚀 Quick Start

#### 1. Installation

```bash
# Clone the project
git clone https://github.com/yourusername/android-auto-flash.git
cd android-auto-flash

# Install dependencies
pip install -r requirements.txt

# Or install in development mode
pip install -e .
```

#### 2. Prepare Resources

See Chinese section for resource structure.

#### 3. Configuration

Edit `config.yaml`:

```yaml
# Global config
adb_path: "adb"
fastboot_path: "fastboot"

# Root method (currently only apatch is supported)
root_method: "apatch"

# Device config
devices:
  redfin:
    model: "redfin"
    build_id: "TQ3A.230901.001.C2"
    superkey: "your_superkey_here"
    boot_img_source: "firmware"  # or "patched"
```

#### 4. Run Flashing

```bash
# Single device
python main.py flash --device redfin

# Boot-only (keep data)
python main.py flash --device redfin --boot-only

# Resume from checkpoint
python main.py flash --device redfin --resume

# Dry run (no actual operations)
python main.py flash --device redfin --dry-run
```

### 📄 License

MIT License

---

**Created with ❤️ for Android enthusiasts**
