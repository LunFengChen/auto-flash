# Android 全自动刷机工具

一个 Android 自动刷机简易框架，支持多设备并发刷机、断点续传、自动恢复。

> 为了解决繁琐重复的刷机过程而写，适用于群控刷机和批量改机。
> 
> 只适配了 Windows，其他平台自己配置环境变量或者修改源码。
> 
> 证书嵌入模块参考：https://github.com/LunFengChen/MoveCertificate


## yamls 配置目录

刷机配置统一放在 `yamls/` 下，按设备/用途拆分配置文件：

| 文件 | 用途 |
| --- | --- |
| `yamls/pixel5.yaml` | Pixel 5 (redfin) APatch 刷机配置（含 reqable、appproxy、快手、xj-server-v3、带 Reqable 证书的 MoveCertificate 模块） |
| `yamls/apatch.yaml` | APatch 本地 fork 同步/构建参数（拉 gh 新版 + 合并上游 bmax121/APatch） |

使用 yamls 配置运行：

```bash
# 刷机
python main.py --config-dir yamls --config pixel5.yaml

# 只安装 APK / 二进制 / 模块
python -m core.tool_installer_cli --config-dir yamls --config pixel5.yaml
python -m core.tool_installer_cli --apk-only --config-dir yamls --config pixel5.yaml
python -m core.tool_installer_cli --binary-only --config-dir yamls --config pixel5.yaml
python -m core.tool_installer_cli --module-only --config-dir yamls --config pixel5.yaml
```

同步 APatch fork 并合并上游（APatch APK 来自本地仓库 `/home/xiaofeng/Desktop/projects/apatch`）：

```bash
bash scripts/sync-apatch.sh          # 拉 origin + 合并 upstream/main
bash scripts/sync-apatch.sh --push   # 合并后 push 到 GitHub
bash scripts/sync-apatch.sh --copy   # 复制 APatch 仓库已有 APK 到 resources/common/root/
bash scripts/sync-apatch.sh --build  # 重新编译并复制 APatch APK 到 resources/common/root/
```

同步桌面 reverse 里的工具/APK/模块资源：

```bash
bash scripts/sync-reverse-resources.sh
```

当前映射：`reverse/tools/app-arm64-v8a-release.apk` -> `resources/common/apks/appproxy.apk`，
`reverse/devices/auto-flash/resources/common/...` -> reqable、xj-server-v3、带 Reqable 证书的 MoveCertificate 模块和刷机工具。

不传参数时保持旧行为，默认读取根目录 `config.yaml`。

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
- 可根据真实刷机流程扩展其他设备

## 快速开始

### 1. 安装

```bash
git clone https://github.com/LunFengChen/auto-flash.git
cd auto-flash
pip install -r requirements.txt
```

### 2. 准备资源
照着我下面的这个目录结构准备就行，具体内容仅供参考；
```bash
resources/
├── common/
│   ├── apks/
│   │   ├── reqable-app-android-arm64.apk
│   │   ├── clashmi_1.0.11.150_android_arm64-v8a.apk
│   │   ├── frida环境检测.apk
│   │   └── 环境检测-by小枫.apk
│   ├── binary/
│   │   ├── r0gson.dex
│   │   ├── r16
│   │   ├── SoFixer-Linux-32
│   │   ├── SoFixer-Linux-64
│   │   └── xj3
│   ├── root/
│   │   ├── APatch_11182_d52e119_main-debug.apk
│   │   ├── KitsuneMagisk-v27.2-kitsune-2.apk
│   │   └── KitsuneMagisk-v30.6.apk
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
                └── apatch_patched_TQ3A.230901.001.C2_0.12.7.img(如果没有的话就是会自动修补)
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
8. ✅ 重启设备
9. ✋ **手动打开 APatch 触发授权**（激活 root 环境，如果是我自己编译的 apatch 可以跳过这一步，具体可看 https://github.com/LunFengChen/Apatch 的 actions 编译流程）
10. ✅ 安装 APK 和模块
11. ✅ 重启生效

## 其他注意事项

- 刷机会清空数据，提前备份
- 必须解锁 Bootloader
- 电量至少 30%
- 使用原装数据线
- 有变砖风险

## 许可证

MIT License
