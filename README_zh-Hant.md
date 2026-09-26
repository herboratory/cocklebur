# Cocklebur Server — MVP

**版本：** `0.2.17.2`  
**Project pack format：** `1.0`

Cocklebur Server 是一個輕量、可自行部署的 project workspace。核心原則是：**一個 project 同時間只有一份 canonical live copy**；大家在同一個 server project 上工作，結束時可以把整個 project 匯出成可攜 ZIP 帶走。

這個壓縮包是 **Server 發布版**，已移除 Local / pywebview / Tauri desktop build 工具，以及 H2～H16 等舊驗收與 hotfix 文件。

Cocklebur 用於 **個人、學術/研究、教學/教育、非商業社群**情境；不授予商業使用權，詳見 `LICENSE`。

## 核心設計

- 一個 project 只有一份 active canonical server copy。
- 資料使用 JSON / JSONL + 原始 files，並非綁死在 proprietary database。
- 不做 CRDT、offline multi-master sync 或 silent auto-merge。
- 可變更資料有 version；拿舊版本 Save 時回 HTTP `409`，不會偷偷覆蓋較新的內容。
- Export 會做一致性 snapshot，包含 machine-readable data、human-readable text 與原始 files。
- Server 必須維持 **單一 application worker**。

## Docker 快速啟動

```bash
cp .env.example .env
```

本機測試可先維持：

```dotenv
POPUP_APP_MODE=server
POPUP_DATA_DIR=/data
POPUP_HOST_PORT=8000
POPUP_BASE_URL=http://127.0.0.1:8000
```

穩定部署建議設定一組長而隨機、僅用於首次 Claim Host 的 bootstrap key：

```dotenv
COCKLEBUR_BOOTSTRAP_KEY=換成你自己的長隨機secret
```

啟動：

```bash
docker compose up -d --build
curl http://127.0.0.1:8000/health
```

本機測試開 `http://127.0.0.1:8000`。若要公開到 Internet，保留 Cocklebur 只 bind localhost，前面再放 HTTPS reverse proxy / tunnel。詳細看 `DEPLOY_SERVER.md`。

## 權限模型

Cocklebur 把 **Server Host** 和 **project role** 分開：

- **Host**：可在這個 Cocklebur instance 建立 / Import project。
- **Owner**：管理某個 project、邀請、角色、recovery、export / close / delete。
- **Member**：正常協作。
- **Viewer**：project 內容唯讀；仍可修改自己的 display name。

Project Owner / Member / Viewer 並不會因此取得 Host 權限。

## 主要功能

### Cards
- To-do / Event。
- Pending / In Progress / Done / Archived。
- Markdown、tags、assignees、checklist、日期與 Event `.ics`。
- **Visibility：** `Everyone` / `Only me`。
- **Edit access：** Shared / creator-only。
- Assignee 只代表責任歸屬，不控制權限。
- To-do / Event 都只有原 creator 能 Delete。
- Card 內會顯示人類可讀的 activity，例如 `Bob completed “Book venue”`，不會把 `card.created` 這種 backend key 直接丟給使用者。

### Announcements / Discussion / Files
- Project announcements。
- Channels、帶標題的 threads、replies，以及依角色/人員控制 channel visibility。
- File upload/download、metadata、size/quota、SHA-256 與 Card links。

### Recovery
- Owner 可為既有 collaborator 產生一次性 recovery link。
- GET 打開 recovery link 只會進確認頁；真正確認 recovery 時才 consume token，避免 preview/prefetch 把 link 吃掉。
- Recovery 會恢復原 identity，**不會踢掉其他仍然有效的 browser sessions**。
- Owner 另有 break-glass recovery code；成功使用後會 rotate 成新 code。

## 資料與隱私

Self-hosted Cocklebur 不要求把 project data 放到軟體作者營運的中央資料服務；資料由部署者自己控制 storage。這只是技術架構描述，不代表部署者沒有隱私、安全或法律責任。

Internet-facing deployment 請：

- 使用 HTTPS；
- 維持單一 app worker；
- 不要把 raw Docker port 直接公開到 Internet；
- 備份 persistent volume；
- 保護 Host bootstrap key、Host recovery code、invite link、recovery link 與 Owner recovery code。

## 文件

- `DEPLOY_SERVER.md` — Server 部署、乾淨重建、tunnel、Host access
- `USER_GUIDE.md` / `USER_GUIDE_zh-Hant.md` — 使用方法
- `BACKUP_RESTORE.md` — 備份 / 還原
- `UPDATE.md` — 安全更新
- `EXPORT_FORMAT.md` — project pack 格式
- `SECURITY.md` — security model
- `RELEASE.md` — release metadata / limitations
- `CHANGELOG.md` — 歷史變更
- `LICENSE` — license

## Package sanity check

```bash
python scripts/package_guard.py
```

它會檢查 Server 發布必需檔案、拒絕 runtime secrets / project data / cache，並在工具可用時做 Python / JavaScript syntax validation。


## Server 0.2.17.2

Adds Workspace Bundle export/import, Note Cards, retry-safe Card creation, New Project spacing polish, and Host-only data-safe Update Center staging. Host access uses a single explicit Bootstrap Key for first claim, browser Host sessions for normal use, and rotating Host recovery codes for recovery. Project Pack format remains 1.0.
