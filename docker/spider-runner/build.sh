#!/bin/bash
# CrawloPilot Spider Runner 镜像构建脚本

set -e

echo "========================================="
echo "  CrawloPilot Spider Runner 镜像构建"
echo "========================================="

# 配置
IMAGE_NAME="crawlopilot/spider-runner"
IMAGE_TAG="${1:-latest}"
PROJECT_ROOT="$(cd "$(dirname "$0")/../.." && pwd)"

echo ""
echo "镜像名称: $IMAGE_NAME"
echo "镜像标签: $IMAGE_TAG"
echo "项目根目录: $PROJECT_ROOT"
echo ""

# 构建镜像
echo "[1/2] 构建 Docker 镜像..."

docker build \
    -t "${IMAGE_NAME}:${IMAGE_TAG}" \
    -f "$PROJECT_ROOT/docker/spider-runner/Dockerfile" \
    "$PROJECT_ROOT"

echo ""
echo "[2/2] 验证镜像..."

# 验证镜像
if docker image inspect "${IMAGE_NAME}:${IMAGE_TAG}" > /dev/null 2>&1; then
    echo "✓ 镜像构建成功"
    echo ""
    echo "镜像信息:"
    docker images "${IMAGE_NAME}:${IMAGE_TAG}"
    echo ""
    
    # 显示镜像大小
    IMAGE_SIZE=$(docker images "${IMAGE_NAME}:${IMAGE_TAG}" --format "{{.Size}}")
    echo "镜像大小: $IMAGE_SIZE"
    echo ""
    
    echo "========================================="
    echo "✓ 构建完成!"
    echo "========================================="
    echo ""
    echo "使用示例:"
    echo ""
    echo "docker run -it --rm \\"
    echo "  -e API_URL=http://localhost:8000 \\"
    echo "  -e API_TOKEN=your_token \\"
    echo "  -e TASK_ID=task_123 \\"
    echo "  -e SPIDER_NAME=my_spider \\"
    echo "  -e GIT_URL=https://github.com/xxx/spider.git \\"
    echo "  -v \$(pwd)/output:/output \\"
    echo "  ${IMAGE_NAME}:${IMAGE_TAG}"
    echo ""
else
    echo "❌ 镜像构建失败"
    exit 1
fi
