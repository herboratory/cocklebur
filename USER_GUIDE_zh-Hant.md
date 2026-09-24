# Cocklebur Server 使用指南

## 1. Projects 與 Host access

Server Host 控制這個 Cocklebur instance 能不能 New Project / Import Pack。Project 的 Owner / Member / Viewer 身分不等於 Host 權限。

取得 Host access 後，才從 Projects 頁建立或匯入 project。

## 2. Project roles

- **Owner**：project 管理、邀請、roles、recovery、export / close / delete。
- **Member**：一般內容協作、Discussion reply、upload。
- **Viewer**：project 內容唯讀；仍可修改自己的 display name。

一個 project 可以有多個 Owner；最後一位 Owner 不能被 demote / remove。

## 3. Cards

Card 分為 To-do / Event，可包含 status、日期、assignees、tags、Markdown 與 checklist。

### Visibility

- **Everyone**：project 內有權看到內容的人都看得到。
- **Only me**：只有 Card creator 看得到。

### Edit access

- **Shared**：能看到這張 Card 的 Owner / Member 可共同 edit。
- **Creator only**：只有 Card creator 能 edit。

Assignee 只表示責任歸屬，不控制 visibility / edit permission。

To-do / Event 都只有原 creator 能 Delete。

Card Activity 會用人話記錄「誰做了什麼」，例如完成/重開 checklist、修改內容、status 或 schedule。

## 4. Announcements

用於 project-wide 的重要公告。

## 5. Discussion

Discussion 有 channels、帶標題的 threads 與 replies。Owner 可依 everyone / roles / specific people 設定 channel visibility。Member 可在有權限的 channel 發言；Viewer 唯讀。

## 6. Files

可 upload / download 原始 files，並附 metadata / Card links。Cocklebur 會檢查單檔大小、project quota，並記錄 SHA-256 digest。

資料夾或 macOS `.app` bundle 請先壓成 ZIP 再 upload。

## 7. Invitations

Owner 產生 invite link / QR。對方開啟後輸入 display name（以及 optional PIN），browser 取得 project-scoped credential。

Invite link 不是長期登入憑證。

## 8. Recovery

若 collaborator 遺失 browser access，Owner 可針對原本 identity 產生一次性 recovery link。

打開 link 時先進 confirmation page；真正確認 recovery 時才 consume token，因此 link preview / prefetch 不會先把 token 吃掉。

Recovery 會恢復原 identity，**不會讓其他仍有效的 browser session 失效**。

Owner 另有 break-glass Owner recovery code。成功 recovery 後 code 會 rotate，請保存新 code。

## 9. Conflict

兩個人若基於同一個舊 version 同時修改，同步較晚的 stale save 會收到 conflict，而不是偷偷蓋掉較新的內容。

## 10. Export

**Export current state** 會建立一致性 ZIP snapshot：

- `data/` — machine-readable project state
- `readable/` — human-readable text
- `files/` — 原始 uploads

任何時候都可以 Export。

## 11. Closing

Owner 可 review project、Export current state，之後 Archive 或 Delete canonical server copy。Permanent delete 前必須已有 current export。

## 12. Restore

取得 Host access 後，在 Projects 使用 **Import pack**。Cocklebur 會先驗證 pack；成功後 importing browser 直接取得 Owner access，並顯示新的 Owner recovery code。

如果同一 project ID 已存在，Import 會拒絕，不會默默做出第二份 writable copy。
