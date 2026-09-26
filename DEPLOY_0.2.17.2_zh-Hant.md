# Cocklebur Server 0.2.17.2 部署

這版把 Host credential 名稱一次收乾淨。Server mode 只認：

```dotenv
COCKLEBUR_BOOTSTRAP_KEY=<你的長隨機 secret>
```

## 測試環境可砍掉重練

1. 停掉舊 deployment。
2. 刪除 Cocklebur 測試用 `/data` volume/PVC。
3. 設定：

```dotenv
POPUP_APP_MODE=server
COCKLEBUR_BOOTSTRAP_KEY=<你的長隨機 bootstrap key>
```

4. 部署 0.2.17.2。
5. 驗證：

```bash
curl https://YOUR_HOST/health
```

首次應看到 `host_claimed: false`。
6. Browser → **Claim Host** → 輸入 Bootstrap Key。
7. 保存 Cocklebur 顯示的 Host recovery code。
8. 用 private window 測 **Host recovery**；成功後應產生新的 recovery code，舊 code 失效。

## 若未設定 Bootstrap Key

Server 會直接拒絕啟動並顯示：

```text
COCKLEBUR_BOOTSTRAP_KEY is required when POPUP_APP_MODE=server
```

這是刻意設計：Server deployment 必須明確提供 Bootstrap Key。

## Break-glass

```bash
python -m app.admin host-status
python -m app.admin reset-host --yes
```

reset 只清 Host credential，保留 projects 與 delegated instance grants。
