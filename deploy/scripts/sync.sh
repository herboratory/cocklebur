#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
ROOT_DIR="$(cd "${SCRIPT_DIR}/../.." && pwd)"
DEPLOY_DIR="${ROOT_DIR}/deploy"

# 載入統一設定檔
CONFIG_FILE="${DEPLOY_DIR}/deploy.env"
if [[ -f "$CONFIG_FILE" ]]; then
  set -a
  # shellcheck disable=SC1090
  source "$CONFIG_FILE"
  set +a
else
  echo "錯誤: 找不到設定檔 $CONFIG_FILE"
  exit 1
fi

echo "=========================================================="
echo "同步 K8s Kustomize Overlays 與 Helm Values 設定檔"
echo "來源: $CONFIG_FILE"
echo "=========================================================="

ENV_LIST=("eng" "uat" "stg" "prod")

for ENV in "${ENV_LIST[@]}"; do
  ENV_UPPER="$(echo "$ENV" | tr '[:lower:]' '[:upper:]')"

  # 讀取對應環境之變數 (支援環境變數優先覆蓋)
  VAR_CTX="${ENV_UPPER}_KUBE_CONTEXT"
  VAR_REG="${ENV_UPPER}_REGISTRY"
  VAR_TAG="${ENV_UPPER}_IMAGE_TAG"
  VAR_DOM="${ENV_UPPER}_DEFAULT_DOMAIN"
  VAR_SC="${ENV_UPPER}_STORAGE_CLASS"
  VAR_SZ="${ENV_UPPER}_STORAGE_SIZE"
  VAR_ING_CLS="${ENV_UPPER}_INGRESS_CLASS"
  VAR_ING_TYPE="${ENV_UPPER}_INGRESS_TYPE"
  VAR_TLS_SEC="${ENV_UPPER}_TLS_SECRET"
  VAR_ISSUER="${ENV_UPPER}_CERT_ISSUER"
  VAR_ISSUER_KIND="${ENV_UPPER}_CERT_ISSUER_KIND"
  VAR_CA_SEC="${ENV_UPPER}_CA_SECRET"

  KUBE_CTX="${!VAR_CTX:-}"
  REGISTRY="${!VAR_REG:-}"
  IMAGE_TAG="${!VAR_TAG:-${DEFAULT_IMAGE_TAG:-latest}}"
  DOMAIN="${!VAR_DOM:-}"
  STORAGE_CLASS="${!VAR_SC:-}"
  STORAGE_SIZE="${!VAR_SZ:-10Gi}"
  INGRESS_CLASS="${!VAR_ING_CLS:-public}"
  INGRESS_TYPE="${!VAR_ING_TYPE:-traefik}"
  TLS_SECRET="${!VAR_TLS_SEC:-cocklebur-tls-${ENV}}"
  CERT_ISSUER="${!VAR_ISSUER:-letsencrypt-prod}"
  CERT_ISSUER_KIND="${!VAR_ISSUER_KIND:-ClusterIssuer}"
  CA_SECRET="${!VAR_CA_SEC:-}"
  NAMESPACE="${GLOBAL_NAMESPACE:-cocklebur-app}"

  echo ">>> 正在更新 [${ENV}] 環境配置..."

  # ---------------------------------------------------------------------------
  # 1. 更新 Kustomize Overlay
  # ---------------------------------------------------------------------------
  OVERLAY_DIR="${DEPLOY_DIR}/k8s/overlays/${ENV}"
  mkdir -p "$OVERLAY_DIR"

  # 1.1 env-config.env
  cat <<EOF > "${OVERLAY_DIR}/env-config.env"
POPUP_APP_MODE=server
POPUP_DATA_DIR=/data
POPUP_BASE_URL=https://${DOMAIN}
POPUP_MAX_UPLOAD_MB=${POPUP_MAX_UPLOAD_MB:-50}
POPUP_IMPORT_MAX_MB=${POPUP_IMPORT_MAX_MB:-2048}
POPUP_PROJECT_QUOTA_MB=${POPUP_PROJECT_QUOTA_MB:-1024}
EOF

  # 1.2 cluster-issuer-ca.yaml (若有設定 CA_SECRET)
  HAS_CA_RESOURCE="false"
  if [[ -n "$CA_SECRET" ]]; then
    HAS_CA_RESOURCE="true"
    cat <<EOF > "${OVERLAY_DIR}/cluster-issuer-ca.yaml"
apiVersion: cert-manager.io/v1
kind: ClusterIssuer
metadata:
  name: ${CERT_ISSUER}
spec:
  ca:
    secretName: ${CA_SECRET}
EOF
  else
    rm -f "${OVERLAY_DIR}/cluster-issuer-ca.yaml"
  fi

  # 1.3 kustomization.yaml
  INGRESS_ANNOTATIONS=""
  if [[ "$INGRESS_TYPE" == "traefik" ]]; then
    INGRESS_ANNOTATIONS=$(cat <<EOF
        annotations:
          traefik.ingress.kubernetes.io/router.entrypoints: web, websecure
          traefik.ingress.kubernetes.io/router.tls: "true"
EOF
)
  else
    INGRESS_ANNOTATIONS=$(cat <<EOF
        annotations:
          nginx.ingress.kubernetes.io/ssl-redirect: "true"
          nginx.ingress.kubernetes.io/proxy-body-size: "${POPUP_MAX_UPLOAD_MB:-50}m"
          nginx.ingress.kubernetes.io/client-max-body-size: "${POPUP_MAX_UPLOAD_MB:-50}m"
EOF
)
  fi

  RESOURCES_LIST="  - ../../base"
  if [[ "$HAS_CA_RESOURCE" == "true" ]]; then
    RESOURCES_LIST="${RESOURCES_LIST}
  - cluster-issuer-ca.yaml"
  fi

  STORAGE_CLASS_SPEC=""
  if [[ -n "$STORAGE_CLASS" ]]; then
    STORAGE_CLASS_SPEC="storageClassName: ${STORAGE_CLASS}"
  fi

  cat <<EOF > "${OVERLAY_DIR}/kustomization.yaml"
apiVersion: kustomize.config.k8s.io/v1beta1
kind: Kustomization

namespace: ${NAMESPACE}

resources:
${RESOURCES_LIST}

images:
  - name: cocklebur-server
    newName: ${REGISTRY}/cocklebur-server
    newTag: "${IMAGE_TAG}"

configMapGenerator:
  - name: cocklebur-config
    envs:
      - env-config.env

patches:
  # 1. PVC 儲存設定
  - target:
      kind: PersistentVolumeClaim
      name: cocklebur-data
    patch: |-
      apiVersion: v1
      kind: PersistentVolumeClaim
      metadata:
        name: cocklebur-data
      spec:
        ${STORAGE_CLASS_SPEC}
        resources:
          requests:
            storage: ${STORAGE_SIZE}

  # 2. Ingress 設定 (${INGRESS_TYPE} 控制器)
  - target:
      kind: Ingress
      name: cocklebur-ingress
    patch: |-
      apiVersion: networking.k8s.io/v1
      kind: Ingress
      metadata:
        name: cocklebur-ingress
${INGRESS_ANNOTATIONS}
      spec:
        ingressClassName: ${INGRESS_CLASS}
        rules:
          - host: ${DOMAIN}
            http:
              paths:
                - path: /
                  pathType: Prefix
                  backend:
                    service:
                      name: cocklebur-service
                      port:
                        number: 8000
        tls:
          - hosts:
              - ${DOMAIN}
            secretName: ${TLS_SECRET}

  # 3. cert-manager Certificate 設定
  - target:
      kind: Certificate
      name: cocklebur-certificate
    patch: |-
      apiVersion: cert-manager.io/v1
      kind: Certificate
      metadata:
        name: cocklebur-certificate
      spec:
        secretName: ${TLS_SECRET}
        issuerRef:
          name: ${CERT_ISSUER}
          kind: ${CERT_ISSUER_KIND}
          group: cert-manager.io
        dnsNames:
          - ${DOMAIN}
EOF

  # ---------------------------------------------------------------------------
  # 2. 更新 Helm Values
  # ---------------------------------------------------------------------------
  HELM_VALUES_FILE="${DEPLOY_DIR}/helm/cocklebur/values-${ENV}.yaml"

  HELM_INGRESS_ANNOTATIONS=""
  if [[ "$INGRESS_TYPE" == "traefik" ]]; then
    HELM_INGRESS_ANNOTATIONS=$(cat <<EOF
    traefik.ingress.kubernetes.io/router.entrypoints: web, websecure
    traefik.ingress.kubernetes.io/router.tls: "true"
EOF
)
  else
    HELM_INGRESS_ANNOTATIONS=$(cat <<EOF
    nginx.ingress.kubernetes.io/ssl-redirect: "true"
    nginx.ingress.kubernetes.io/proxy-body-size: "${POPUP_MAX_UPLOAD_MB:-50}m"
    nginx.ingress.kubernetes.io/client-max-body-size: "${POPUP_MAX_UPLOAD_MB:-50}m"
EOF
)
  fi

  HELM_CA_BLOCK=""
  if [[ -n "$CA_SECRET" ]]; then
    HELM_CA_BLOCK=$(cat <<EOF
clusterIssuerCA:
  create: true
  name: ${CERT_ISSUER}
  caSecretName: ${CA_SECRET}
EOF
)
  else
    HELM_CA_BLOCK=$(cat <<EOF
clusterIssuerCA:
  create: false
EOF
)
  fi

  cat <<EOF > "$HELM_VALUES_FILE"
# =============================================================================
# 自動產生自 deploy/deploy.env - 請勿手動修改此檔，如需調整請修改 deploy/deploy.env
# 環境: ${ENV_UPPER}
# =============================================================================

image:
  repository: ${REGISTRY}/cocklebur-server
  tag: "${IMAGE_TAG}"

ingress:
  className: "${INGRESS_CLASS}"
  annotations:
${HELM_INGRESS_ANNOTATIONS}
  hosts:
    - host: ${DOMAIN}
      paths:
        - path: /
          pathType: Prefix
  tls:
    - secretName: ${TLS_SECRET}
      hosts:
        - ${DOMAIN}

certificate:
  secretName: ${TLS_SECRET}
  issuerRef:
    name: ${CERT_ISSUER}
    kind: ${CERT_ISSUER_KIND}
  dnsNames:
    - ${DOMAIN}

${HELM_CA_BLOCK}

persistence:
  storageClassName: "${STORAGE_CLASS}"
  size: ${STORAGE_SIZE}

config:
  baseUrl: https://${DOMAIN}
  maxUploadMb: "${POPUP_MAX_UPLOAD_MB:-50}"
  importMaxMb: "${POPUP_IMPORT_MAX_MB:-2048}"
  projectQuotaMb: "${POPUP_PROJECT_QUOTA_MB:-1024}"
EOF

done

echo "=========================================================="
echo "同步完成！Kustomize 與 Helm 設定檔均已更新。"
echo "=========================================================="
