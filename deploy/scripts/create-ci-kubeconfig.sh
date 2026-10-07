#!/usr/bin/env bash
set -euo pipefail

# =============================================================================
# 產生符合 CI/CD 最小權限之 Kubeconfig (僅限 cocklebur-app namespace)
# 用法: ./deploy/scripts/create-ci-kubeconfig.sh [kube-context] [output-file]
# 範例: ./deploy/scripts/create-ci-kubeconfig.sh uat22-k8s uat-ci-kubeconfig.yaml
# =============================================================================

CTX="${1:-$(kubectl config current-context)}"
OUT_FILE="${2:-ci-kubeconfig.yaml}"
NAMESPACE="cocklebur-app"
SA_NAME="cocklebur-ci-deployer"
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
ROOT_DIR="$(cd "${SCRIPT_DIR}/../.." && pwd)"

echo "=== 開始配置最小權限 CI/CD 帳號 ==="
echo "目標 Context:   $CTX"
echo "命名空間:       $NAMESPACE"
echo "ServiceAccount: $SA_NAME"
echo "輸出檔案:       $OUT_FILE"

# 1. 確保 Namespace 存在
if ! kubectl --context "$CTX" get ns "$NAMESPACE" >/dev/null 2>&1; then
  kubectl --context "$CTX" create ns "$NAMESPACE"
fi

# 2. 套用最小權限 RBAC 定義
kubectl --context "$CTX" apply -f "${ROOT_DIR}/deploy/k8s/rbac/ci-deployer-rbac.yaml"

# 3. 取得 API Server 端點與 CA 憑證
CURRENT_CLUSTER="$(kubectl config view --raw -o jsonpath="{.contexts[?(@.name == \"$CTX\")].context.cluster}")"
API_SERVER="$(kubectl config view --raw -o jsonpath="{.clusters[?(@.name == \"$CURRENT_CLUSTER\")].cluster.server}")"
CLUSTER_CA="$(kubectl config view --raw --flatten -o jsonpath="{.clusters[?(@.name == \"$CURRENT_CLUSTER\")].cluster.certificate-authority-data}")"

# 4. 取得或產生長期 ServiceAccount Token (K8s 1.24+ 相容)
SECRET_NAME="${SA_NAME}-token"
if ! kubectl --context "$CTX" get secret "$SECRET_NAME" -n "$NAMESPACE" >/dev/null 2>&1; then
  kubectl --context "$CTX" apply -n "$NAMESPACE" -f - <<EOF
apiVersion: v1
kind: Secret
metadata:
  name: ${SECRET_NAME}
  namespace: ${NAMESPACE}
  annotations:
    kubernetes.io/service-account.name: ${SA_NAME}
type: kubernetes.io/service-account-token
EOF
  sleep 2
fi

TOKEN="$(kubectl --context "$CTX" get secret "$SECRET_NAME" -n "$NAMESPACE" -o jsonpath='{.data.token}' | base64 -d)"

# 5. 組合獨立的最小權限 Kubeconfig
cat <<EOF > "$OUT_FILE"
apiVersion: v1
kind: Config
clusters:
- name: ${CURRENT_CLUSTER}
  cluster:
    server: ${API_SERVER}
    certificate-authority-data: ${CLUSTER_CA}
users:
- name: ${SA_NAME}
  user:
    token: ${TOKEN}
contexts:
- name: ci-context
  context:
    cluster: ${CURRENT_CLUSTER}
    namespace: ${NAMESPACE}
    user: ${SA_NAME}
current-context: ci-context
EOF

chmod 600 "$OUT_FILE"
echo "=========================================================="
echo "最小權限 Kubeconfig 產生完成！"
echo "檔案路徑: $OUT_FILE"
echo ""
echo "測試驗證："
echo "  kubectl --kubeconfig=$OUT_FILE get pods -n $NAMESPACE  # 應該成功"
echo "  kubectl --kubeconfig=$OUT_FILE get pods -n default     # 應該被拒絕 (403 Forbidden)"
echo "=========================================================="
