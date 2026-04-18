# 中壢在地經營 SEO 一頁式網站

這是一個使用 Flask 製作的單頁式品牌網站，主題是「中壢在地經營 SEO」。
專案已整理成可直接上傳到 GitHub，並部署到常見 Python 平台的版本。

## 目前功能

- 一頁式行銷首頁
- 中壢在地 SEO 文案與服務區塊
- FAQ 區塊
- `ProfessionalService` 與 `FAQPage` 結構化資料
- 可透過 `SITE_URL` 環境變數產生正確 canonical 與 schema 網址
- 可使用 `gunicorn` 作為 production server

## 專案檔案

- `app.py`: Flask 主程式
- `wsgi.py`: production 入口
- `templates/landing.html`: 一頁式首頁
- `static/styles.css`: 網站樣式
- `requirements.txt`: Python 套件
- `Procfile`: 給支援 Procfile 的平台使用
- `runtime.txt`: Python 版本
- `.gitignore`: Git 忽略規則

## 本機執行

1. 安裝套件

```bash
python3 -m pip install -r requirements.txt
```

2. 啟動網站

```bash
python3 app.py
```

3. 開啟瀏覽器

```text
http://127.0.0.1:5000
```

## GitHub 上傳

1. 在 GitHub 建立一個新的 repository
2. 在本機專案目錄執行

```bash
git init
git add .
git commit -m "Initial SEO landing page"
git branch -M main
git remote add origin <你的 GitHub repository URL>
git push -u origin main
```

## 部署建議

這份專案很適合部署到 Render、Railway、Fly.io 或支援 Python/Gunicorn 的平台。

### Render 範例

- Build Command

```bash
pip install -r requirements.txt
```

- Start Command

```bash
gunicorn wsgi:app
```

- Environment Variables

```text
SITE_URL=https://你的正式網域
```

如果平台有自動提供 `PORT`，這份專案會直接使用。

## 上線前建議修改

- 把 `app.py` 內的品牌名稱、電話、地址改成你的真實資料
- 把 `SITE_URL` 設成正式網址
- 如果你有自己的品牌名稱與服務項目，可以把首頁文案換成你的實際產業版本

## 目前是什麼型態

這是一個單頁式 SEO 官網，不是多頁 CMS，也不是後台型網站。
如果你下一步要，我可以再幫你補：

- 聯絡表單
- LINE 按鈕
- 真實品牌文案
- favicon / Open Graph 圖
- 多頁 SEO 架構
