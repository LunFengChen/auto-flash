#!/usr/bin/env bash
# 同步 APatch 本地 fork：拉取 gh 新版 + 合并上游 bmax121/APatch
# 用法: bash scripts/sync-apatch.sh [--build] [--push]
#   --build  合并后重新编译 APK 并复制到 resources/common/root/
#   --push   合并完成后 push 到自己的 GitHub fork
set -euo pipefail

REPO="${APATCH_REPO:-/home/xiaofeng/Desktop/projects/apatch}"
BRANCH="${APATCH_BRANCH:-feature/rom-root-grants}"
UPSTREAM_BRANCH="main"
COMMIT_MSG="${APATCH_COMMIT_MSG:-merge: 合并上游 bmax121/APatch main}"

cd "$REPO"

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

if [ "${1:-}" = "--push" ] || [ "${2:-}" = "--push" ]; then
  echo "==> push 到 origin/$BRANCH"
  git push origin "$BRANCH"
fi

if [ "${1:-}" = "--build" ] || [ "${2:-}" = "--build" ]; then
  echo "==> 编译 APK（DEFAULT_SUPERKEY=xiaofeng777, AUTO_INSTALL_APATCH=true）"
  ./gradlew :app:assembleDebug :app:assembleRelease \
    -PDEFAULT_SUPERKEY=xiaofeng777 \
    -PAUTO_INSTALL_APATCH=true
  COMMIT=$(git rev-parse --short HEAD)
  VERSION=$(git describe --always --tags 2>/dev/null || echo "$COMMIT")
  DEST="$(cd "$(dirname "$0")/.." && pwd)/resources/common/root"
  mkdir -p "$DEST"
  cp -v app/build/outputs/apk/debug/app-debug.apk \
    "$DEST/APatch_${VERSION}_${COMMIT}_feature-rom-root-grants-debug.apk"
  echo "==> 记得更新 yamls/pixel5.yaml 的 root.apatch.apk_path 为新的文件名"
fi

echo "==> 完成: $(git log --oneline -1)"
