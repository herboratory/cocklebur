# 設定檔與機密管理 (Configuration & Secrets)

本文件詳細說明 Cocklebur Server 的環境變數架構、網域自動解析機制、以及應用程式金鑰的生命週期管理。

---

## 1. 環境變數單一真實來源 (Single Source of Truth)

為了避免在 Docker Compose、Kubernetes ConfigMap、Helm Values 以及 Ingress YAML 中重複定義相同的網域與金鑰，本專案採用 **`.env` 作為核心真實來源**。

### 1.1 設定檔優先級 (Lookup Precedence)
部署工具尋找設定檔的順序如下：
1. **環境專屬檔案**：`deploy/k8s/overlays/<env>/.env`（若存在則優先採用）
2. **專案全域檔案**：專案根目錄 `.env`（預設讀取此檔案）

### 1.2 變數參考規格表

| 變數名稱 | 預設值 | 存放載體 | 說明 |
| :--- | :--- | :--- | :--- |
| `POPUP_APP_MODE` | `server` | ConfigMap | 執行模式，固定為 `server` |
| `POPUP_DATA_DIR` | `/data` | ConfigMap | 持久化資料儲存目錄，對應 PV 掛載點 |
| `POPUP_BASE_URL` | `https://cocklebur.example.com` | ConfigMap | 外部存取之絕對路徑，用於邀請連結與 QR Code 生成 |
| `POPUP_MAX_UPLOAD_MB`| `50` | ConfigMap | 單一檔案上傳上限 (MB) |
| `POPUP_IMPORT_MAX_MB`| `2048` | ConfigMap | 專案打包檔匯入上限 (MB) |
| `POPUP_PROJECT_QUOTA_MB` | `1024` | ConfigMap | 單一專案之存儲配額上限 (MB) |
| `COCKLEBUR_BOOTSTRAP_KEY` | *(隨機產生)* | Secret | 首次認領實例主機權限（Host Claim）之一次性金鑰 |
| `COCKLEBUR_HOST_KEY` | *(相容別名)* | Secret | 同上，舊版別名相容變數 |
| `POPUP_SECRET_KEY` | *(隨機產生)* | Secret | Cookie 簽署與 Session 加密之金鑰 |

---

## 2. 網域自動提取與同步機制 (Dynamic Domain Sync)

### 2.1 運作邏輯
以往在 K8s 部署中，變更網域需要同時修改：
1. Pod 的環境變數 `POPUP_BASE_URL`
2. Ingress 的 `spec.rules[*].host`
3. Ingress 的 `spec.tls[*].hosts`
4. cert-manager Certificate 的 `spec.dnsNames`

在 Cocklebur 的自動化部署機制中，您**只需要在 `.env` 中更新一行**：
```ini
POPUP_BASE_URL=https://cocklebur-eng.example.com
```

### 2.2 流程圖解
```
[ 編輯 .env 檔案 ]
  POPUP_BASE_URL=https://cocklebur-eng.example.com
         |
         v
[ 執行 deploy.sh ]
         |
         +--> 1. URL 解析器提取 Hostname: "cocklebur-eng.example.com"
         |
         +--> 2. 同步注入 ConfigMap: POPUP_BASE_URL
         |
         +--> 3. 同步注入 Ingress: rules[0].host, tls[0].hosts
         |
         +--> 4. 同步注入 Certificate: dnsNames[0]
```
- 若未在 `.env` 設定，系統會自動 fallback 至該環境的預設網域。
- 若需臨時覆蓋，可直接於命令列宣告：`DOMAIN="custom.example.com" ./deploy/scripts/deploy.sh eng`。

---

## 3. 機密金鑰管理與 Bootstrap Key 生命週期

### 3.1 Bootstrap Key 核心概念
`COCKLEBUR_BOOTSTRAP_KEY` 是一組**一次性初始化金鑰**，其職責是讓系統管理員在首次部署後，安全地認領（Claim）為 Cocklebur 的系統 Host。

> [!IMPORTANT]
> **金鑰生命週期規則**：
> 1. 當 Deployer 部署完畢後，開啟網頁點擊 **Claim Host**。
> 2. 輸入 Bootstrap Key 並為 Host 命名。
> 3. Cocklebur 會在瀏覽器植入 HttpOnly Session Cookie，並在畫面上顯示一組 **Host Recovery Code**。
> 4. **在此之後，Bootstrap Key 立即永久失效**，無法再次用於登入。日後若更換瀏覽器或遺失 Session，必須使用 Host Recovery Code 進行身分復原。

### 3.2 基礎架構管理者 vs 應用程式 Host 之職責分離
在許多企業情境中，負責 K8s 部署的維運工程師（Infrastructure Deployer）與實際使用 Cocklebur 的組織管理者（Host）並非同一人：
- 維運人員在 CI/CD 中產生或注入 `COCKLEBUR_BOOTSTRAP_KEY`。
- 部署完成後，維運人員將這組一次性 Key 移交給業務負責人。
- 業務負責人連上網頁點擊 Claim Host，並自行保管 Recovery Code。
- 維運人員無法透過該 Key 登入應用程式查看業務資料（但具備基礎設施 root 權限）。

---

## 4. CI/CD Pipeline 整合範例

在自動化 Pipeline 中，機密金鑰不應寫死在 Git 倉庫內。以下以常見 CI/CD 平台示範如何注入：

### 4.1 GitLab CI 範例
在 GitLab 專案 Settings $\rightarrow$ CI/CD $\rightarrow$ Variables 中定義 `PROD_BOOTSTRAP_KEY` 與 `PROD_SECRET_KEY`（設為 Masked）：

```yaml
deploy_prod:
  stage: deploy
  image: bitnami/kubectl:latest
  script:
    - kubectl config use-context <prod-context>
    - kubectl create namespace cocklebur-app --dry-run=client -o yaml | kubectl apply -f -
    - |
      kubectl create secret generic cocklebur-secrets \
        --namespace=cocklebur-app \
        --from-literal=COCKLEBUR_BOOTSTRAP_KEY="$PROD_BOOTSTRAP_KEY" \
        --from-literal=POPUP_SECRET_KEY="$PROD_SECRET_KEY" \
        --dry-run=client -o yaml | kubectl apply -f -
    - kubectl apply -k deploy/k8s/overlays/prod
```

### 4.2 GitHub Actions 範例
透過 GitHub Secrets 注入：
```yaml
- name: Deploy to Kubernetes
  run: |
    kubectl create secret generic cocklebur-secrets \
      --namespace=cocklebur-app \
      --from-literal=COCKLEBUR_BOOTSTRAP_KEY="${{ secrets.COCKLEBUR_BOOTSTRAP_KEY }}" \
      --from-literal=POPUP_SECRET_KEY="${{ secrets.POPUP_SECRET_KEY }}" \
      --dry-run=client -o yaml | kubectl apply -f -
    kubectl apply -k deploy/k8s/overlays/stg
```
