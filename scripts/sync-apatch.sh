#!/usr/bin/env bash
# 同步 APatch 本地 fork：拉取 gh 新版 + 合并上游 bmax121/APatch
# 用法: bash scripts/sync-apatch.sh [--build] [--copy] [--push]
#   --build  合并后重新编译 APK
#   --copy   复制 APatch 本地构建产物到 auto-flash/resources/common/root/
#   --push   合并完成后 push 到自己的 GitHub fork
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
AUTO_FLASH_ROOT="$(cd "$SCRIPT_DIR/.." && pwd)"
REPO="${APATCH_REPO:-/home/xiaofeng/Desktop/projects/apatch}"
BRANCH="${APATCH_BRANCH:-feature/rom-root-grants}"
UPSTREAM_BRANCH="main"
COMMIT_MSG="${APATCH_COMMIT_MSG:-merge: 合并上游 bmax121/APatch main}"

DO_PUSH=false
DO_BUILD=false
DO_COPY=false
for arg in "$@"; do
  case "$arg" in
    --push) DO_PUSH=true ;;
    --build) DO_BUILD=true; DO_COPY=true ;;
    --copy) DO_COPY=true ;;
  esac
done

copy_apk() {
  echo "==> 复制 APatch 仓库构建产物到 auto-flash 资源目录"
  APK=$(find app/build/outputs/apk -type f -name '*debug.apk' -print | sort | tail -n 1)
  if [ -z "$APK" ]; then
    echo "!! 没找到 APatch debug APK，请先加 --build" >&2
    exit 1
  fi
  DEST="$AUTO_FLASH_ROOT/resources/common/root"
  mkdir -p "$DEST"
  APK_DIR="$(basename "$(dirname "$APK")")"
  APK_NAME="$(basename "$APK")"
  DEST_NAME="${APK_DIR}-${APK_NAME}"
  cp -v "$APK" "$DEST/$DEST_NAME"
  echo "==> APK path: resources/common/root/$DEST_NAME"
}

cd "$REPO"

# 只复制本地 APatch 构建产物时，不做网络同步。
if [ "$DO_COPY" = true ] && [ "$DO_BUILD" = false ] && [ "$DO_PUSH" = false ]; then
  copy_apk
  echo "==> 完成: $(git log --oneline -1)"
  exit 0
fi

echo "==> 确保在分支 $BRANCH 且工作区干净"
if ! git rev-parse --verify -q "$BRANCH" >/dev/null; then
  echo "本地分支 $BRANCH 不存在，先 checkout 到现有分支"
  git checkout -b "$BRANCH" origin/"$BRANCH" 2>/dev/null || git checkout "$BRANCH"
fi
git checkout "$BRANCH"
if [ -n "$(git status --porcelain)" ]; then
  echo "!! 工作区有未提交改动，先提交或 stash 后再同步" >&2
  git status --short
  exit 1
fi

echo "==> fetch origin（自己的 GitHub 新版）"
git fetch origin --prune

echo "==> fetch upstream（bmax121/APatch）"
git fetch upstream --prune

echo "==> 合并 upstream/$UPSTREAM_BRANCH"
if git merge --no-edit upstream/"$UPSTREAM_BRANCH" -m "$COMMIT_MSG"; then
  echo "==> 合并完成，无冲突"
else
  echo "!! 存在冲突，请手动解决后: git add -A && git commit"
  echo "   常见冲突处理参考 yamls/apatch.yaml 注释"
  exit 1
fi

if [ "$DO_PUSH" = true ]; then
  echo "==> push 到 origin/$BRANCH"
  git push origin "$BRANCH"
fi

if [ "$DO_BUILD" = true ]; then
  echo "==> 编译 APK（DEFAULT_SUPERKEY=xiaofeng777, AUTO_INSTALL_APATCH=true）"
  ./gradlew :app:assembleDebug \
    -PDEFAULT_SUPERKEY=xiaofeng777 \
    -PAUTO_INSTALL_APATCH=true \
    -x downloadJailbreakKo
fi

if [ "$DO_COPY" = true ]; then
  copy_apk
fi

echo "==> 完成: $(git log --oneline -1)"
