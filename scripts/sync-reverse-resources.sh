#!/usr/bin/env bash
# 从桌面 reverse 资源库同步 auto-flash 需要的本地资源。
# APatch APK 优先取 /home/xiaofeng/Desktop/projects/apatch 的本地构建产物，
# 其他工具/APK/模块直接从 /home/xiaofeng/Desktop/reverse 拿。
# 用法: bash scripts/sync-reverse-resources.sh
set -euo pipefail

PROJECT_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
REVERSE_ROOT="${REVERSE_ROOT:-/home/xiaofeng/Desktop/reverse}"
REVERSE_AUTO_FLASH="${REVERSE_AUTO_FLASH:-$REVERSE_ROOT/devices/auto-flash}"
APATCH_REPO="${APATCH_REPO:-/home/xiaofeng/Desktop/projects/apatch}"

copy_file() {
  local src="$1"
  local dst="$2"
  if [ ! -f "$src" ]; then
    echo "!! 源文件不存在: $src" >&2
    return 1
  fi
  mkdir -p "$(dirname "$dst")"
  cp -f "$src" "$dst"
  chmod --reference="$src" "$dst" 2>/dev/null || true
  echo "copied: $src -> $dst"
}

latest_apatch_apk() {
  find "$APATCH_REPO/app/build/outputs/apk" -type f -name '*debug.apk' -print 2>/dev/null \
    | sort \
    | tail -n 1
}

APATCH_APK="${APATCH_APK:-$(latest_apatch_apk)}"
if [ -n "$APATCH_APK" ] && [ -f "$APATCH_APK" ]; then
  APATCH_APK_NAME="$(basename "$APATCH_APK")"
  copy_file "$APATCH_APK" "$PROJECT_ROOT/resources/common/root/$APATCH_APK_NAME"
else
  copy_file "$REVERSE_AUTO_FLASH/resources/common/root/APatch_11220_39ba3bb_feature-rom-root-grants-debug.apk" \
    "$PROJECT_ROOT/resources/common/root/APatch_11220_39ba3bb_feature-rom-root-grants-debug.apk"
fi

copy_file "$REVERSE_AUTO_FLASH/resources/common/apks/reqable-app-android-arm64.apk" \
  "$PROJECT_ROOT/resources/common/apks/reqable-app-android-arm64.apk"

# appproxy 在 reverse/tools 里叫 app-arm64-v8a-release.apk，包名 cn.ys1231.appproxy。
copy_file "$REVERSE_ROOT/tools/app-arm64-v8a-release.apk" \
  "$PROJECT_ROOT/resources/common/apks/appproxy.apk"

copy_file "${KUAISHOU_APK:-/home/xiaofeng/Downloads/快手.apk}" \
  "$PROJECT_ROOT/resources/common/apks/快手.apk"
copy_file "${KUAISHOU_EXPRESS_APK:-/home/xiaofeng/Desktop/work/ds-rhino-ks-api/_local/apks/快手极速版-14.7.20.11779-11779-20260817.apk}" \
  "$PROJECT_ROOT/resources/common/apks/快手极速版-14.7.20.11779-11779-20260817.apk"

copy_file "$REVERSE_AUTO_FLASH/resources/common/binary/xj-server-v3" \
  "$PROJECT_ROOT/resources/common/binary/xj-server-v3"

copy_file "$REVERSE_AUTO_FLASH/resources/common/modules/zip/MoveCertificate-v1.0.1-withReqable-d8e119df.zip" \
  "$PROJECT_ROOT/resources/common/modules/zip/MoveCertificate-v1.0.1-withReqable-d8e119df.zip"

# 刷 boot 的本机工具也从 reverse 的 auto-flash 资源同步。
for name in magiskboot magiskboot.exe kptools-linux kptools-msys2-0.12.7.exe kpimg-android-0.13.2 kpimg-linux-0.13.2; do
  if [ -f "$REVERSE_AUTO_FLASH/resources/common/tools/$name" ]; then
    copy_file "$REVERSE_AUTO_FLASH/resources/common/tools/$name" "$PROJECT_ROOT/resources/common/tools/$name"
  fi
done

# Linux 侧 BootPatcher 期望 binary/magiskboot、binary/kptools、binary/kpimg 这几个短名。
if [ -f "$PROJECT_ROOT/resources/common/tools/magiskboot" ]; then
  copy_file "$PROJECT_ROOT/resources/common/tools/magiskboot" "$PROJECT_ROOT/resources/common/binary/magiskboot"
fi
if [ -f "$PROJECT_ROOT/resources/common/tools/kptools-linux" ]; then
  copy_file "$PROJECT_ROOT/resources/common/tools/kptools-linux" "$PROJECT_ROOT/resources/common/binary/kptools"
fi
if [ -f "$PROJECT_ROOT/resources/common/tools/kpimg-linux-0.13.2" ]; then
  copy_file "$PROJECT_ROOT/resources/common/tools/kpimg-linux-0.13.2" "$PROJECT_ROOT/resources/common/binary/kpimg"
fi

cat <<EOF
==> 完成
APatch 仓库: $APATCH_REPO
reverse 资源: $REVERSE_ROOT
配置入口: python main.py --config-dir yamls --config pixel5-ks.yaml
EOF
