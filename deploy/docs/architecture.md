# 系統架構與設計決策 (Architecture & Design Decisions)

本文件詳細闡述 Cocklebur Server 在 Kubernetes 架構上的技術決策與設計考量。

---

## 1. 應用程式特性與限制

### 1.1 單一工作處理序 (Single Worker) 與檔案型儲存
- **運作模式**：Cocklebur Server 採用 Uvicorn/FastAPI 架構，執行指令為 `uvicorn app.main:app --workers 1`。
- **儲存後端**：採用 SQLite 資料庫及本機檔案系統儲存使用者專案、討論卡片、附件與稽核紀錄，所有狀態皆持久化於容器內的 `/data` 目錄。
- **不可擴展性 (Non-horizontally scalable)**：因為底層為本機檔案系統與 SQLite，**嚴禁將 Pod 副本數（Replicas）設定大於 1**。若同時有多個實例嘗試寫入同一個 SQLite 檔案，將導致 `database is locked` 錯誤或資料損毀。

---

## 2. Pod 更新策略與儲存防鎖定 (Deployment Strategy)

Kubernetes 預設的 Deployment 更新策略為 `RollingUpdate`（先起新 Pod，等待 Ready 後再刪除舊 Pod）。在具備檔案型狀態的應用中，此策略會引發以下致命問題：

1. **PVC 掛載衝突**：多數區塊型儲存（如 AWS EBS、MicroK8s HostPath、Longhorn 等）的 Access Mode 為 `ReadWriteOnce` (RWO)，代表同時間只能掛載至單一節點上的單一 Pod。RollingUpdate 會導致新 Pod 因無法掛載 Volume 而永久處於 `ContainerCreating`。
2. **SQLite 鎖定**：即便底層為可多點掛載的 NFS，新舊 Pod 重疊並行寫入 SQLite 同樣會觸發資料損毀。

### 架構解法：強制指定 `strategy.type: Recreate`
```yaml
spec:
  replicas: 1
  strategy:
    type: Recreate
```
- **運作流程**：在升級映像檔或變更設定時，Kubernetes 會**先完全終止舊 Pod** 並釋放 `/data` 儲存卷鎖定，隨後才啟動新 Pod 進行掛載。
- **維運影響**：升級時會有約數秒至數十秒的短暫停機時間（Downtime），但能 100% 確保資料的完整性與交易一致性。

---

## 3. 安全權限模型 (SecurityContext & Non-Root)

### 3.1 容器非 Root 使用者
在 Dockerfile 中，應用程式建立了專用非特權系統使用者 `popup`：
```dockerfile
RUN useradd -r -u 10001 popup && mkdir -p /data && chown -R popup:popup /data /app
USER popup
```

### 3.2 儲存卷權限指派 (`fsGroup: 10001`)
當 Kubernetes 將外掛儲存（PVC）掛載進容器時，目錄所有權預設往往屬於 `root:root (0:0)`。若未適當處理，非 root 使用者 `popup` (UID 10001) 將無法寫入 `/data`，導致服務啟動失敗。

我們在 Pod 層級明確宣告安全群組：
```yaml
spec:
  securityContext:
    runAsNonRoot: true
    runAsUser: 10001
    runAsGroup: 10001
    fsGroup: 10001
```
- **機制**：`fsGroup: 10001` 會指示 Kubelet 在 Volume 掛載時，自動遞迴將該磁碟區的 GID 調整為 10001，並賦予群組讀寫權限。
- **優勢**：無需使用額外具特權的 `initContainer` 執行 `chown`，完全符合 Kubernetes Pod Security Standards (PSS) 的 Restricted 安全等級。

---

## 4. 網路與 Ingress 路由拓撲

### 4.1 為什麼必須使用獨立子網域？（而非子路徑 `/cocklebur`）
在架構評估初期，曾評估是否能將服務掛載於現有主機的子路徑（例如 `https://example.com/cocklebur`）。經對原始碼全面靜態掃描後，確定必須採用獨立子網域（FQDN，如 `https://cocklebur.example.com`）：

1. **靜態資源絕對路徑**：HTML 模板中的 CSS、JS 引用皆為 `/static/app.css` 與 `/static/app.js`。
2. **前端 API 調用**：所有 AJAX/Fetch 端點均寫死為根路徑（如 `/api/instance/access`、`/api/projects/...`）。
3. **Cookie Path**：會話與認證 Cookie 的作用域被固定宣告為 `Path=/`。
4. **衝突避免**：若硬切子路徑，瀏覽器請求靜態資源時會直接打到根路徑上的其他服務，造成 404 或資料錯亂。

### 4.2 雙 Ingress 控制器相容架構
針對不同環境採用不同 Ingress 控制器，配置對應的 Annotations：

- **Traefik 控制器 (ENG / UAT)**：
  ```yaml
  metadata:
    annotations:
      traefik.ingress.kubernetes.io/router.entrypoints: web, websecure
      traefik.ingress.kubernetes.io/router.tls: "true"
  ```
- **Ingress-Nginx 控制器 (STG / PROD)**：
  特別配置上傳檔案限制（與程式的 `POPUP_MAX_UPLOAD_MB=50` 保持一致）：
  ```yaml
  metadata:
    annotations:
      nginx.ingress.kubernetes.io/ssl-redirect: "true"
      nginx.ingress.kubernetes.io/proxy-body-size: "50m"
      nginx.ingress.kubernetes.io/client-max-body-size: "50m"
  ```

---

## 5. 健康檢查探針 (Health Probes)

應用程式本體已內建輕量健康檢查端點：
- **檢查路徑**：`GET /health` (Port 8000)
- **Liveness Probe (存活探針)**：
  `initialDelaySeconds: 10`，`periodSeconds: 20`。若連續 3 次失敗，Kubelet 自動重啟容器。
- **Readiness Probe (就緒探針)**：
  `initialDelaySeconds: 5`，`periodSeconds: 10`。就緒後 Ingress 控制器才將網路流量轉發至此 Pod。

---

## 6. Docker / Docker Compose 部署架構考量

對於無需 Kubernetes 叢集或資源受限的獨立環境，本專案提供基於 Docker Compose 的多環境架構：

1. **環境資源命名空間隔離**：
   - 透過環境後綴動態命名：容器名稱為 `cocklebur-server-${ENV}`，資料卷為 `cocklebur_data_${ENV}`。
   - 此設計允許同一個 Docker 主機（例如共用相同 Docker Context 的開發環境與驗收環境）同時運行多個獨立實例，資料完全互不干擾。
2. **端口防衝突機制**：
   - 各環境在 `deploy/deploy.env` 中配置專屬對外映射端口（如 ENG: 8000, UAT: 8001），避免 Host 端口綁定衝突。
3. **安全配置**：
   - 啟用 `security_opt: [no-new-privileges:true]` 防止容器內提升權限。
   - 容器內原生具備健康檢查：每 15 秒探測一次本機 `http://127.0.0.1:8000/health`。
4. **生命週期管理**：
   - 採用 `restart: unless-stopped`，在 VM 或 Docker 守護程式重啟後自動回復運行。
