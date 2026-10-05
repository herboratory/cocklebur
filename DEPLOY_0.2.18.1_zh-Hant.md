# Cocklebur Server 0.2.18.1 部署 / 升級

0.2.18.1 延續 0.2.17.2 的 Host credential model；Server mode 仍只認：

```dotenv
COCKLEBUR_BOOTSTRAP_KEY=<你的長隨機 secret>
```


## 這次是最後一次需要手動 deploy updater baseline

0.2.17.2 本身沒有 updater supervisor，所以單靠 update ZIP 無法讓舊 process 突然具備 Apply/restart 能力。從 0.2.17.2 升到 0.2.18.1 時，保留 `/data`，由部署者正常替換 image/source 一次。

0.2.18.1 標準 Docker image 啟動後，Update Center 會顯示 **Managed updates enabled**。之後 `requirements.txt` 沒變的相容 runtime update 可以直接在頁面：

```text
Validate & stage → Apply update → restart → /health → success / rollback
```

## 從 0.2.17.2 升級

保留原本 `/data` volume/PVC，替換 application image/source 後重啟即可。既有 Host state、project identities、browser access token 都會繼續有效。

升級後：

```bash
curl https://YOUR_HOST/health
```

應看到：

```json
{"status":"ok","version":"0.2.18.1","mode":"server",...}
```

## Multi-device 驗收

1. 在電腦 browser 進 project → **Your profile → Manage devices**。
2. 按 **Add another device**。
3. 手機掃 QR 或打開 one-time link。
4. 手機確認 device name。
5. 電腦與手機應同時保持同一個 `person_id` / role。
6. People list 不應因此多出一個 member。
7. 電腦可在 Manage devices revoke 手機 session；revoke 後手機應失去該 project access。

Host 也可在 **Host access → Manage Host devices** 做同樣測試；Add device 不應 rotation Host recovery code。

## Break-glass Host recovery

若 Host session 與 recovery code 都不可用：

```bash
python -m app.admin host-status
python -m app.admin reset-host --yes
```

reset 只清 Host claim，保留 projects 與 delegated instance grants；之後再用 `COCKLEBUR_BOOTSTRAP_KEY` Claim Host。
