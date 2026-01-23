# Android 全自动刷机工具

一个 Android 自动刷机框架，支持多设备并发刷机、断点续传、自动恢复。

> 为了解决繁琐重复的刷机过程而写，适用于群控刷机和批量改机。
> 
> 只适配了 Windows，其他平台自己配置环境变量。
> 
> 证书嵌入模块参考：https://github.com/LunFengChen/MoveCertificate

## 功能

**已实现** ✅
- 自动刷机（系统、boot.img、APK、模块）
- 多设备并发刷机
- 断点续传
- 自动恢复（刷机失败自动恢复原厂 boot）
- Boot.img 修补（KernelPatch，Windows）
- 自动获取设备型号

**未实现** ⚠️
- UI 自动化（初始化向导、开发者模式需手动）
- Magisk/KernelSU 支持

## 支持设备

- Google Pixel 5 (redfin)
- 可扩展其他设备

## Root 方案

| 方案 | 状态 |
|------|------|
| APatch | ✅ 已支持 |
| Magisk | 🚧 开发中 |
| KernelSU | 🚧 开发中 |

## 快速开始

### 1. 安装

```bash
git clone https://github.com/yourusername/android-auto-flash.git
cd android-auto-flash
pip install -r requirements.txt
```

### 2. 准备资源

```bash
resources/
├── common/
│   ├── apks/
│   │   ├── APatch_11182_d52e119_main-debug.apk
│   │   ├── reqable-app-android-arm64.apk
│   │   ├── clashmi_1.0.11.150_android_arm64-v8a.apk
│   │   ├── frida环境检测.apk
│   │   └── 环境检测-by小枫.apk
│   ├── modules/
│   │   ├── zip/
│   │   │   ├── LSPosed-v1.9.2-7058-zygisk-release.zip
│   │   │   ├── ZygiskNext-1.2.9.1-534-b8e7e21-release.zip
│   │   │   ├── MoveCertificate-v1.0.1-6f37b04-withCert-e4fb11ae-3d521386-243f0bfb.zip
│   │   │   └── zygisk-gadget-xiaojia.zip
│   │   ├── lsp/
│   │   │   ├── BlackDex64.apk
│   │   │   ├── HideMyApp-V3.6.1.r462.4524dde-release.apk
│   │   │   ├── 我不是开发者_1.6.1.apk
│   │   │   ├── 截屏录屏绕过.apk
│   │   │   └── 算法助手Pro_1.0.9.apk
│   │   ├── zygisk/
│   │   │   └── 小佳gadget小工具.apk
│   │   └── kpm/
│   └── tools/
│       ├── kptools-msys2-0.12.7.exe
│       ├── kpimg-android-0.12.7
│       ├── magiskboot.exe
│       ├── msys-2.0.dll
│       └── msys-z.dll
└── devices/
    └── redfin/
        └── TQ3A.230901.001.C2/
            ├── firmware/
            │   ├── boot.img
            │   ├── bootloader-redfin-r3-0.5-9825705.img
            │   ├── radio-redfin-g7250-00258-230518-b-10157620.img
            │   └── image-redfin-tq3a.230901.001.c2.zip
            └── root/
                └── apatch_patched_TQ3A.230901.001.C2_0.12.7.img
```

### 3. 配置

编辑 `config.yaml`：

```yaml
adb_path: "adb"
fastboot_path: "fastboot"
root_method: "apatch"

devices:
  redfin:
    model: "redfin"
    build_id: "TQ3A.230901.001.C2"
    superkey: "your_superkey_here"
    boot_img_source: "firmware"
```

### 4. 运行

```bash
python main.py
```

交互式菜单：
- `1/2` - 刷机单个设备
- `A` - 并发刷机所有设备
- `C` - 清除检查点并重新刷机
- `Q` - 退出

## 刷机流程

1. ✅ 自动检测设备
2. ✅ 刷入系统
3. ✋ **手动完成初始化向导**
4. ✋ **手动开启开发者模式**（设置 → 关于手机 → 点版本号 7 次）
5. ✋ **手动开启 USB 调试**
6. ✅ 安装 APatch
7. ✅ 修补并刷入 boot.img
8. ✅ 安装 APK 和模块
9. ✋ **手动打开 APatch 授予权限**
10. ✅ 重启生效

## 注意事项

- 刷机会清空数据，提前备份
- 必须解锁 Bootloader
- 电量至少 30%
- 使用原装数据线
- 有变砖风险

## 许可证

MIT License
