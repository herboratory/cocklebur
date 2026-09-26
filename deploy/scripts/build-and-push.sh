#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
ROOT_DIR="$(cd "${SCRIPT_DIR}/../.." && pwd)"

# -----------------------------------------------------------------------------
# 0. 載入集中式設定檔 (deploy/deploy.env)
# -----------------------------------------------------------------------------
DEPLOY_ENV_FILE="${ROOT_DIR}/deploy/deploy.env"
if [[ -f "$DEPLOY_ENV_FILE" ]]; then
  set -a
  # shellcheck disable=SC1090
  source "$DEPLOY_ENV_FILE"
  set +a
fi

ENV="${1:-eng}"
TAG="${2:-latest}"

CURRENT_DOCKER_CTX="$(docker context show 2>/dev/null || echo "default")"

case "$ENV" in
  eng)
    DEFAULT_DOCKER_CTX="${ENG_DOCKER_CONTEXT:-}"
    DEFAULT_REGISTRY="${ENG_REGISTRY:-registry.example.com/team}"
    ;;
  uat)
    DEFAULT_DOCKER_CTX="${UAT_DOCKER_CONTEXT:-}"
    DEFAULT_REGISTRY="${UAT_REGISTRY:-registry.example.com/team}"
    ;;
  stg)
    DEFAULT_DOCKER_CTX="${STG_DOCKER_CONTEXT:-}"
    DEFAULT_REGISTRY="${STG_REGISTRY:-registry.example.com/prod}"
    ;;
  prod)
    DEFAULT_DOCKER_CTX="${PROD_DOCKER_CONTEXT:-}"
    DEFAULT_REGISTRY="${PROD_REGISTRY:-registry.example.com/prod}"
    ;;
  *)
    echo "錯誤: 未知環境 '$ENV'。可用環境: eng | uat | stg | prod"
    exit 1
    ;;
esac

# 優先順序: 命令列環境變數 -> deploy.env 設定 -> 目前 Docker Context
DOCKER_CTX="${DOCKER_CTX:-$DEFAULT_DOCKER_CTX}"
if [[ -z "$DOCKER_CTX" ]]; then
  DOCKER_CTX="$CURRENT_DOCKER_CTX"
fi

REGISTRY="${REGISTRY:-$DEFAULT_REGISTRY}"
IMAGE_NAME="${REGISTRY}/cocklebur-server:${TAG}"

echo "=========================================================="
echo "Cocklebur 映像檔建置與推送 (參數化管理)"
echo "環境:           $ENV"
echo "Docker Context: $DOCKER_CTX"
echo "目標 Registry:  $REGISTRY"
echo "完整映像檔名稱: $IMAGE_NAME"
echo "=========================================================="

# 檢查 Docker context (僅在與目前不同時切換)
if [[ "$DOCKER_CTX" != "$CURRENT_DOCKER_CTX" ]]; then
  if docker context ls --format '{{.Name}}' | grep -q "^${DOCKER_CTX}$"; then
    echo "切換 Docker context 至 ${DOCKER_CTX}..."
    docker context use "$DOCKER_CTX"
  else
    echo "提示: Docker context '$DOCKER_CTX' 不存在，維持目前 Docker context (${CURRENT_DOCKER_CTX})。"
    DOCKER_CTX="$CURRENT_DOCKER_CTX"
  fi
else
  echo "使用目前 Docker context: ${DOCKER_CTX}"
fi

echo "建置映像檔..."
docker build -t "$IMAGE_NAME" -f "${ROOT_DIR}/Dockerfile" "$ROOT_DIR"

echo "推送映像檔至 ${REGISTRY}..."
docker push "$IMAGE_NAME"

if [[ "$TAG" != "latest" ]]; then
  LATEST_IMAGE="${REGISTRY}/cocklebur-server:latest"
  echo "同步標記並推送 latest 標籤至 ${LATEST_IMAGE}..."
  docker tag "$IMAGE_NAME" "$LATEST_IMAGE"
  docker push "$LATEST_IMAGE"
fi

echo "=========================================================="
echo "映像檔推送完成: $IMAGE_NAME"
echo "=========================================================="
