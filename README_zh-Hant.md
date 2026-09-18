# Cocklebur Server

**版本：** `0.2.16`  
**Project pack format：** `1.0`

Cocklebur Server 是一個輕量、self-hosted 的專案工作空間：一個 project 維持一份 canonical live copy，專案結束後可以把整包資料 export 帶走。

這個 archive 是 **Server distribution**，不包含 Desktop build tooling。

## 核心模型

- 每個 active project 一份 canonical server copy。
- JSON / JSONL + 原始 files 作為資料本體。
- 不做 CRDT、offline multi-master sync 或偷偷 merge。
- Stale write 回 HTTP `409`。
- Export 同時包含 machine-readable data、human-readable text 與原始 files。
- Server 必須只跑 **一個 application worker**。

## Docker 快速開始

```bash
cp .env.example .env
```

本機測試可設定：

```dotenv
POPUP_APP_MODE=server
POPUP_DATA_DIR=/data
POPUP_HOST_PORT=8000
POPUP_BASE_URL=http://127.0.0.1:8000
COCKLEBUR_BOOTSTRAP_KEY=換成一個夠長的隨機 secret
```

舊的 `COCKLEBUR_HOST_KEY` 名稱仍相容，會被當成 bootstrap key。

啟動：

```bash
docker compose up -d --build
curl http://127.0.0.1:8000/health
```

## 權限模型

Cocklebur 把 infrastructure、instance 與 project 三個層級分開：

- **Infrastructure Admin / Deployer**：管理主機、Docker、storage、backup、network；這不是 Cocklebur app role。
- **Host**：管理整個 Cocklebur instance。
- **Owner**：管理某一個 project。
- **Member**：一般 project 協作。
- **Viewer**：project content 唯讀，但可改自己的 display name。

另外，某個既有 project identity 可以被 Host 額外授權：

- **Create projects**：可建立新 project；建立後自動成為該 project Owner。
- **Import project packs**：可 import project pack；成功後取得 imported project 的 Owner access。

Owner / Member / Viewer 本身不會自動得到 Create / Import。

### Host bootstrap 與 recovery

`COCKLEBUR_BOOTSTRAP_KEY` 是一次性的 bootstrap credential。指定的 Host 第一次在 Projects 頁按 **Claim Host**，輸入 bootstrap key 後，Cocklebur 會把真正的 Host state 寫進 persistent `/data`，並顯示 Host recovery code。

完成 claim 後，bootstrap key **不再是 Host 登入密碼**。新的 browser 必須用目前的 Host recovery code；成功 recovery 後舊 Host browser session 不會被踢掉，但 recovery code 會 rotate。

Infrastructure Admin 仍然掌握底層 server/storage，因此技術上始終能讀、改、刪 self-hosted data。Cocklebur 的 app 權限不會假裝能限制 server root/admin。

## 主要功能

- Projects + expected end date
- Dashboard / announcements
- To-do / Event Cards
- Checklist、tags、assignees、visibility、edit access
- Discussion channels + titled threads
- Project files
- Owner / Member / Viewer
- Invitation / recovery
- Instance-level Create / Import delegation
- Portable project export / import

公開到 Internet 時請使用 HTTPS、保留 persistent volume、只跑一個 worker，並保護 bootstrap/recovery credential、invite links 與 Owner recovery codes。
