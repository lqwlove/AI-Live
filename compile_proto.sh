#!/bin/bash
# 编译 protobuf 定义文件为 Python 模块
# 使用前请确保已安装 protoc: brew install protobuf

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
PROTO_DIR="$SCRIPT_DIR/proto"

echo "正在编译 protobuf 文件..."

protoc \
    --python_out="$PROTO_DIR" \
    --proto_path="$PROTO_DIR" \
    "$PROTO_DIR/douyin.proto"

if [ $? -eq 0 ]; then
    # 创建 __init__.py 使 proto 目录成为 Python 包
    touch "$PROTO_DIR/__init__.py"
    echo "编译成功！生成文件: $PROTO_DIR/douyin_pb2.py"
else
    echo "编译失败，请检查 protoc 是否已安装: brew install protobuf"
    exit 1
fi
