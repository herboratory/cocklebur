# Cocklebur Server 0.2.16 — Instance Auth 人工驗收

這包主要驗收 **Infrastructure / Host / Project role 分層**，以及 **Create / Import 額外 instance permission**。

## A. 全新 instance

1. 準備 `.env`：

```dotenv
POPUP_APP_MODE=server
POPUP_DATA_DIR=/data
POPUP_HOST_PORT=8000
POPUP_BASE_URL=http://127.0.0.1:8000
COCKLEBUR_BOOTSTRAP_KEY=請換成隨機secret
```

2. 啟動：

```bash
docker compose up -d --build
```

3. 打開 Projects 首頁。

預期：

- 顯示 **Claim Host**，不是已登入 Host。
- New project / Import pack 尚未顯示。
- `/health` 顯示 `host_claimed: false`。

## B. Claim Host

1. 按 **Claim Host**。
2. 輸入 Host display name + bootstrap key。
3. 保存 Host recovery code。

預期：

- Projects 頁顯示 `Host access ✓`。
- New project / Import pack 出現。
- **Instance permissions** 出現。
- `/health` 顯示 `host_claimed: true`。

## C. Bootstrap key 必須變成一次性

用另一個 browser / private window：

- 再用同一 bootstrap key 嘗試 Claim Host。

預期：被拒絕，提示 instance 已有 Host，必須用 Host recovery。

## D. Host recovery

在第二個 browser：

1. 按 **Host recovery**。
2. 輸入剛保存的 Host recovery code。

預期：

- 第二個 browser 取得 Host access。
- 顯示新的 Host recovery code。
- 舊 recovery code 失效。
- 第一個 browser 的 Host session **仍然有效**。

## E. Host != Project Owner

1. 第一個 Host browser 建一個 Project A。
2. 第二個 Host browser（只有 Host recovery，沒有 Project A cookie）直接開 Project A。

預期：

- 第二個 browser **不能因為是 Host 就直接取得 Project A Owner access**。
- Host scope 與 Project Owner scope 分開。

## F. Member + Create

1. Project A Owner 產生 invite。
2. 第三個 browser 加入成 Member。
3. Host 在首頁打開 **Instance permissions**。
4. 找到這個 Member identity，只勾 **Create**，不要勾 Import。

Member browser 回 Projects 頁後預期：

- New project 出現。
- Import pack 不出現。
- Project A 裡仍然是 Member，不會變 Host / Owner。

Member 建立 Project B：

- 成功。
- Member 在 Project B 自動成為 Owner。
- 在 Project A 仍是 Member。

## G. Create / Import 必須可獨立授權

Host 再把同一 identity 的 **Import** 打開。

預期：

- Import pack 出現。
- Create / Import 可以獨立開關。
- 開關不改變原 project role。

## H. 移除 identity 後 grant 失效

Project A Owner 將該 Member 從 Project A 移除。

預期：

- 由 Project A identity 掛載的 Create / Import instance grant 一起失效。
- 這不影響他已經擁有的 Project B Owner identity。

## I. Upgrade from 0.2.15

若 `/data` 已有舊 project，但沒有 `.instance_auth.json`：

1. 更新 code，不刪 volume。
2. 啟動 0.2.16。
3. 用原本的 `COCKLEBUR_HOST_KEY`（或新 `COCKLEBUR_BOOTSTRAP_KEY`）做一次 **Claim Host**。
4. 保存新的 Host recovery code。

預期：舊 project 保留；pack format 仍為 1.0。

## J. 基本 regression

- Project Create / Import
- Invite / QR
- Owner / Member / Viewer role change
- Member/Owner recovery
- Cards visibility/edit/delete rules
- Discussion / Files
- Export / Import

都應維持正常。
