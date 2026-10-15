# Memorama 翻牌記憶

> 中文物品詞彙的翻牌記憶遊戲，含排行榜

- **網址：** https://wangchiapin.github.io/Memorama/
- **Firebase 專案：** memorma-24dab（與 `pop-colores-numeros` 共用）
- **登入方式：** 匿名登入
- **狀態：** 使用中

## 功能
- 開始畫面與遊戲中可選：字體（简体／繁體）、介面語言（Español／English）、發音標示（不顯示／拼音／注音），立即生效並記在玩家瀏覽器
- 拼音、注音、語音一律台灣讀音
- 配錯時可直接點下一張牌
- 分數存檔失敗會存在玩家瀏覽器，之後自動補送
- GA4：`game_start`、`game_complete`、`leaderboard_view`

## 圖片
`images/images{id}.webp`（300×300）。程式會依序找 `.webp` → `.png` → 顯示 emoji。
第 33 張（紙）尚未放圖。

## Firebase 規則
見 `firestore-rules-snippet.txt`（只替換排行榜那一段，不要整份覆蓋）。
