# Personal Dashboard

Auto-updating dashboard: stocks (portfolio + AI picks), NBA scores, Tech/AI news, Gaming news.
Rebuilds every 5 hours via GitHub Actions → hosted free on GitHub Pages.

---

## Setup (one-time, ~10 minutes)

### Step 1 — Get your free API keys

| Key | Where to get it | Free? |
|-----|----------------|-------|
| `NEWSAPI_KEY` | https://newsapi.org → Sign up → copy key | Yes (100 req/day) |
| `ANTHROPIC_API_KEY` | https://console.anthropic.com → API Keys | Pay-per-use (~$0.01/run) |

---

### Step 2 — Push this folder to GitHub

1. Go to **github.com** → click **New repository**
2. Name it `personal-dashboard`, set it to **Public**, click **Create**
3. Open Terminal and run:

```bash
cd "path/to/personal-dashboard"
git init
git add .
git commit -m "initial dashboard"
git branch -M main
git remote add origin https://github.com/YOUR_USERNAME/personal-dashboard.git
git push -u origin main
```

Replace `YOUR_USERNAME` with your GitHub username.

---

### Step 3 — Add your API keys as GitHub Secrets

1. On GitHub, go to your repo → **Settings** → **Secrets and variables** → **Actions**
2. Click **New repository secret** and add:
   - Name: `NEWSAPI_KEY` → paste your NewsAPI key
   - Name: `ANTHROPIC_API_KEY` → paste your Anthropic key
3. Click **Add secret** for each one

---

### Step 4 — Enable GitHub Pages

1. In your repo → **Settings** → **Pages**
2. Under **Source**, select **Deploy from a branch**
3. Branch: `main`, folder: `/ (root)` → click **Save**
4. Your site will be live at: `https://YOUR_USERNAME.github.io/personal-dashboard`

---

### Step 5 — Run it for the first time

1. Go to your repo → **Actions** tab
2. Click **Update Dashboard** in the left sidebar
3. Click **Run workflow** → **Run workflow** (green button)
4. Wait ~60 seconds → refresh your GitHub Pages URL

The dashboard will now auto-rebuild every 5 hours automatically.

---

## Adding more stocks later

Open `scripts/generate_dashboard.py` and edit:

```python
PORTFOLIO = ['AAPL', 'TSLA', 'NVDA', 'SPY']        # your stocks
WATCHLIST = ['MSFT', 'GOOGL', 'AMZN', ...]          # AI will pick from these
```

Commit and push — done.

---

## File structure

```
personal-dashboard/
├── .github/workflows/update-dashboard.yml   # auto-update schedule
├── scripts/generate_dashboard.py            # fetches data + builds HTML
├── index.html                               # the live dashboard (auto-generated)
├── requirements.txt                         # Python dependencies
└── README.md
```
