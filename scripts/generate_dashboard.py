import os
import json
import yfinance as yf
import requests
from datetime import datetime, timedelta
import anthropic

PORTFOLIO = ['AAPL', 'TSLA', 'NVDA', 'SPY']
WATCHLIST = ['MSFT', 'GOOGL', 'AMZN', 'META', 'AMD', 'PLTR', 'SMCI', 'NFLX', 'COIN', 'MSTR']


def get_stock_data(symbols):
    data = {}
    for symbol in symbols:
        try:
            ticker = yf.Ticker(symbol)
            hist = ticker.history(period="1mo")
            info = ticker.info
            if len(hist) >= 2:
                price = round(float(hist['Close'].iloc[-1]), 2)
                change_1d = round(((hist['Close'].iloc[-1] - hist['Close'].iloc[-2]) / hist['Close'].iloc[-2]) * 100, 2)
                idx_1w = max(-5, -len(hist))
                change_1w = round(((hist['Close'].iloc[-1] - hist['Close'].iloc[idx_1w]) / hist['Close'].iloc[idx_1w]) * 100, 2)
                change_1m = round(((hist['Close'].iloc[-1] - hist['Close'].iloc[0]) / hist['Close'].iloc[0]) * 100, 2)
                data[symbol] = {
                    'price': price,
                    'change_1d': float(change_1d),
                    'change_1w': float(change_1w),
                    'change_1m': float(change_1m),
                    'volume': int(hist['Volume'].iloc[-1]),
                    'name': info.get('longName', symbol),
                }
        except Exception as e:
            print(f"Error fetching {symbol}: {e}")
    return data


def get_ai_analysis(portfolio_data, watch_data):
    client = anthropic.Anthropic(api_key=os.environ['ANTHROPIC_API_KEY'])

    def summarize(d):
        return {k: {'price': v['price'], '1d': f"{v['change_1d']}%", '1w': f"{v['change_1w']}%", '1m': f"{v['change_1m']}%"} for k, v in d.items()}

    prompt = f"""You are a financial analyst. Based on this stock data give investment insights.

PORTFOLIO (stocks I own): {json.dumps(summarize(portfolio_data))}
WATCHLIST (stocks to consider): {json.dumps(summarize(watch_data))}

Return ONLY valid JSON with this exact structure:
{{
  "portfolio_analysis": {{
    "SYMBOL": {{
      "action": "BUY MORE" or "HOLD" or "SELL",
      "confidence": "High" or "Medium" or "Low",
      "reasoning": "2-3 sentence explanation",
      "price_target_1w": number,
      "price_target_1m": number
    }}
  }},
  "top_picks": [
    {{
      "symbol": "SYMBOL",
      "reasoning": "Why this is a good pick right now",
      "entry_price": number
    }}
  ],
  "market_outlook": "2-3 sentence overall market analysis"
}}"""

    msg = client.messages.create(
        model="claude-opus-4-7",
        max_tokens=2000,
        messages=[{"role": "user", "content": prompt}],
    )

    text = msg.content[0].text
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        start, end = text.find('{'), text.rfind('}') + 1
        if start >= 0 and end > start:
            return json.loads(text[start:end])
        return {}


def get_news(api_key, query, count=6):
    try:
        resp = requests.get(
            "https://newsapi.org/v2/everything",
            params={'q': query, 'sortBy': 'publishedAt', 'pageSize': count, 'language': 'en', 'apiKey': api_key},
            timeout=10,
        )
        if resp.status_code == 200:
            return resp.json().get('articles', [])
    except Exception as e:
        print(f"News error ({query}): {e}")
    return []


def get_nba_scores():
    try:
        resp = requests.get(
            "https://site.api.espn.com/apis/site/v2/sports/basketball/nba/scoreboard",
            timeout=10,
        )
        if resp.status_code == 200:
            games = []
            for event in resp.json().get('events', []):
                comp = event['competitions'][0]
                home = comp['competitors'][0]
                away = comp['competitors'][1]
                status = comp['status']['type']
                games.append({
                    'home_team': home['team']['displayName'],
                    'home_abbr': home['team']['abbreviation'],
                    'home_score': home.get('score', '-'),
                    'away_team': away['team']['displayName'],
                    'away_abbr': away['team']['abbreviation'],
                    'away_score': away.get('score', '-'),
                    'status': status['shortDetail'],
                    'completed': status['completed'],
                    'in_progress': not status['completed'] and status['name'] != 'STATUS_SCHEDULED',
                })
            return games
    except Exception as e:
        print(f"NBA error: {e}")
    return []


# ── HTML helpers ──────────────────────────────────────────────────────────────

def cls(val):
    return 'pos' if val > 0 else ('neg' if val < 0 else 'neu')

def arrow(val):
    return '▲' if val > 0 else ('▼' if val < 0 else '–')

def time_ago(iso):
    try:
        pub = datetime.fromisoformat(iso.replace('Z', '+00:00'))
        diff = datetime.now(pub.tzinfo) - pub
        if diff.seconds < 3600:
            return f"{diff.seconds // 60}m ago"
        if diff.days == 0:
            return f"{diff.seconds // 3600}h ago"
        return f"{diff.days}d ago"
    except Exception:
        return ''


def render_news_cards(articles):
    html = ''
    for a in articles[:6]:
        if not a.get('title') or a['title'] == '[Removed]':
            continue
        title = a['title'][:90] + ('…' if len(a['title']) > 90 else '')
        source = a.get('source', {}).get('name', '')
        url = a.get('url', '#')
        ago = time_ago(a.get('publishedAt', ''))
        html += f'''
        <a href="{url}" target="_blank" rel="noopener" class="news-card">
          <div class="news-meta">{source}{' · ' + ago if ago else ''}</div>
          <div class="news-title">{title}</div>
        </a>'''
    return html


def generate_html(portfolio_data, watch_data, ai, tech_news, gaming_news, nba_games):
    now = datetime.now().strftime('%b %d, %Y · %I:%M %p')

    # ── Portfolio cards ───────────────────────────────────────────────────────
    portfolio_html = ''
    for sym, d in portfolio_data.items():
        an = ai.get('portfolio_analysis', {}).get(sym, {})
        action = an.get('action', 'HOLD')
        ac = 'abuy' if 'BUY' in action else ('asell' if action == 'SELL' else 'ahold')
        targets = ''
        if an.get('price_target_1w'):
            targets = f'<div class="targets"><span>1W est: <b>${an["price_target_1w"]}</b></span><span>1M est: <b>${an["price_target_1m"]}</b></span></div>'
        reasoning = f'<div class="reasoning">{an["reasoning"]}</div>' if an.get('reasoning') else ''
        conf = f'<span class="conf">{an["confidence"]} confidence</span>' if an.get('confidence') else ''

        portfolio_html += f'''
        <div class="card stock-card">
          <div class="card-top">
            <div>
              <div class="sym">{sym}</div>
              <div class="sname">{d["name"][:32]}</div>
            </div>
            <div class="right-top">
              <div class="badge {ac}">{action}</div>
              {conf}
            </div>
          </div>
          <div class="price">${d["price"]:,.2f}</div>
          <div class="changes">
            <div class="chg"><span class="clbl">1D</span><span class="{cls(d["change_1d"])}">{arrow(d["change_1d"])} {abs(d["change_1d"])}%</span></div>
            <div class="chg"><span class="clbl">1W</span><span class="{cls(d["change_1w"])}">{arrow(d["change_1w"])} {abs(d["change_1w"])}%</span></div>
            <div class="chg"><span class="clbl">1M</span><span class="{cls(d["change_1m"])}">{arrow(d["change_1m"])} {abs(d["change_1m"])}%</span></div>
          </div>
          {reasoning}
          {targets}
        </div>'''

    # ── Top picks ─────────────────────────────────────────────────────────────
    picks_html = ''
    for pick in ai.get('top_picks', [])[:3]:
        sym = pick['symbol']
        d = watch_data.get(sym, {})
        price_str = f'${d["price"]:,.2f}' if d else ''
        chg_html = ''
        if d:
            chg_html = f'<span class="{cls(d["change_1d"])}">{arrow(d["change_1d"])} {abs(d["change_1d"])}% today</span>'
        entry = f'<div class="entry">Suggested entry: <b>${pick["entry_price"]}</b></div>' if pick.get('entry_price') else ''
        picks_html += f'''
        <div class="card pick-card">
          <div class="card-top">
            <div class="sym">{sym}</div>
            <div class="right-top"><span class="price-sm">{price_str}</span>{chg_html}<div class="badge abuy">BUY</div></div>
          </div>
          <div class="reasoning">{pick.get("reasoning", "")}</div>
          {entry}
        </div>'''

    # ── NBA ───────────────────────────────────────────────────────────────────
    nba_html = ''
    if nba_games:
        for g in nba_games:
            live_cls = ' live' if g['in_progress'] else ''
            live_dot = '<span class="live-dot">●</span> ' if g['in_progress'] else ''
            nba_html += f'''
            <div class="card game-card{live_cls}">
              <div class="team-row">
                <span class="tname">{g["away_abbr"]}</span>
                <span class="tscore">{g["away_score"]}</span>
              </div>
              <div class="gstatus">{live_dot}{g["status"]}</div>
              <div class="team-row">
                <span class="tname">{g["home_abbr"]}</span>
                <span class="tscore">{g["home_score"]}</span>
              </div>
            </div>'''
    else:
        nba_html = '<div class="empty">No games scheduled today</div>'

    outlook = ai.get('market_outlook', 'Market analysis unavailable.')

    return f'''<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width, initial-scale=1.0">
  <title>Dashboard</title>
  <style>
    *, *::before, *::after {{ box-sizing: border-box; margin: 0; padding: 0; }}

    :root {{
      --bg: #070710;
      --surface: #0f0f1a;
      --border: #1e1e35;
      --border-hover: #5a4fff;
      --text: #e0e0f0;
      --muted: #6b6b90;
      --accent: #7c6aff;
      --green: #3ddc84;
      --red: #ff5c5c;
      --yellow: #ffd166;
      --live: #ff5c5c;
    }}

    body {{
      font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', system-ui, sans-serif;
      background: var(--bg);
      color: var(--text);
      min-height: 100vh;
    }}

    /* ── Header ── */
    header {{
      background: linear-gradient(135deg, #0d0d20 0%, #12122a 100%);
      border-bottom: 1px solid var(--border);
      padding: 18px 28px;
      display: flex;
      justify-content: space-between;
      align-items: center;
      position: sticky;
      top: 0;
      z-index: 10;
      backdrop-filter: blur(12px);
    }}
    header h1 {{
      font-size: 1.35rem;
      font-weight: 800;
      background: linear-gradient(90deg, #7c6aff, #c56aff, #ff6ab0);
      -webkit-background-clip: text;
      -webkit-text-fill-color: transparent;
      letter-spacing: -0.5px;
    }}
    .stamp {{ font-size: 0.72rem; color: var(--muted); }}

    /* ── Layout ── */
    .wrap {{ max-width: 1380px; margin: 0 auto; padding: 28px 22px; }}
    .section {{ margin-bottom: 40px; }}
    .sec-head {{
      display: flex; align-items: center; gap: 8px;
      margin-bottom: 16px;
    }}
    .sec-icon {{ font-size: 1.1rem; }}
    .sec-title {{ font-size: 1rem; font-weight: 700; color: #fff; letter-spacing: -0.2px; }}

    /* ── Grid ── */
    .grid-4 {{ display: grid; grid-template-columns: repeat(auto-fill, minmax(270px, 1fr)); gap: 14px; }}
    .grid-3 {{ display: grid; grid-template-columns: repeat(auto-fill, minmax(300px, 1fr)); gap: 14px; }}
    .grid-nba {{ display: grid; grid-template-columns: repeat(auto-fill, minmax(200px, 1fr)); gap: 12px; }}

    /* ── Cards ── */
    .card {{
      background: var(--surface);
      border: 1px solid var(--border);
      border-radius: 14px;
      padding: 18px;
      transition: border-color 0.2s, box-shadow 0.2s;
    }}
    .card:hover {{ border-color: var(--border-hover); box-shadow: 0 0 20px rgba(124,106,255,0.08); }}

    /* ── Stock card ── */
    .card-top {{ display: flex; justify-content: space-between; align-items: flex-start; margin-bottom: 12px; }}
    .right-top {{ display: flex; flex-direction: column; align-items: flex-end; gap: 5px; }}
    .sym {{ font-size: 1.15rem; font-weight: 800; color: #fff; }}
    .sname {{ font-size: 0.68rem; color: var(--muted); margin-top: 2px; }}
    .price {{ font-size: 1.9rem; font-weight: 700; color: #fff; margin-bottom: 12px; letter-spacing: -1px; }}
    .price-sm {{ font-size: 0.9rem; font-weight: 600; color: #fff; }}
    .changes {{ display: flex; gap: 18px; margin-bottom: 10px; }}
    .chg {{ display: flex; flex-direction: column; align-items: center; gap: 3px; }}
    .clbl {{ font-size: 0.6rem; color: var(--muted); text-transform: uppercase; letter-spacing: 0.5px; }}
    .pos {{ color: var(--green); font-weight: 600; font-size: 0.82rem; }}
    .neg {{ color: var(--red); font-weight: 600; font-size: 0.82rem; }}
    .neu {{ color: var(--muted); font-weight: 600; font-size: 0.82rem; }}
    .reasoning {{ font-size: 0.74rem; color: #aaa; line-height: 1.55; padding-top: 10px; border-top: 1px solid var(--border); margin-top: 2px; }}
    .targets {{ display: flex; gap: 14px; margin-top: 8px; font-size: 0.73rem; color: var(--accent); }}
    .conf {{ font-size: 0.63rem; color: var(--muted); }}
    .entry {{ font-size: 0.74rem; color: var(--accent); margin-top: 8px; }}

    /* ── Badges ── */
    .badge {{ padding: 3px 9px; border-radius: 20px; font-size: 0.65rem; font-weight: 800; letter-spacing: 0.6px; }}
    .abuy  {{ background: #0f2e1a; color: var(--green); border: 1px solid var(--green); }}
    .asell {{ background: #2e0f0f; color: var(--red);   border: 1px solid var(--red);   }}
    .ahold {{ background: #2e260a; color: var(--yellow); border: 1px solid var(--yellow); }}

    /* ── Outlook ── */
    .outlook {{
      background: linear-gradient(135deg, #0d0d22, #141428);
      border: 1px solid var(--border);
      border-left: 3px solid var(--accent);
      border-radius: 14px;
      padding: 20px 24px;
      font-size: 0.88rem;
      color: #ccc;
      line-height: 1.7;
    }}

    /* ── News ── */
    .news-card {{
      background: var(--surface);
      border: 1px solid var(--border);
      border-radius: 12px;
      padding: 14px 16px;
      text-decoration: none;
      display: block;
      transition: border-color 0.2s, transform 0.15s;
    }}
    .news-card:hover {{ border-color: var(--border-hover); transform: translateY(-2px); }}
    .news-meta {{ font-size: 0.63rem; color: var(--accent); text-transform: uppercase; letter-spacing: 0.5px; margin-bottom: 7px; }}
    .news-title {{ font-size: 0.84rem; color: #ddd; line-height: 1.45; }}

    /* ── NBA ── */
    .game-card {{ padding: 14px 16px; }}
    .game-card.live {{ border-color: var(--live); box-shadow: 0 0 14px rgba(255,92,92,0.15); }}
    .team-row {{ display: flex; justify-content: space-between; align-items: center; padding: 4px 0; }}
    .tname {{ font-size: 0.88rem; color: #ddd; font-weight: 600; }}
    .tscore {{ font-size: 1.25rem; font-weight: 800; color: #fff; }}
    .gstatus {{ text-align: center; font-size: 0.68rem; color: var(--muted); padding: 5px 0; border-top: 1px solid var(--border); border-bottom: 1px solid var(--border); margin: 5px 0; }}
    .live-dot {{ color: var(--live); font-size: 0.6rem; }}
    .empty {{ color: var(--muted); font-size: 0.85rem; padding: 18px 0; }}

    footer {{ text-align: center; font-size: 0.7rem; color: #333; padding: 24px 0 12px; border-top: 1px solid var(--border); margin-top: 12px; }}

    @media (max-width: 640px) {{
      .wrap {{ padding: 16px 12px; }}
      header {{ flex-direction: column; gap: 6px; text-align: center; }}
      .price {{ font-size: 1.5rem; }}
    }}
  </style>
</head>
<body>

<header>
  <h1>⚡ Personal Dashboard</h1>
  <div class="stamp">Updated {now} · auto-refreshes every 5h</div>
</header>

<div class="wrap">

  <!-- AI Market Outlook -->
  <div class="section">
    <div class="sec-head"><span class="sec-icon">🧠</span><span class="sec-title">AI Market Outlook</span></div>
    <div class="outlook">{outlook}</div>
  </div>

  <!-- My Portfolio -->
  <div class="section">
    <div class="sec-head"><span class="sec-icon">💼</span><span class="sec-title">My Portfolio</span></div>
    <div class="grid-4">{portfolio_html}</div>
  </div>

  <!-- AI Top Picks -->
  <div class="section">
    <div class="sec-head"><span class="sec-icon">🎯</span><span class="sec-title">AI Top Picks to Watch</span></div>
    <div class="grid-3">{picks_html}</div>
  </div>

  <!-- Tech & AI News -->
  <div class="section">
    <div class="sec-head"><span class="sec-icon">💻</span><span class="sec-title">Tech &amp; AI News</span></div>
    <div class="grid-3">{render_news_cards(tech_news)}</div>
  </div>

  <!-- NBA Scores -->
  <div class="section">
    <div class="sec-head"><span class="sec-icon">🏀</span><span class="sec-title">NBA Scores</span></div>
    <div class="grid-nba">{nba_html}</div>
  </div>

  <!-- Gaming News -->
  <div class="section">
    <div class="sec-head"><span class="sec-icon">🎮</span><span class="sec-title">Gaming News</span></div>
    <div class="grid-3">{render_news_cards(gaming_news)}</div>
  </div>

</div>

<footer>Auto-updates every 5 hours via GitHub Actions &nbsp;·&nbsp; Powered by Claude AI</footer>

</body>
</html>'''


def main():
    newsapi_key = os.environ.get('NEWSAPI_KEY', '')

    print("Fetching portfolio data...")
    portfolio_data = get_stock_data(PORTFOLIO)

    print("Fetching watchlist data...")
    watch_data = get_stock_data(WATCHLIST)

    print("Running AI analysis...")
    ai = {}
    if os.environ.get('ANTHROPIC_API_KEY'):
        try:
            ai = get_ai_analysis(portfolio_data, watch_data)
        except Exception as e:
            print(f"AI analysis failed: {e}")

    print("Fetching news...")
    tech_news, gaming_news = [], []
    if newsapi_key:
        tech_news = get_news(newsapi_key, 'artificial intelligence OR AI OR technology', 6)
        gaming_news = get_news(newsapi_key, 'gaming OR "video games" OR esports OR PlayStation OR Xbox', 6)

    print("Fetching NBA scores...")
    nba_games = get_nba_scores()

    print("Generating index.html...")
    html = generate_html(portfolio_data, watch_data, ai, tech_news, gaming_news, nba_games)

    with open('index.html', 'w', encoding='utf-8') as f:
        f.write(html)

    print("Done! Dashboard saved to index.html")


if __name__ == '__main__':
    main()
