#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
ROOT_DIR="$(cd "${SCRIPT_DIR}/../.." && pwd)"

# -----------------------------------------------------------------------------
# 0. 載入統一部署設定檔 (deploy/deploy.env) 並自動同步 K8s 與 Helm
# -----------------------------------------------------------------------------
DEPLOY_ENV_FILE="${ROOT_DIR}/deploy/deploy.env"
if [[ -f "$DEPLOY_ENV_FILE" ]]; then
  set -a
  # shellcheck disable=SC1090
  source "$DEPLOY_ENV_FILE"
  set +a
fi


# 解析命令列參數 (支援靈活順序與 --build 參數)
ENV="eng"
TOOL="${DEFAULT_TOOL:-kustomize}"
DO_BUILD="${AUTO_BUILD_IMAGE:-false}"

for arg in "$@"; do
  case "$arg" in
    eng|uat|stg|prod)
      ENV="$arg"
      ;;
    helm|--helm)
      TOOL="helm"
      ;;
    kustomize|--kustomize)
      TOOL="kustomize"
      ;;
    docker|--docker)
      TOOL="docker"
      ;;
    --build|-b|build)
      DO_BUILD="true"
      ;;
    --no-build|no-build)
      DO_BUILD="false"
      ;;
    -h|--help)
      echo "用法: $0 [eng|uat|stg|prod] [kustomize|helm|docker] [--build|--no-build]"
      echo ""
      echo "參數說明:"
      echo "  [環境]        eng | uat | stg | prod (預設: eng)"
      echo "  [工具]        kustomize | helm | docker (預設: kustomize)"
      echo "  [--build]     部署前先執行獨立建置腳本 build-and-push.sh"
      echo "  [--no-build]  跳過映像檔建置 (預設)"
      exit 0
      ;;
  esac
done

# 若指定為 docker 部署，直接委派至專屬 Docker 部署腳本
if [[ "$TOOL" == "docker" ]]; then
  exec "${SCRIPT_DIR}/deploy-docker.sh" "$@"
fi

NAMESPACE="${GLOBAL_NAMESPACE:-${NAMESPACE:-cocklebur-app}}"

CURRENT_KUBE_CTX="$(kubectl config current-context 2>/dev/null || echo "")"
case "$ENV" in
  eng)
    EXPECTED_CONTEXT="${KUBE_CONTEXT:-${ENG_KUBE_CONTEXT:-$CURRENT_KUBE_CTX}}"
    DEFAULT_DOMAIN="${ENG_DEFAULT_DOMAIN:-cocklebur-eng.example.com}"
    REGISTRY="${ENG_REGISTRY:-}"
    IMAGE_TAG="${ENG_IMAGE_TAG:-latest}"
    STORAGE_CLASS="${ENG_STORAGE_CLASS:-}"
    CA_ISSUER="${ENG_CA_ISSUER:-internal-ca-issuer}"
    CA_SECRET="${ENG_CA_SECRET:-internal-ca-secret}"
    ;;
  uat)
    EXPECTED_CONTEXT="${KUBE_CONTEXT:-${UAT_KUBE_CONTEXT:-$CURRENT_KUBE_CTX}}"
    DEFAULT_DOMAIN="${UAT_DEFAULT_DOMAIN:-cocklebur-uat.example.com}"
    REGISTRY="${UAT_REGISTRY:-}"
    IMAGE_TAG="${UAT_IMAGE_TAG:-latest}"
    STORAGE_CLASS="${UAT_STORAGE_CLASS:-}"
    CA_ISSUER="${UAT_CA_ISSUER:-internal-ca-issuer}"
    CA_SECRET="${UAT_CA_SECRET:-internal-ca-secret}"
    ;;
  stg)
    EXPECTED_CONTEXT="${KUBE_CONTEXT:-${STG_KUBE_CONTEXT:-$CURRENT_KUBE_CTX}}"
    DEFAULT_DOMAIN="${STG_DEFAULT_DOMAIN:-cocklebur-stg.example.com}"
    REGISTRY="${STG_REGISTRY:-}"
    IMAGE_TAG="${STG_IMAGE_TAG:-latest}"
    STORAGE_CLASS="${STG_STORAGE_CLASS:-}"
    CA_ISSUER="${STG_CERT_ISSUER:-letsencrypt-prod}"
    CA_SECRET=""
    ;;
  prod)
    EXPECTED_CONTEXT="${KUBE_CONTEXT:-${PROD_KUBE_CONTEXT:-$CURRENT_KUBE_CTX}}"
    DEFAULT_DOMAIN="${PROD_DEFAULT_DOMAIN:-cocklebur.example.com}"
    REGISTRY="${PROD_REGISTRY:-}"
    IMAGE_TAG="${PROD_IMAGE_TAG:-0.2.17}"
    STORAGE_CLASS="${PROD_STORAGE_CLASS:-}"
    CA_ISSUER="${PROD_CERT_ISSUER:-letsencrypt-prod}"
    CA_SECRET=""
    ;;
esac

# -----------------------------------------------------------------------------
# 1. 載入應用程式環境設定檔與解析變數
# 優先順序:
#   Tier 1 (最高): 命令列 / 執行環境變數 (BASE_URL, POPUP_BASE_URL, DOMAIN)
#   Tier 2: 專案根目錄應用程式環境檔 (.env) 中的 POPUP_BASE_URL
#   Tier 3: 環境專屬 Overlay 檔 (deploy/k8s/overlays/${ENV}/.env)
#   Tier 4: 統一部署設定檔 (deploy/deploy.env) 中的 ${ENV_UPPER}_DEFAULT_DOMAIN
# -----------------------------------------------------------------------------
CLI_BASE_URL="${BASE_URL:-${POPUP_BASE_URL:-}}"
CLI_DOMAIN="${DOMAIN:-}"

POPUP_BASE_URL=""
COCKLEBUR_BOOTSTRAP_KEY=""
POPUP_SECRET_KEY=""

# (1) 先讀取根目錄 .env (以根目錄 .env 之 POPUP_BASE_URL 為主)
ROOT_ENV_FILE="${ROOT_DIR}/.env"
if [[ -f "$ROOT_ENV_FILE" ]]; then
  echo ">>> 偵測到根目錄應用程式環境檔: ${ROOT_ENV_FILE}"
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
      POPUP_SECRET_KEY)
        [[ -z "$POPUP_SECRET_KEY" ]] && POPUP_SECRET_KEY="$val"
        ;;
    esac
  done < "$ROOT_ENV_FILE"
fi

# (2) 讀取 Overlay 專屬 .env (補充/覆蓋環境專屬金鑰；若根目錄無 BASE_URL 則作為次選)
OVERLAY_ENV_FILE="${ROOT_DIR}/deploy/k8s/overlays/${ENV}/.env"
if [[ -f "$OVERLAY_ENV_FILE" ]]; then
  echo ">>> 偵測到環境專屬 Overlay 設定: ${OVERLAY_ENV_FILE}"
  while IFS='=' read -r key val || [[ -n "$key" ]]; do
    key="$(echo "$key" | tr -d ' \t\r')"
    [[ -z "$key" || "$key" =~ ^# ]] && continue
    val="$(echo "$val" | sed -e 's/^[[:space:]]*//' -e 's/[[:space:]\r]*$//')"
    if [[ "$val" =~ ^\"(.*)\"$ ]] || [[ "$val" =~ ^\'(.*)\'$ ]]; then
      val="${BASH_REMATCH[1]}"
    fi

    case "$key" in
      COCKLEBUR_BOOTSTRAP_KEY|COCKLEBUR_HOST_KEY)
        COCKLEBUR_BOOTSTRAP_KEY="$val"
        ;;
      POPUP_SECRET_KEY)
        POPUP_SECRET_KEY="$val"
        ;;
      POPUP_BASE_URL)
        # 僅在根目錄 .env 未定義 POPUP_BASE_URL 時採用 overlay 中的值
        [[ -z "$POPUP_BASE_URL" ]] && POPUP_BASE_URL="$val"
        ;;
    esac
  done < "$OVERLAY_ENV_FILE"
fi

# (3) 若皆未設定 POPUP_BASE_URL，fallback 到 deploy.env 的預設網域
if [[ -z "$POPUP_BASE_URL" && -n "$DEFAULT_DOMAIN" ]]; then
  POPUP_BASE_URL="https://${DEFAULT_DOMAIN}"
fi

# -----------------------------------------------------------------------------
# 2. 套用最高優先權 (CLI / Runtime 變數覆蓋) 並同步 DOMAIN 與 POPUP_BASE_URL
# -----------------------------------------------------------------------------
# 若執行時傳入 BASE_URL 或 POPUP_BASE_URL，以此為最高優先
if [[ -n "$CLI_BASE_URL" ]]; then
  POPUP_BASE_URL="$CLI_BASE_URL"
fi

# 自動萃取 DOMAIN
PARSED_DOMAIN=""
if [[ -n "$POPUP_BASE_URL" ]]; then
  PARSED_DOMAIN="$(python3 -c "import urllib.parse, sys; u=sys.argv[1]; p=urllib.parse.urlparse(u if '://' in u else 'https://'+u); print(p.hostname or '')" "$POPUP_BASE_URL")"
fi

# 若使用者有外部指定 DOMAIN，以 CLI 為最高優先權
if [[ -n "$CLI_DOMAIN" ]]; then
  DOMAIN="$CLI_DOMAIN"
  # 若外部指定了 DOMAIN 但未明確傳入 BASE_URL，則同步將 POPUP_BASE_URL 更新為 https://${DOMAIN}
  if [[ -z "$CLI_BASE_URL" ]]; then
    POPUP_BASE_URL="https://${DOMAIN}"
  fi
else
  DOMAIN="${PARSED_DOMAIN:-$DEFAULT_DOMAIN}"
fi

if [[ -z "$POPUP_BASE_URL" ]]; then
  POPUP_BASE_URL="https://${DOMAIN}"
fi

echo "=========================================================="
echo "Cocklebur Server 部署程序 (參數化管理)"
echo "環境:               $ENV"
echo "命名空間 (NAMESPACE): $NAMESPACE"
echo "部署工具 (TOOL):      $TOOL"
echo "執行映像檔建置 (BUILD): $DO_BUILD"
echo "預期 Context:       $EXPECTED_CONTEXT"
echo "對外網域 (DOMAIN):    $DOMAIN"
echo "基礎 URL (BASE_URL):  $POPUP_BASE_URL"
if [[ -n "$CA_ISSUER" ]]; then
  echo "自簽 CA Issuer:     $CA_ISSUER (Secret: $CA_SECRET)"
fi
echo "=========================================================="

# -----------------------------------------------------------------------------
# 3. 獨立映像檔建置步驟 (可單獨執行 build-and-push.sh，亦可由參數觸發)
# -----------------------------------------------------------------------------
if [[ "$DO_BUILD" == "true" ]]; then
  echo ">>> [前置作業] 觸發獨立建置腳本 (build-and-push.sh)..."
  "${SCRIPT_DIR}/build-and-push.sh" "$ENV" "$IMAGE_TAG"
  echo ">>> 映像檔建置與推送完成，繼續執行 Kubernetes 資源部署..."
fi

# -----------------------------------------------------------------------------
# 4. 檢查 kubectl context
# -----------------------------------------------------------------------------
CURRENT_CONTEXT="$(kubectl config current-context 2>/dev/null || echo "")"
if [[ "$CURRENT_CONTEXT" != "$EXPECTED_CONTEXT" ]]; then
  echo "提示: 目前 kubectl context 是 '$CURRENT_CONTEXT'，即將切換至 '$EXPECTED_CONTEXT'..."
  if kubectl config get-contexts "$EXPECTED_CONTEXT" >/dev/null 2>&1; then
    kubectl config use-context "$EXPECTED_CONTEXT"
  else
    echo "警告: Context '$EXPECTED_CONTEXT' 不存在於本機 kubeconfig 中！"
    if [[ "$ENV" == "prod" ]]; then
      echo "（prod 目前尚未建立叢集，可略過切換）"
      exit 1
    fi
  fi
fi

# -----------------------------------------------------------------------------
# 5. 建立 Namespace (若不存在)
# -----------------------------------------------------------------------------
if ! kubectl get namespace "$NAMESPACE" >/dev/null 2>&1; then
  echo "建立命名空間 $NAMESPACE..."
  kubectl create namespace "$NAMESPACE"
fi

# -----------------------------------------------------------------------------
# 5.1 檢查並配置 Private Registry 憑證 (避免 ImagePullBackOff)
# -----------------------------------------------------------------------------
REG_SECRET_NAME="${DOCKER_REGISTRY_SECRET:-cocklebur-registry-secret}"
if ! kubectl get secret "$REG_SECRET_NAME" -n "$NAMESPACE" >/dev/null 2>&1; then
  SRC_SEC="$(kubectl get secrets -A --field-selector type=kubernetes.io/dockerconfigjson -o jsonpath='{range .items[*]}{.metadata.namespace}{"/"}{.metadata.name}{"\n"}{end}' 2>/dev/null | head -n 1 || true)"
  if [[ -n "$SRC_SEC" ]]; then
    SRC_NS="${SRC_SEC%%/*}"
    SRC_NAME="${SRC_SEC##*/}"
    echo "複製現有 Registry Secret ($SRC_NS/$SRC_NAME) 至 $NAMESPACE/$REG_SECRET_NAME..."
    kubectl get secret "$SRC_NAME" -n "$SRC_NS" -o yaml | \
      sed "s/namespace: .*/namespace: ${NAMESPACE}/" | \
      sed "s/name: .*/name: ${REG_SECRET_NAME}/" | \
      kubectl apply -f - >/dev/null 2>&1 || true
  fi
fi

if kubectl get secret "$REG_SECRET_NAME" -n "$NAMESPACE" >/dev/null 2>&1; then
  kubectl patch serviceaccount default -n "$NAMESPACE" -p "{\"imagePullSecrets\": [{\"name\": \"${REG_SECRET_NAME}\"}]}" >/dev/null 2>&1 || true
fi

# -----------------------------------------------------------------------------
# 6. 重用 .env 變數建立/同步 Secret (cocklebur-secrets)
# -----------------------------------------------------------------------------
if [[ -z "$COCKLEBUR_BOOTSTRAP_KEY" ]]; then
  COCKLEBUR_BOOTSTRAP_KEY="$(python3 -c 'import secrets; print(secrets.token_urlsafe(32))')"
  echo "（.env 中未指定 Bootstrap Key，自動產生一組安全金鑰）"
fi
if [[ -z "$POPUP_SECRET_KEY" ]]; then
  POPUP_SECRET_KEY="$(python3 -c 'import secrets; print(secrets.token_urlsafe(32))')"
fi

echo "建立 / 更新 Secret 'cocklebur-secrets'..."
kubectl create secret generic cocklebur-secrets \
  --namespace="$NAMESPACE" \
  --from-literal=COCKLEBUR_BOOTSTRAP_KEY="$COCKLEBUR_BOOTSTRAP_KEY" \
  --from-literal=POPUP_SECRET_KEY="$POPUP_SECRET_KEY" \
  --dry-run=client -o yaml | kubectl apply -f -

# -----------------------------------------------------------------------------
# 7. 同步 .env 變數至 ConfigMap 與 ClusterIssuer
# -----------------------------------------------------------------------------
OVERLAY_DIR="${ROOT_DIR}/deploy/k8s/overlays/${ENV}"
echo "建立 / 更新 ConfigMap 'cocklebur-config'..."
kubectl create configmap cocklebur-config --namespace="$NAMESPACE" --from-literal=POPUP_APP_MODE="server" --from-literal=POPUP_DATA_DIR="/data" --from-literal=POPUP_BASE_URL="${POPUP_BASE_URL:-}" --from-literal=POPUP_MAX_UPLOAD_MB="50" --from-literal=POPUP_IMPORT_MAX_MB="2048" --from-literal=POPUP_PROJECT_QUOTA_MB="1024" --dry-run=client -o yaml | kubectl apply -f -

# -----------------------------------------------------------------------------
# 8. 執行部署 (Kustomize 或 Helm)
# -----------------------------------------------------------------------------
if [[ "$TOOL" == "kustomize" ]]; then
  echo "正在使用 Kustomize 部署 (${ENV})..."

  MANIFESTS="$(kubectl kustomize "$OVERLAY_DIR")"
  
  # 動態替換注入自訂網域 (替換範本佔位符與預設網域)
  echo "套用網域 ${DOMAIN} 至 Ingress 與 Certificate..."
  MANIFESTS="$(echo "$MANIFESTS" | sed "s/cocklebur-${ENV}\.example\.com/${DOMAIN}/g")"
  MANIFESTS="$(echo "$MANIFESTS" | sed "s/cocklebur\.example\.com/${DOMAIN}/g")"
  if [[ "$DOMAIN" != "$DEFAULT_DOMAIN" ]]; then
    MANIFESTS="$(echo "$MANIFESTS" | sed "s/${DEFAULT_DOMAIN}/${DOMAIN}/g")"
  fi

  # 動態替換 Registry 與 Tag
  if [[ -n "$REGISTRY" ]]; then
    echo "套用映像檔倉庫 ${REGISTRY}..."
    MANIFESTS="$(echo "$MANIFESTS" | sed -E "s@registry\.example\.com/(team|prod)@${REGISTRY}@g")"
  fi
  if [[ -n "$IMAGE_TAG" ]]; then
    echo "套用映像檔標籤 ${IMAGE_TAG}..."
    MANIFESTS="$(echo "$MANIFESTS" | sed -E "s@(${REGISTRY:-registry\.example\.com/(team|prod)}/cocklebur-server):[a-zA-Z0-9._-]+@\1:${IMAGE_TAG}@g")"
  fi

  # 動態替換 StorageClass
  if [[ -n "$STORAGE_CLASS" ]]; then
    echo "套用儲存類別 ${STORAGE_CLASS}..."
    MANIFESTS="$(echo "$MANIFESTS" | sed "s/storageClassName: .*/storageClassName: ${STORAGE_CLASS}/g")"
  fi

  # 動態替換自簽 CA Issuer 與 Secret
  if [[ -n "$CA_ISSUER" ]]; then
    MANIFESTS="$(echo "$MANIFESTS" | sed "s/internal-ca-issuer/${CA_ISSUER}/g")"
  fi
  if [[ -n "$CA_SECRET" ]]; then
    MANIFESTS="$(echo "$MANIFESTS" | sed "s/internal-ca-secret/${CA_SECRET}/g")"
  fi

  echo "$MANIFESTS" | kubectl apply -f -

elif [[ "$TOOL" == "helm" ]]; then
  echo "正在使用 Helm 部署 (${ENV})..."
  helm upgrade --install cocklebur "${ROOT_DIR}/deploy/helm/cocklebur" \
    --namespace "$NAMESPACE" \
    -f "${ROOT_DIR}/deploy/helm/cocklebur/values-${ENV}.yaml" \
    --set image.repository="${REGISTRY:-registry.example.com/team}/cocklebur-server" \
    --set image.tag="${IMAGE_TAG}" \
    --set config.baseUrl="${POPUP_BASE_URL}" \
    --set ingress.hosts[0].host="${DOMAIN}" \
    --set ingress.tls[0].hosts[0]="${DOMAIN}" \
    --set certificate.dnsNames[0]="${DOMAIN}" \
    --set secrets.bootstrapKey="${COCKLEBUR_BOOTSTRAP_KEY}" \
    --set secrets.secretKey="${POPUP_SECRET_KEY}"
else
  echo "錯誤: 未知的工具 '$TOOL'。請選擇 kustomize 或 helm。"
  exit 1
fi

# -----------------------------------------------------------------------------
# 9. 等待與檢查 Rollout 狀態
# -----------------------------------------------------------------------------
echo "等待 Deployment rollout..."
kubectl rollout status deployment/cocklebur-server -n "$NAMESPACE" --timeout=120s || true

echo "=========================================================="
echo "部署完成！狀態摘要："
echo "=========================================================="
kubectl get pod,svc,pvc,ingress,certificate -n "$NAMESPACE"
echo "----------------------------------------------------------"
echo "連線位址:     ${POPUP_BASE_URL}"
echo "Bootstrap Key: ${COCKLEBUR_BOOTSTRAP_KEY}"
echo "（首次連線請進入網頁點擊 Claim Host，並輸入上述 Bootstrap Key）"
echo "=========================================================="
