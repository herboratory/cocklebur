#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
ROOT_DIR="$(cd "${SCRIPT_DIR}/../.." && pwd)"
DEPLOY_DIR="${ROOT_DIR}/deploy"

# -----------------------------------------------------------------------------
# 0. 載入統一部署設定檔 (deploy/deploy.env)
# -----------------------------------------------------------------------------
DEPLOY_ENV_FILE="${DEPLOY_DIR}/deploy.env"
if [[ -f "$DEPLOY_ENV_FILE" ]]; then
  set -a
  # shellcheck disable=SC1090
  source "$DEPLOY_ENV_FILE"
  set +a
fi

# 解析參數
ENV="eng"
DO_BUILD="${AUTO_BUILD_IMAGE:-false}"

for arg in "$@"; do
  case "$arg" in
    eng|uat|stg|prod)
      ENV="$arg"
      ;;
    --build|-b|build)
      DO_BUILD="true"
      ;;
    --no-build|no-build)
      DO_BUILD="false"
      ;;
    -h|--help)
      echo "用法: $0 [eng|uat|stg|prod] [--build|--no-build]"
      echo ""
      echo "參數說明:"
      echo "  [環境]        eng | uat | stg | prod (預設: eng)"
      echo "  [--build]     部署前先執行獨立建置腳本 build-and-push.sh"
      echo "  [--no-build]  跳過映像檔建置 (預設)"
      echo ""
      echo "支援環境變數覆蓋:"
      echo "  DOCKER_CONTEXT / DOCKER_CTX : 指定 Docker Context"
      echo "  PORT / HOST_PORT            : 指定本機映射端口"
      echo "  DOMAIN                      : 指定網域名稱"
      exit 0
      ;;
  esac
done

ENV_UPPER="$(echo "$ENV" | tr '[:lower:]' '[:upper:]')"

# 讀取環境專屬變數
VAR_CTX="${ENV_UPPER}_DOCKER_CONTEXT"
VAR_PORT="${ENV_UPPER}_DOCKER_PORT"
VAR_REG="${ENV_UPPER}_REGISTRY"
VAR_TAG="${ENV_UPPER}_IMAGE_TAG"
VAR_DOM="${ENV_UPPER}_DEFAULT_DOMAIN"

TARGET_DOCKER_CTX="${!VAR_CTX:-default}"
TARGET_PORT="${!VAR_PORT:-8000}"
TARGET_REGISTRY="${!VAR_REG:-registry.example.com}"
TARGET_IMAGE_TAG="${!VAR_TAG:-latest}"
DEFAULT_DOMAIN="${!VAR_DOM:-localhost}"

DOCKER_CTX="${DOCKER_CONTEXT:-${DOCKER_CTX:-$TARGET_DOCKER_CTX}}"
HOST_PORT="${PORT:-${HOST_PORT:-$TARGET_PORT}}"
IMAGE_NAME="${TARGET_REGISTRY}/cocklebur-server:${TARGET_IMAGE_TAG}"
CONTAINER_NAME="cocklebur-server-${ENV}"
VOLUME_NAME="cocklebur_data_${ENV}"

# -----------------------------------------------------------------------------
# 1. 尋找並重用 .env 變數 (優先順序: overlays/<env>/.env -> 專案根目錄 .env)
# -----------------------------------------------------------------------------
ENV_FILE=""
if [[ -f "${DEPLOY_DIR}/k8s/overlays/${ENV}/.env" ]]; then
  ENV_FILE="${DEPLOY_DIR}/k8s/overlays/${ENV}/.env"
elif [[ -f "${ROOT_DIR}/.env" ]]; then
  ENV_FILE="${ROOT_DIR}/.env"
fi

POPUP_BASE_URL=""
COCKLEBUR_BOOTSTRAP_KEY=""
POPUP_SECRET_KEY=""

if [[ -n "$ENV_FILE" ]]; then
  echo ">>> 偵測到應用程式環境檔: ${ENV_FILE}"
  while IFS='=' read -r key val || [[ -n "$key" ]]; do
    key="$(echo "$key" | tr -d ' \t\r')"
    [[ -z "$key" || "$key" =~ ^# ]] && continue
    val="$(echo "$val" | sed -e 's/^[[:space:]]*//' -e 's/[[:space:]\r]*$//')"
    if [[ "$val" =~ ^\"(.*)\"$ ]] || [[ "$val" =~ ^\'(.*)\'$ ]]; then
      val="${BASH_REMATCH[1]}"
    fi

    case "$key" in
      POPUP_BASE_URL) POPUP_BASE_URL="$val" ;;
      COCKLEBUR_BOOTSTRAP_KEY|COCKLEBUR_HOST_KEY)
        [[ -z "$COCKLEBUR_BOOTSTRAP_KEY" ]] && COCKLEBUR_BOOTSTRAP_KEY="$val"
        ;;
      POPUP_SECRET_KEY) POPUP_SECRET_KEY="$val" ;;
    esac
  done < "$ENV_FILE"
fi

# 萃取網域
PARSED_DOMAIN=""
if [[ -n "$POPUP_BASE_URL" ]]; then
  PARSED_DOMAIN="$(python3 -c "import urllib.parse, sys; u=sys.argv[1]; p=urllib.parse.urlparse(u if '://' in u else 'https://'+u); print(p.hostname or '')" "$POPUP_BASE_URL")"
fi
DOMAIN="${DOMAIN:-${PARSED_DOMAIN:-$DEFAULT_DOMAIN}}"
if [[ -z "$POPUP_BASE_URL" ]]; then
  POPUP_BASE_URL="http://${DOMAIN}:${HOST_PORT}"
fi

# 補齊金鑰
if [[ -z "$COCKLEBUR_BOOTSTRAP_KEY" ]]; then
  COCKLEBUR_BOOTSTRAP_KEY="$(python3 -c 'import secrets; print(secrets.token_urlsafe(32))')"
fi
if [[ -z "$POPUP_SECRET_KEY" ]]; then
  POPUP_SECRET_KEY="$(python3 -c 'import secrets; print(secrets.token_urlsafe(32))')"
fi

echo "=========================================================="
echo "Cocklebur Server Docker 部署程序 (參數化管理)"
echo "環境:               $ENV"
echo "Docker Context:     $DOCKER_CTX"
echo "容器名稱:           $CONTAINER_NAME"
echo "資料卷名稱:         $VOLUME_NAME"
echo "映射端口:           $HOST_PORT -> 8000"
echo "映像檔:             $IMAGE_NAME"
echo "執行映像檔建置:     $DO_BUILD"
echo "基礎 URL:           $POPUP_BASE_URL"
echo "=========================================================="

# -----------------------------------------------------------------------------
# 2. 獨立映像檔建置步驟 (若觸發 --build)
# -----------------------------------------------------------------------------
if [[ "$DO_BUILD" == "true" ]]; then
  echo ">>> [前置作業] 觸發映像檔建置與推送 (build-and-push.sh)..."
  "${SCRIPT_DIR}/build-and-push.sh" "$ENV" "$TARGET_IMAGE_TAG"
  echo ">>> 映像檔就緒，繼續執行 Docker 部署..."
fi

# -----------------------------------------------------------------------------
# 3. 驗證 Docker Context
# -----------------------------------------------------------------------------
DOCKER_CMD=(docker)
if [[ -n "$DOCKER_CTX" && "$DOCKER_CTX" != "default" ]]; then
  if docker context ls --format '{{.Name}}' | grep -q "^${DOCKER_CTX}$"; then
    DOCKER_CMD=(docker --context "$DOCKER_CTX")
  else
    echo "警告: Docker context '$DOCKER_CTX' 不存在，使用本機預設 context。"
  fi
fi

# 測試連線
echo "測試 Docker 伺服器通訊..."
"${DOCKER_CMD[@]}" info > /dev/null

# -----------------------------------------------------------------------------
# 4. 執行 Docker Compose 部署
# -----------------------------------------------------------------------------
COMPOSE_FILE="${DEPLOY_DIR}/docker/docker-compose.yml"
if [[ ! -f "$COMPOSE_FILE" ]]; then
  echo "錯誤: 找不到 $COMPOSE_FILE"
  exit 1
fi

export IMAGE_NAME
export CONTAINER_NAME
export VOLUME_NAME
export HOST_PORT
export POPUP_BASE_URL
export COCKLEBUR_BOOTSTRAP_KEY
export POPUP_SECRET_KEY
export POPUP_MAX_UPLOAD_MB="${POPUP_MAX_UPLOAD_MB:-50}"
export POPUP_IMPORT_MAX_MB="${POPUP_IMPORT_MAX_MB:-2048}"
export POPUP_PROJECT_QUOTA_MB="${POPUP_PROJECT_QUOTA_MB:-1024}"

echo "拉取/更新映像檔並啟動容器..."
"${DOCKER_CMD[@]}" compose -f "$COMPOSE_FILE" -p "cocklebur-${ENV}" up -d --remove-orphans

# -----------------------------------------------------------------------------
# 5. 檢查容器執行狀態
# -----------------------------------------------------------------------------
echo "等待容器就緒..."
sleep 3

echo "=========================================================="
echo "Docker 部署完成！狀態摘要："
echo "=========================================================="
"${DOCKER_CMD[@]}" ps -f "name=${CONTAINER_NAME}"
echo "----------------------------------------------------------"
echo "連線位址:     ${POPUP_BASE_URL}"
echo "Host 端口:    ${HOST_PORT}"
echo "Bootstrap Key: ${COCKLEBUR_BOOTSTRAP_KEY}"
echo "（首次連線請進入網頁點擊 Claim Host，並輸入上述 Bootstrap Key）"
echo "=========================================================="
