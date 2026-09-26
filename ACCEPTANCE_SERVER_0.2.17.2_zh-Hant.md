# Cocklebur Server 0.2.17.2 人工驗收

## 0. Host lifecycle / recovery hotfix

1. 使用全新 `/data` 啟動，`GET /health` 應顯示 `host_claimed: false`。
2. 首次按 **Claim Host**，使用 `COCKLEBUR_BOOTSTRAP_KEY` 成功後必須顯示 Host recovery code。
3. 清除 browser cookies 或換一個乾淨 browser 後，Host 按鈕應顯示 **Host recovery**，bootstrap key 不再被接受。
4. 使用剛保存的 Host recovery code 應恢復 Host access，並立即產生一個新的 recovery code；舊 code 必須失效。
5. 從 0.2.16 保留 `.instance_auth.json` 升級到 0.2.17.2 時，既有 current recovery code 應仍可使用。
6. 若 Host session 與 recovery code 都遺失，infra admin 可執行：
   `python -m app.admin reset-host --yes`
   它必須先 backup `.instance_auth.json`，只清 Host claim，保留 projects 與 instance grants。

## A. New Project spacing

1. 打開 New project。
2. 確認 Project name 輸入框與 Description label 之間有明顯約 12px 垂直間距，不再黏在一起。

## B. Card Save 防重送

1. 新增 To-do。
2. 按 Save 後，按鈕應立即 disabled 並顯示 `Saving…`。
3. 慢網路下不要產生重複 Card；若 30 秒無法確認，畫面提示可安全 retry。
4. retry 同一次 create 不應多生一張 Card。

## C. Note

1. Cards → `+`。
2. 確認 `To-do / Event / Note` 三個 type 位於同一行。
3. 選 Note：不顯示 task status、assignee、event start/end；保留 Edit access、Visibility、Tags、Content。
4. Save 後 Card badge 顯示 Note，沒有 task status badge。
5. 編輯 Note 可 Archive / Restore。
6. Export Project Pack 後應有 `readable/notes.txt`，canonical JSON 仍在 `data/cards/`。

## D. Workspace Bundle

1. Projects 首頁按 `Export accessible`。
2. ZIP 應有 `bundle-manifest.json`、`checksums.json`、`projects/p_....zip`。
3. Bundle 只包含目前 browser 擁有 Owner/Member project access 的 projects；Host 身分本身不應繞過 project access。

## E. Multi-import / Workspace Bundle import

1. Projects → Import，一次選多個 Project Pack，或選 Workspace Bundle。
2. 先看到 preflight：Ready / Duplicate ID / Invalid pack / Incompatible version。
3. Duplicate 可選 Skip 或 Import as new project IDs。
4. Import 後保存每個新的 Owner recovery code。

## F. Update Center foundation

1. Host access 後打開 Update center。
2. 上傳符合 `UPDATE_PACKAGE_FORMAT.md` 的 ZIP。
3. 預期顯示 current / target / minimum source version。
4. staging 成功後應顯示 backup path 與 stage path。
5. 此時 application version **不應自動改變**，server 不應自動 restart。
6. `POPUP_DATA_DIR/.update_backups/` 應出現 pre-update `.tar.gz`。
7. Clear staged update 應移除 staged payload，但保留已建立的 data backup。
8. 含 `data/`、`.env`、未列入 checksums 的 payload file、checksum 錯誤或 incompatible version 的 update ZIP 都必須拒絕。

## G. Regression

- Create / Import Project
- Owner / Member / Viewer
- Invite / Recovery
- To-do / Event create/edit/delete
- Announcements / Discussion / Files
- single Project Pack export/import
- archive / close / delete lifecycle

## Credential naming cleanup

- Server mode 只設定 `COCKLEBUR_BOOTSTRAP_KEY` 可正常啟動。
- 兩者都沒設定必須啟動失敗。
