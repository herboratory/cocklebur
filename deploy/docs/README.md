# Cocklebur Server Kubernetes 部署架構說明文件

歡迎閱讀 Cocklebur Server Kubernetes 雲原生部署手冊。本文件集詳細說明了針對 Cocklebur Server 特性所設計的高可用與多環境隔離部署架構，涵蓋 **Kustomize** 與 **Helm** 雙軌支援、自動化 TLS 憑證展延、持久化存儲掛載、以及環境變數動態同步機制。

---

## 快速導覽 (Documentation Index)

| 文件章節 | 說明重點 |
| :--- | :--- |
| **[1. 系統架構與設計決策 (Architecture)](architecture.md)** | Pod 單一實例特性、Recreate 策略、安全權限模型 (fsGroup 10001)、Ingress 拓撲、Docker 隔離 |
| **[2. 部署操作指南 (Deployment Guide)](deployment-guide.md)** | Kustomize、Helm 與 Docker 三軌部署、一鍵自動化腳本 (`deploy.sh` / `deploy-docker.sh`)、多環境切換 |
| **[3. 設定檔與機密管理 (Config & Secrets)](configuration-and-secrets.md)** | `deploy.env` 全域單一來源 (SSOT)、網域自動提取與同步、Bootstrap Key 生命週期 |
| **[4. TLS 憑證與自動展延 (TLS & Certificates)](tls-and-certificates.md)** | cert-manager 整合、CA / Let's Encrypt 簽發、Ingress 命名空間隔離限制與解法 |
| **[5. 持久化存儲與備份還原 (Storage & Backup)](storage-and-backup.md)** | PVC 規格、StorageClass 選擇、Docker Volume 隔離、SQLite 檔案鎖定防護、備份與還原流程 |

---

## 系統總體架構概覽 (System Architecture)

```
                       [ 外部使用者 / 客戶端瀏覽器 ]
                                     |
                                  (HTTPS)
                                     v
                  +--------------------------------------+
                  |           Ingress Controller         |
                  |  (Traefik / Nginx Ingress Controller)|
                  +--------------------------------------+
                                     |
                   (TLS Termination via cert-manager)
                   (Secret: cocklebur-tls-<env>)
                                     |
                                     v
                  +--------------------------------------+
                  |          ClusterIP Service           |
                  |     (cocklebur-service: Port 8000)   |
                  +--------------------------------------+
                                     |
                                     v
+-------------------------------------------------------------------------+
| Namespace: cocklebur-app                                                |
|                                                                         |
|  +-------------------------------------------------------------------+  |
|  | Deployment (replicas: 1, strategy: Recreate)                      |  |
|  |                                                                   |  |
|  |  +-------------------------------------------------------------+  |  |
|  |  | Pod (SecurityContext: runAsUser: 10001, fsGroup: 10001)     |  |  |
|  |  |                                                             |  |  |
|  |  |  [ FastAPI / Uvicorn Server: Port 8000 ]                    |  |  |
|  |  |    ^                                                        |  |  |
|  |  |    |-- ConfigMap (POPUP_BASE_URL, POPUP_APP_MODE...)        |  |  |
|  |  |    |-- Secret (COCKLEBUR_BOOTSTRAP_KEY, POPUP_SECRET_KEY)   |  |  |
|  |  |    |-- Mount: /data -----------------------------------+    |  |  |
|  |  +----+---------------------------------------------------+----+  |  |
|  +-------+---------------------------------------------------+------+  |
|          |                                                   |          |
|          v                                                   v          |
|    +-------------+                                     +-------------+  |
|    | Healthcheck |                                     | PVC: /data  |  |
|    |   /health   |                                     | (10Gi, RWO) |  |
|    +-------------+                                     +------+------+  |
+---------------------------------------------------------------|---------+
                                                                v
                                                    +---------------------+
                                                    | PersistentVolume    |
                                                    | (microk8s / NFS-CSI)|
                                                    +---------------------+
```

---

## 多環境規格矩陣 (Multi-Environment Matrix)

本專案標準化支援四個獨立環境，彼此獨立不共用資源：

| 規格項目 | ENG (開發環境) | UAT (驗收測試) | STG (預發布環境) | PROD (正式生產) |
| :--- | :--- | :--- | :--- | :--- |
| **Namespace** | `cocklebur-app` | `cocklebur-app` | `cocklebur-app` | `cocklebur-app` |
| **Kubectl Context** | `<eng-cluster-context>` | `<uat-cluster-context>` | `<stg-cluster-context>` | `<prod-cluster-context>` |
| **對外網域規範** | `cocklebur-eng.<domain>` | `cocklebur-uat.<domain>` | `cocklebur-stg.<domain>` | `cocklebur.<domain>` |
| **Ingress 類型** | Traefik | Traefik | Ingress-Nginx | Ingress-Nginx |
| **TLS 憑證來源** | 內部自簽 Root CA | 內部自簽 Root CA | Let's Encrypt | Let's Encrypt |
| **TLS Secret 名稱** | `cocklebur-tls-eng` | `cocklebur-tls-uat` | `cocklebur-tls-stg` | `cocklebur-tls-prod` |
| **StorageClass** | HostPath (`microk8s`) | HostPath (`microk8s`) | 網路分散式 (`nfs-csi`)| 高可靠儲存 (`standard`) |
| **PV 容量配額** | 10 GiB | 10 GiB | 10 GiB | 20 GiB |
| **容器映像來源** | `<internal-registry>` | `<internal-registry>` | `<control-registry>` | `<control-registry>` |

---

## 核心亮點

1. **零設定網域同步**：直接改動 `.env` 中的 `POPUP_BASE_URL`，部署機制自動解析出對應 Hostname 並同時更新 Ingress 路由規則與 cert-manager 憑證申請。
2. **雙軌部署工具**：同時支援以 `kustomize` 進行微調宣告式管理，或以 `helm` 進行標準封裝參數化發布。
3. **儲存防鎖定保護**：嚴格鎖定 `replicas: 1` 搭配 `Recreate` 更新策略，徹底杜絕檔案型資料庫在滾動更新時產生的並行讀寫損壞。
4. **安全合規**：全容器以 Non-Root UID 10001 運行，PVC 自動套用權限群組 `fsGroup: 10001`，無需任何特權容器（Privileged Container）。
