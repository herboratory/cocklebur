# Cocklebur Server Kubernetes 多環境部署指南

本專案提供 `cocklebur-server` 在 Kubernetes 上的多環境部署架構，同時支援 **Kustomize**（原生標準）與 **Helm Chart** 兩種部署模式，並具備自動更新的 TLS 憑證、獨立的 PersistentVolume 儲存以及多環境隔離機制。

---

## 1. 環境對照表 (Environment Matrix)

| 項目 | ENG (開發環境) | UAT (驗收環境) | STG (預發環境) | PROD (正式環境) |
| :--- | :--- | :--- | :--- | :--- |
| **Kubectl Context** | `<eng-cluster-context>` | `<uat-cluster-context>` | `<stg-cluster-context>` | `<prod-cluster-context>` |
| **Namespace** | `cocklebur-app` | `cocklebur-app` | `cocklebur-app` | `cocklebur-app` |
| **對外網域** | `cocklebur-eng.example.com` | `cocklebur-uat.example.com` | `cocklebur-stg.example.com` | `cocklebur.example.com` |
| **Ingress Controller** | Traefik | Traefik | Ingress-Nginx | Ingress-Nginx |
| **TLS Secret 名稱** | `cocklebur-tls-eng` | `cocklebur-tls-uat` | `cocklebur-tls-stg` | `cocklebur-tls-prod` |
| **憑證簽發者 (Issuer)** | 內網自簽 CA (`internal-ca-issuer`) | 內網自簽 CA (`internal-ca-issuer`) | Let's Encrypt (`letsencrypt-prod`)| Let's Encrypt (`letsencrypt-prod`)|
| **StorageClass** | `local-path` | `local-path` | `nfs-client` | `standard` (或依叢集提供) |
| **PV 容量** | 10 GiB | 10 GiB | 10 GiB | 20 GiB |
| **Image Registry** | `registry.example.com/team` | `registry.example.com/team` | `registry.example.com/prod` | `registry.example.com/prod` |
| **Docker Context** | `<docker-context-eng>` | `<docker-context-eng>` | `<docker-context-stg>` | `<docker-context-stg>` |
| **Docker Host Port**| `8000` | `8001` (避免與 eng 衝突) | `8000` | `8000` |

---

## 2. 核心架構與重要規則

1. **單一 Pod 與更新策略 (Recreate)**：
   Cocklebur 使用底層檔案型儲存（SQLite 與目錄檔案），同時間只能有 1 個實例寫入。Deployment 嚴格設定 `replicas: 1` 且更新策略為 `strategy.type: Recreate`，避免升級時因多 Pod 同時掛載 RWO PV 發生鎖定。
2. **安全性與權限 (SecurityContext)**：
   容器以非 root 使用者 `popup` (UID 10001) 執行。Pod 配置 `securityContext.fsGroup: 10001`，確保掛載的 PVC 目錄具備正確讀寫權限。Docker 模式下則開啟 `no-new-privileges: true`。
3. **網域與路徑**：
   系統前端 API 請求 (`/api/...`) 與靜態資源全部以根目錄 `/` 運作，因此各環境皆配置專屬獨立子網域（如 `cocklebur-eng.example.com`）。
4. **TLS Secret 與 Namespace 隔離**：
   Kubernetes Ingress 規定 TLS Secret 必須與 Ingress 位於同一個 Namespace。我們透過 cert-manager 的 `Certificate` 資源直接在 `cocklebur-app` 命名空間內自動產生並展延 `cocklebur-tls-<env>` Secret。
5. **Private Registry 映像檔認證自癒**：
   部署腳本會自動檢查並同步私有 Registry 憑證至 ServiceAccount，避免 Kubernetes 下載私有映像檔時遭遇 `ImagePullBackOff`。

---

## 3. 全域統一部署變數中心 (`deploy/deploy.env`)

本專案建立了 **K8s、Helm、Docker 與 Scripts 的全域統一變數設定檔** [deploy/deploy.env](file:///home/pveUsers/stinger/workspace/cocklebur-server/deploy/deploy.env)。

**您只需要在 `deploy/deploy.env` 調整各環境的參數**（例如 Context、StorageClass、容量、CA Secret、Registry、Docker Context/Port、網域等），執行部署時，K8s、Helm 與 Docker 都會全自動套用最新設定：

```ini
# 例如修改 ENG 環境設定範例：
ENG_DOCKER_CONTEXT="<your-eng-docker-context>"
ENG_DOCKER_PORT=8000
ENG_STORAGE_CLASS="local-path"
ENG_STORAGE_SIZE="10Gi"
ENG_CA_ISSUER="internal-ca-issuer"
ENG_CA_SECRET="internal-ca-secret"
```

若手動修改了 `deploy/deploy.env`，可透過以下指令一鍵同步所有 Kustomize Overlays 與 Helm Values：
```bash
./deploy/scripts/sync.sh
```
*(注意：執行 `./deploy/scripts/deploy.sh` 時已內建自動執行同步，完全無需手動介入)*

---

## 4. 應用程式 `.env` 變數直接重用機制

除了基礎架構變數外，您也可以**直接修改應用程式的 `.env` 檔案**（專案根目錄 `.env` 或 `deploy/k8s/overlays/<env>/.env`），部署程式會自動重用：

1. **網域自動同步**：
   在 `.env` 中設定 `POPUP_BASE_URL=https://cocklebur.example.com`，部署腳本會**自動萃取出網域**，並同步注入至 Kubernetes 的 **Ingress host**、**cert-manager Certificate dnsNames** 以及 Pod 的 **ConfigMap**，無需手動修改任何 YAML 檔！
2. **機密金鑰自動同步**：
   在 `.env` 中設定 `COCKLEBUR_HOST_KEY=...`，部署腳本會自動讀取並同步至 Kubernetes Secret `cocklebur-secrets` 或 Docker Compose 環境變數。
3. **命令列臨時自訂網域**：
   若臨時想要部署至其他網域，可直接透過環境變數傳入：
   ```bash
   DOMAIN="my-test.example.com" ./deploy/scripts/deploy.sh eng
   ```

---

## 5. 快速部署流程

### 方式 A：一鍵部署腳本 (支援 K8s、Helm 與 Docker)

專案提供了自動讀取 `.env`、自動切換 Context、建立 Namespace/Volume、同步 Secret 並部署的整合腳本：

```bash
# 語法: ./deploy/scripts/deploy.sh [環境] [部署工具: kustomize|helm|docker] [--build|--no-build]

# 1. 部署 ENG 環境至 Kubernetes (預設 kustomize，可帶 --build 建置映像檔)
./deploy/scripts/deploy.sh eng --build

# 2. 僅更新 K8s 資源與設定 (預設跳過映像檔建置，極速部署)
./deploy/scripts/deploy.sh eng

# 3. 使用 Docker 部署至 ENG (自動使用 ENG_DOCKER_CONTEXT)
./deploy/scripts/deploy.sh eng docker

# 4. 使用 Docker 部署至 UAT (自動使用 UAT_DOCKER_CONTEXT 與 UAT_DOCKER_PORT)
./deploy/scripts/deploy.sh uat docker --build

# 5. 部署 STG 環境 (使用 Helm 並建置映像檔)
./deploy/scripts/deploy.sh stg helm --build

# 6. 單獨執行映像檔建置與推送 (不觸發部署)
./deploy/scripts/build-and-push.sh eng
```

---

### 方式 B：使用 Kustomize 手動部署

#### 步驟 1：切換至目標叢集 Context
```bash
# ENG
kubectl config use-context <eng-cluster-context>

# STG
kubectl config use-context <stg-cluster-context>
```

#### 步驟 2：建立 Namespace 與 Secret
```bash
kubectl create namespace cocklebur-app --dry-run=client -o yaml | kubectl apply -f -

# 產生安全金鑰並建立 Secret:
BOOTSTRAP_KEY=$(python3 -c 'import secrets; print(secrets.token_urlsafe(32))')
SECRET_KEY=$(python3 -c 'import secrets; print(secrets.token_urlsafe(32))')

kubectl create secret generic cocklebur-secrets \
  --namespace=cocklebur-app \
  --from-literal=COCKLEBUR_BOOTSTRAP_KEY="$BOOTSTRAP_KEY" \
  --from-literal=POPUP_SECRET_KEY="$SECRET_KEY" \
  --dry-run=client -o yaml | kubectl apply -f -

echo "請保存 Bootstrap Key: $BOOTSTRAP_KEY"
```

#### 步驟 3：套用 Kustomize Overlay
```bash
# 預覽渲染後的 YAML
kubectl kustomize deploy/k8s/overlays/eng

# 實際部署 (以 eng 為例)
kubectl apply -k deploy/k8s/overlays/eng
```

---

### 方式 C：使用 Helm 手動部署

```bash
kubectl create namespace cocklebur-app --dry-run=client -o yaml | kubectl apply -f -

# 透過 Helm 部署並以 values-<env>.yaml 覆蓋設定
helm upgrade --install cocklebur deploy/helm/cocklebur \
  --namespace cocklebur-app \
  -f deploy/helm/cocklebur/values-eng.yaml \
  --set secrets.bootstrapKey="<YOUR_BOOTSTRAP_KEY>" \
  --set secrets.secretKey="<YOUR_SECRET_KEY>"
```

---

### 方式 D：使用獨立 Docker 腳本部署

若目標機器偏好以 Docker / Docker Compose 執行容器：

```bash
# 語法: ./deploy/scripts/deploy-docker.sh [環境] [--build|--no-build]

# 部署至 ENG (使用 deploy.env 中的 ENG_DOCKER_CONTEXT 與 ENG_DOCKER_PORT)
./deploy/scripts/deploy-docker.sh eng

# 部署至 UAT 並先建置映像檔
./deploy/scripts/deploy-docker.sh uat --build

# 臨時指定端口或 Docker Context 部署
PORT=8080 DOCKER_CTX="<custom-docker-context>" ./deploy/scripts/deploy-docker.sh eng
```

---

## 6. 映像檔建置與推送

若有更新程式碼並需推送到對應環境的 Container Registry：

```bash
# 語法: ./deploy/scripts/build-and-push.sh [環境] [版本標籤]

# 建置並推送至 ENG/UAT Registry
./deploy/scripts/build-and-push.sh eng latest

# 建置並推送至 STG Registry
./deploy/scripts/build-and-push.sh stg latest

# 指定版本 tag
./deploy/scripts/build-and-push.sh prod 0.2.16
```

---

## 7. 首次認領 Host (First Host Claim)

部署完成且 DNS 解析就緒後：

1. 開啟瀏覽器進入首頁（如 `https://cocklebur-eng.example.com` 或 `http://localhost:8000`）。
2. 點擊右上角 **Claim Host**。
3. 輸入 Host 名稱並填入部署時建立的 `COCKLEBUR_BOOTSTRAP_KEY`。
4. 系統會顯示 **Host Recovery Code**，請務必妥善備份保存。
5. 完成認領後，Bootstrap Key 即失效，日後若需登入其他瀏覽器請使用 Host Recovery Code。

---

## 8. 狀態檢查與排錯

### Kubernetes 狀態檢查
```bash
# 查看所有相關資源狀態
kubectl get all,pvc,ingress,certificate -n cocklebur-app

# 檢查 cert-manager 憑證簽發進度
kubectl describe certificate cocklebur-certificate -n cocklebur-app

# 查看應用程式 Pod 即時日誌
kubectl logs -f deployment/cocklebur-server -n cocklebur-app

# 進入 Pod 內部檢查 /data 目錄
kubectl exec -it deployment/cocklebur-server -n cocklebur-app -- ls -la /data
```

### Docker 狀態檢查
```bash
# 查看 Docker 容器執行狀態與健康檢查
docker --context <docker-context-eng> ps -f "name=cocklebur-server"

# 查看容器即時日誌
docker --context <docker-context-eng> logs -f cocklebur-server-eng

# 檢查 Docker 資料卷 (Volume)
docker --context <docker-context-eng> volume inspect cocklebur_data_eng
```
