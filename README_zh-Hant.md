# Cocklebur

**輕量、可攜的專案工作空間。Local 落地，結束時整包帶走。**

Cocklebur 是以「專案」為核心的輕量工作空間。你可以在 macOS 本機單人使用，也可以自行部署 Server 版讓小型團隊共同使用同一份 canonical project。專案結束後，可以把整個工作空間匯出成可攜式 project pack。

**目前版本：** `0.2.15`

[English](README.md)

## 下載

預先建置好的版本都放在 [GitHub Releases](https://github.com/herboratory/cocklebur/releases/latest)：

- **macOS Desktop** — 下載 `.dmg`
- **Self-hosted Server** — 下載 Server `.zip`

這個 repository 本身刻意保持精簡，主要作為 Cocklebur 的公開下載入口、說明、issue 回報與專案資訊頁。

## macOS Desktop

Cocklebur Desktop 是 local-only、單人使用版本。除非你主動匯出，project data 都留在你的 Mac 上。

### macOS 第一次開啟

目前 macOS 版本**尚未使用 Apple Developer ID 簽署，也未 notarize**，所以第一次開啟時 macOS 可能會阻擋。

1. 先嘗試開啟 Cocklebur 一次。
2. 打開 **System Settings → Privacy & Security**。
3. 往下找到 Cocklebur，按 **Open Anyway**。
4. 再確認 **Open**。

通常每一份 app 只需要做一次。

如果 macOS 顯示 app damaged，請先確認是從 Cocklebur 官方 GitHub Release 下載，並核對 checksum。若確認檔案正常，進階使用者可移除 quarantine attribute：

```bash
xattr -cr /Applications/Cocklebur.app
```

## Self-hosted Server

Server 版適合需要多人共同使用同一份 project workspace 的小型團隊。

下載並解壓 Server package 後：

```bash
cp .env.example .env
```

至少設定：

```dotenv
COCKLEBUR_HOST_KEY=請換成足夠長的隨機密鑰
POPUP_APP_MODE=server
POPUP_DATA_DIR=/data
POPUP_BASE_URL=https://你的-cocklebur-網址
```

然後啟動：

```bash
docker compose up -d --build
```

Server 版預期放在你自己的 HTTPS reverse proxy 或 tunnel 後方。不要把 Cocklebur 的 plain HTTP port 直接暴露到公網。

## 主要功能

- Projects 與 optional expected end date
- Dashboard
- Announcements
- To-do / Event Cards
- Checklist、tag、assignee
- Discussion channels 與有標題的 threads
- Project files
- Server mode 的 Owner / Member / Viewer
- Invitation / recovery links
- Activity history
- Project export / import
- Human-readable + machine-readable portable project packs

Cocklebur 刻意不做 offline multi-master sync，也不做 Google Docs 式即時多人共同編輯。同一個 project 永遠以一份 canonical active copy 為準。

## Portable by design

Project 可以完整匯出，內容包括 structured project data、human-readable material、checksums 與原始 files；之後可以重新匯入 Cocklebur。

## Privacy

Cocklebur 是 local / self-hosted 軟體。Herboratory 不提供中央 Cocklebur project-data service。

但 self-hosting 仍代表機器或 server 管理者能直接存取底層檔案；app 裡的 visibility control 並不是 filesystem encryption。

## 支持開發

Cocklebur 是 **Herboratory** 的專案。

如果 Cocklebur 對你有幫助，可以透過 Buy Me a Coffee 支持 Herboratory 持續開發與維護各個專案：

<a href="https://www.buymeacoffee.com/herboratory">
  <img
    src="https://cdn.buymeacoffee.com/buttons/v2/default-yellow.png"
    alt="Buy Me a Coffee"
    height="60"
    width="217"
  >
</a>

## License

Cocklebur 採用 **PolyForm Noncommercial License 1.0.0**。目前不授予商業使用權。

詳見 [LICENSE](LICENSE)。
