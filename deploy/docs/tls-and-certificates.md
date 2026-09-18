# TLS 憑證與自動展延機制 (TLS & Certificates)

本文件深入探討 Cocklebur Server 在 Kubernetes 上的 TLS 憑證管理架構、cert-manager 整合實務以及跨命名空間安全規範。

---

## 1. Kubernetes Ingress 的命名空間隔離限制

在設計 Kubernetes Ingress 時，常見一個疑問：
> *「叢集中既有的 TLS 憑證存放在 `cert-management` 命名空間，專案能否直接重用該 Secret？」*

### 核心限制 (Namespace Isolation)
**答案是：標準 Ingress 控制器嚴禁跨 Namespace 讀取 Secret。**
- Kubernetes 官方的 Ingress 規範與絕大多數 Ingress 控制器（包括 Ingress-Nginx、Traefik、HAProxy）均嚴格規定：**`spec.tls[*].secretName` 所指向的 Secret，必須與 Ingress 資源位於同一個 Namespace 內**。
- 若在 `cocklebur-app` 命名空間的 Ingress 中填入 `cert-management` 下的 Secret，控制器會因存取權限受限或找不到資源，直接拋出錯誤並降級為使用預設自簽假憑證（Fake Certificate）。

---

## 2. 解決架構：基於 cert-manager 的就地自動簽發

為了既滿足安全規範、又能重用叢集既有的 CA / Let's Encrypt 帳號，我們採用了 **cert-manager 的 `Certificate` 宣告模式**：

```
+--------------------------------------------------------------------+
| 叢集層級 (Cluster Scope)                                           |
|                                                                    |
|  [ ClusterIssuer: internal-ca-issuer ]  [ ClusterIssuer: letsencrypt-prod ]
|         (內網自簽 CA 根金鑰)                   (外網 ACME HTTP-01)          |
+--------------------------------------------------------------------+
                             |                            |
                             +-------------+--------------+
                                           | (簽署憑證)
                                           v
+--------------------------------------------------------------------+
| 專案命名空間: cocklebur-app                                         |
|                                                                    |
|   1. 宣告 Certificate (cocklebur-certificate)                      |
|          |                                                         |
|          v (自動產生 / 定期展延)                                    |
|   2. Secret: cocklebur-tls-<env>                                   |
|          ^                                                         |
|          | (同 Namespace 內直接掛載)                                |
|   3. Ingress (cocklebur-ingress)                                   |
+--------------------------------------------------------------------+
```

### 優勢
1. **命名空間合規**：憑證 Secret（`cocklebur-tls-<env>`）直接生成在 `cocklebur-app` 下，Ingress 能直接無障礙綁定。
2. **免手動複製**：無需部署複雜的跨 Namespace Secret 複製器（如 Reflector、kubed）。
3. **全自動展延 (Auto-renewal)**：cert-manager 會在憑證到期前 30 天自動重新簽發，並平滑重寫 Secret，Ingress 控制器會自動熱載入（Hot Reload），全程零停機、零人工介入。

---

## 3. 多環境簽發策略 (Environment CA Strategy)

### 3.1 ENG / UAT 環境：內部自簽 CA (`internal-ca-issuer`)
- **使用場景**：內網環境無法連通公網，或使用內部自訂網域（如 `.internal`），無法通過公網 ACME HTTP-01 挑戰。
- **簽發方式**：引用 cert-manager 命名空間中的自簽 Root CA Secret（`internal-ca-secret`）。
- **ClusterIssuer 設定**（已納入部署模板）：
  ```yaml
  apiVersion: cert-manager.io/v1
  kind: ClusterIssuer
  metadata:
    name: internal-ca-issuer
  spec:
    ca:
      secretName: internal-ca-secret
  ```

### 3.2 STG / PROD 環境：公網 Let's Encrypt (`letsencrypt-prod`)
- **使用場景**：對外提供服務的正式網域，需取得公認受信任之免費 SSL 憑證。
- **簽發方式**：透過 ACME 自動進行 HTTP-01 挑戰，Ingress 控制器配合建立臨時 Solver 路由完成驗證。
- **Certificate 宣告範例**：
  ```yaml
  apiVersion: cert-manager.io/v1
  kind: Certificate
  metadata:
    name: cocklebur-certificate
    namespace: cocklebur-app
  spec:
    secretName: cocklebur-tls-stg
    issuerRef:
      name: letsencrypt-prod
      kind: ClusterIssuer
    dnsNames:
      - cocklebur-stg.example.com
  ```

---

## 4. 憑證除錯與狀態檢驗指引

若 Ingress 未能正常提供 HTTPS，可依序執行以下診斷命令：

### 步驟 1：檢查 Certificate 狀態
```bash
kubectl get certificate -n cocklebur-app
```
*預期輸出：*
```text
NAME                    READY   SECRET               AGE
cocklebur-certificate   True    cocklebur-tls-eng    5m
```

### 步驟 2：若 READY 為 False，檢查詳細原因
```bash
kubectl describe certificate cocklebur-certificate -n cocklebur-app
```
查看最下方的 `Events` 與 `Status.Conditions`。常見原因：
- DNS 尚未解析至叢集節點 IP。
- Ingress 控制器防火牆阻擋 80 端口（ACME HTTP-01 挑戰需要 80 端口）。

### 步驟 3：檢查 CertificateRequest 與 ACME Order (針對 Let's Encrypt)
```bash
kubectl get certificaterequest,order,challenge -n cocklebur-app
```
若有卡住的 Challenge，可執行：
```bash
kubectl describe challenge <challenge-name> -n cocklebur-app
```
查看 Let's Encrypt 回應的錯誤訊息（例如 Connection refused 或 DNS NXDOMAIN）。
