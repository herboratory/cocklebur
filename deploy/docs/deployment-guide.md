# 部署操作指南 (Deployment Guide)

本指南提供 Cocklebur Server 在各環境進行自動化部署、手動部署與映像檔建置的標準作業程序。

---

## 1. 事前準備 (Prerequisites)

- **Kubernetes CLI (`kubectl`)**：已安裝且設定好各叢集 Context（若使用 K8s/Helm 部署）。
- **Docker CLI (`docker`)**：已安裝並配置好各環境之 Docker Context（若使用 Docker 部署或映像檔建置）。
- **Helm 3 / 4**（若選擇 Helm 部署模式）。
- **權限需求**：
  - K8s 叢集：具備建立 Namespace、Deployment、Service、PVC、Ingress、Secret 及 cert-manager Certificate 權限。
  - Docker 環境：具備目標 Docker Context 的 SSH / Daemon 操作權限。
- **叢集基礎設施**（K8s 模式）：
  - 叢集中已安裝 Ingress Controller（Traefik 或 Ingress-Nginx）。
  - 叢集中已安裝 cert-manager (v1.x) 並配置妥當對應之 ClusterIssuer。

---

## 2. 方式一：一鍵自動化部署（推薦）

專案內建智慧化防呆部署腳本 [deploy/scripts/deploy.sh](file:///home/pveUsers/stinger/workspace/cocklebur-server/deploy/scripts/deploy.sh)，負責處理環境切換、變數萃取與資源套用。

### 2.1 語法說明
```bash
./deploy/scripts/deploy.sh [環境名稱] [部署工具] [--build|--no-build]
```
- **環境名稱 (選填，預設為 `eng`)**：可選 `eng`、`uat`、`stg`、`prod`。
- **部署工具 (選填，預設為 `kustomize`)**：可選 `kustomize`、`helm` 或 `docker`。
- **建置開關 (選填，預設為 `--no-build`)**：
  - `--build`：在部署前先呼叫獨立腳本 `build-and-push.sh` 進行 Docker 建置與推送。
  - `--no-build`：僅更新資源與設定（適用於只修改 `.env` 或設定的極速部署場景）。

### 2.2 常用指令範例

```bash
# 1. 部署 ENG 環境至 K8s 並自動建置映像檔 (--build)
./deploy/scripts/deploy.sh eng --build

# 2. 僅更新設定與 K8s 資源 (跳過映像檔建置)
./deploy/scripts/deploy.sh eng

# 3. 部署 ENG 環境至 Docker (自動切換至 ENG_DOCKER_CONTEXT)
./deploy/scripts/deploy.sh eng docker

# 4. 部署 UAT 環境至 Docker 並建置映像檔
./deploy/scripts/deploy.sh uat docker --build

# 5. 部署 STG 預發環境 (使用 Helm 引擎並觸發建置)
./deploy/scripts/deploy.sh stg helm --build

# 6. 臨時指定自訂網域部署
DOMAIN="custom-host.example.com" ./deploy/scripts/deploy.sh eng

# 7. 單獨執行映像檔建置與推送 (不觸發部署)
./deploy/scripts/build-and-push.sh eng
```

### 2.3 腳本自動化防呆機制
執行時，腳本會自動完成以下工作：
1. **驗證 Context**：檢查目前 Kubectl 或 Docker Context 是否符合該環境預期，若不符合自動切換；若找不到 Context 則中斷並提示。
2. **自動建立 Namespace / Volume**：確保 K8s 命名空間或 Docker 專用 Volume 存在。
3. **讀取與解析 `.env`**：自動載入 `POPUP_BASE_URL`、`COCKLEBUR_HOST_KEY` 與 `POPUP_SECRET_KEY`。
4. **動態網域萃取**：自動從 `POPUP_BASE_URL` 解析出 Hostname，並同步更新 Ingress、Certificate 或 Docker 變數。
5. **產生與注入 Secret**：自動建立金鑰，若設定檔未提供則自動產生高強度隨機金鑰。
6. **自癒映像檔拉取憑證**：K8s 部署時自動偵測叢集內的私有 Registry 憑證並綁定至 ServiceAccount，避免 `ImagePullBackOff`。
7. **監控進度與列印資訊**：監聽就緒狀態，並列印出對外連線 URL 與首次登入 Bootstrap Key。

---

## 3. 方式二：使用 Kustomize 手動部署

若環境受限（如 CI/CD Runner 未安裝客製腳本），可直接調用原生的 `kubectl apply -k`。

### 步驟 1：切換 Context 與建立 Namespace
```bash
kubectl config use-context <YOUR_CLUSTER_CONTEXT>
kubectl create namespace cocklebur-app --dry-run=client -o yaml | kubectl apply -f -
```

### 步驟 2：手動建立 Secret
```bash
kubectl create secret generic cocklebur-secrets \
  --namespace=cocklebur-app \
  --from-literal=COCKLEBUR_BOOTSTRAP_KEY="<YOUR_BOOTSTRAP_KEY>" \
  --from-literal=POPUP_SECRET_KEY="<YOUR_SECRET_KEY>" \
  --dry-run=client -o yaml | kubectl apply -f -
```

### 步驟 3：預覽與套用 Overlay
```bash
# 預覽產生之 YAML
kubectl kustomize deploy/k8s/overlays/eng

# 部署至叢集
kubectl apply -k deploy/k8s/overlays/eng
```

---

## 4. 方式三：使用 Helm 手動部署

Cocklebur 提供了標準的 Helm Chart（位於 `deploy/helm/cocklebur/`）。

### 步驟 1：語法檢查與渲染驗證
```bash
helm template cocklebur deploy/helm/cocklebur \
  -f deploy/helm/cocklebur/values-eng.yaml
```

### 步驟 2：執行安裝或升級
```bash
helm upgrade --install cocklebur deploy/helm/cocklebur \
  --namespace cocklebur-app \
  --create-namespace \
  -f deploy/helm/cocklebur/values-eng.yaml \
  --set secrets.bootstrapKey="<YOUR_BOOTSTRAP_KEY>" \
  --set secrets.secretKey="<YOUR_SECRET_KEY>"
```

---

## 5. 方式四：使用 Docker / Docker Compose 獨立部署

若目標機器為獨立 VM 或偏好直接以 Docker Compose 管理，可使用專屬部署腳本 [deploy/scripts/deploy-docker.sh](file:///home/pveUsers/stinger/workspace/cocklebur-server/deploy/scripts/deploy-docker.sh)：

### 5.1 部署語法
```bash
./deploy/scripts/deploy-docker.sh [環境名稱: eng|uat|stg|prod] [--build|--no-build]
```

### 5.2 核心特性
1. **多環境獨立隔離**：
   - 容器名稱自動命名為 `cocklebur-server-${ENV}`。
   - 資料卷自動獨立為 `cocklebur_data_${ENV}`，確保存放於 `/data` 的 SQLite 與檔案永不遺失且互不干擾。
2. **自動端口管理**：
   - `ENG` 預設端口 `8000`。
   - `UAT` 與 `ENG` 共用 Docker 主機時，預設使用 `8001` 避免 Host 端口碰撞。
   - 亦可透過 `PORT=xxxx` 臨時自訂。
3. **安全配置與健康檢查**：
   - 啟用 `security_opt: [no-new-privileges:true]`。
   - 配置每 15 秒探測 `/health` 之健康檢查機制。

### 5.3 手動 Docker Compose 指令範例
若需手動操作 Docker Compose：
```bash
# 1. 設置環境變數
export IMAGE_NAME="registry.example.com/team/cocklebur-server:latest"
export CONTAINER_NAME="cocklebur-server-eng"
export VOLUME_NAME="cocklebur_data_eng"
export HOST_PORT=8000
export POPUP_BASE_URL="http://cocklebur-eng.example.com:8000"
export COCKLEBUR_BOOTSTRAP_KEY="<YOUR_BOOTSTRAP_KEY>"
export POPUP_SECRET_KEY="<YOUR_SECRET_KEY>"

# 2. 透過指定 Docker Context 啟動服務
docker --context <your-eng-docker-context> compose \
  -f deploy/docker/docker-compose.yml \
  -p cocklebur-eng up -d
```

---

## 6. 映像檔建置與推送流程

若有修改原始碼，需產生新版 Docker 映像檔並推送至該環境對應之 Container Registry：

使用內建腳本 [deploy/scripts/build-and-push.sh](file:///home/pveUsers/stinger/workspace/cocklebur-server/deploy/scripts/build-and-push.sh)：

```bash
# 語法: ./deploy/scripts/build-and-push.sh [環境: eng|uat|stg|prod] [版本 Tag]

# 範例 1: 建置並推送至 ENG/UAT Registry (最新版)
./deploy/scripts/build-and-push.sh eng latest

# 範例 2: 建置並推送至 STG/PROD Registry (指定正式版本)
./deploy/scripts/build-and-push.sh prod 0.2.16
```

腳本會依環境自動切換本機對應的 Docker Context（例如 `<docker-context-eng>` 或 `<docker-context-stg>`），並推送至正確的私有 Registry 位址。

---

## 7. 部署後驗證步驟

### 7.1 Kubernetes 部署驗證
1. **檢查 Pod 是否處於 Running 狀態**：
   ```bash
   kubectl get pods -n cocklebur-app -l app.kubernetes.io/name=cocklebur-server
   ```
2. **檢查 PVC 是否已綁定 (Bound)**：
   ```bash
   kubectl get pvc -n cocklebur-app
   ```
3. **檢查 Ingress 狀態與 IP 分配**：
   ```bash
   kubectl get ingress -n cocklebur-app
   ```
4. **檢查 cert-manager 憑證簽署進度**：
   ```bash
   kubectl get certificate,certificaterequest,order -n cocklebur-app
   ```
   確認 Certificate 的 `READY` 狀態為 `True`。

### 7.2 Docker 部署驗證
1. **檢查容器運行狀態與健康指標**：
   ```bash
   docker --context <docker-context-eng> ps -f "name=cocklebur-server"
   ```
   確認 Status 顯示為 `Up ... (healthy)`。
2. **檢查容器日誌**：
   ```bash
   docker --context <docker-context-eng> logs --tail 50 cocklebur-server-eng
   ```
3. **檢查資料卷是否正確掛載**：
   ```bash
   docker --context <docker-context-eng> volume inspect cocklebur_data_eng
   ```
