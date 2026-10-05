# Cocklebur Server 0.2.18.1 驗收

## Host

- [ ] Fresh Claim Host 成功。
- [ ] Host recovery 成功且 recovery code rotation。
- [ ] Host → Manage Host devices 可看到 Current device。
- [ ] Add another Host device 產生 one-time link + QR。
- [ ] 第二 browser 成為同一 Host；第一 browser 不被登出。
- [ ] Add device 不會使既有 Host recovery code失效。
- [ ] 可單獨 revoke 非 current Host device。

## Project identity

- [ ] Owner / Member / Viewer 均可從 Your profile → Manage devices。
- [ ] Add another device 產生 10 分鐘 one-time link + QR。
- [ ] 新 browser 使用同一 `person_id` 與 role。
- [ ] People list 不增加新 member。
- [ ] 舊 browser 保持有效。
- [ ] link 第二次使用失敗。
- [ ] 可單獨 revoke 非 current device。
- [ ] current device 無法 revoke 自己。
- [ ] Invite 仍建立新的 person，而不是 link existing identity。

## Upgrade

- [ ] 0.2.17.x access-hash-only browser session 升級後仍有效。
- [ ] 舊 session 在 Devices 顯示為 legacy session。
- [ ] 0.2.16+ Host recovery state 仍可 recover。

## Existing features

- [ ] Note Card。
- [ ] Card Saving… / idempotency。
- [ ] Workspace Bundle export/import。
- [ ] Update Center 可 Validate & stage。
- [ ] Managed deployment 顯示 Apply update。
- [ ] Apply 後 `/health` 版本切換到 target。
- [ ] 故障 target 會自動回退上一個可用 release。
- [ ] Project Pack format 仍為 1.0。
