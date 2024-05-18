#!/bin/bash

# 停止脚本在遇到错误时继续执行
set -e

# 构建Docker镜像
echo "Building the Docker image..."
docker build --platform linux/amd64 -t popai2api .

# 标记Docker镜像
echo "Tagging the Docker image..."
docker tag popai2api hulu365/popai2api:latest

# 推送Docker镜像到Docker Hub
echo "Pushing the Docker image to Docker Hub..."
docker push hulu365/popai2api:latest

echo "Docker build and push completed successfully."