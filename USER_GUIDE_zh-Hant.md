# Cocklebur Server 使用指南

## 1. Instance 權限與 Project role 是兩回事

**Instance：** Host、Create projects、Import project packs。  
**Project：** Owner、Member、Viewer。

Owner / Member / Viewer 不會自動取得 Create / Import。

## 2. Host

Host 管理整個 Cocklebur instance，預設永遠有 Create + Import。Host 可在 Projects 頁的 **Instance permissions** 針對既有 project identity，分別開關 Create / Import。

Host 不會自動變成所有 project 的 Owner，也不應被當成能直接閱讀所有 project content 的 universal project role。

## 3. Project roles

- **Owner**：管理 project、invite、roles、recovery、export / close / delete。
- **Member**：一般協作、Cards、replies、uploads。
- **Viewer**：project content 唯讀，但可改自己的 display name。

可以有多個 Owner；最後一個 Owner 不能被降級或刪除。

## 4. Create / Import 額外權限

任何 Owner / Member / Viewer identity 都可以被 Host額外授權：

- **Create projects**：可以建立新 project，建立後自動成為新 project Owner。
- **Import project packs**：可以 import pack，成功後目前 browser 取得 imported project Owner access。

這兩個權限不會改變他在原本 project 的 role。

## 5. Host bootstrap / recovery

第一次由指定 Host 使用 bootstrap key Claim Host。之後 bootstrap key 不再能當 Host 密碼；新的 browser 用 Host recovery code。Recovery 成功後會 rotate code，但不會踢掉其他有效 Host browser session。

Host recovery 與 Project Owner recovery 是兩套不同 scope。
