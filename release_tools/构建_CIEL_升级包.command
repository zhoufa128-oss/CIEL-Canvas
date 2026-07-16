#!/bin/zsh
set -u

ROOT_DIR="$(cd "$(dirname "$0")/../../.." && /bin/pwd -P)"
TOOL="$ROOT_DIR/09_发行构建/04_发行工具/build_ciel_update.py"
APPLICATION="$ROOT_DIR/09_发行构建/01_完整发行包/CIEL_Canvas_1.0.0_macOS_arm64/CIEL Canvas/Application/current"
OUTPUT="$ROOT_DIR/09_发行构建/02_升级包"

print -r -- "本工具用于有新版本时构建离线升级 ZIP。"
print -r -- "请从终端明确传入新版本参数；不会为同版本 1.0.0 生成伪升级包。"
print -r -- "示例："
print -r -- "/usr/bin/python3 ${(q)TOOL} --application ${(q)APPLICATION} --from-min 1.0.0 --from-max 1.0.0 --to-version 1.0.1 --to-internal-build <已审核内部构建号> --output-dir ${(q)OUTPUT}"
