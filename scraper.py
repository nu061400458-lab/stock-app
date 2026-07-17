import os
import re
import time
import requests
from bs4 import BeautifulSoup

# LINE Notify トークン（GitHub Secretsから取得）
LINE_TOKEN = os.environ.get("LINE_NOTIFY_TOKEN")

def send_line_notify(message):
    if not LINE_TOKEN:
        print("LINE_TOKENが設定されていません。")
        return
    url = "https://notify-api.line.me/api/notify"
    headers = {"Authorization": f"Bearer {LINE_TOKEN}"}
    data = {"message": message}
    requests.post(url, headers=headers, data=data)

def get_latest_article_tickers(keyword):
    """指定キーワードの最新記事を検索し、掲載されている銘柄コード一覧を取得"""
    search_url = f"https://kabutan.jp/news/search/?word={keyword}"
    res = requests.get(search_url)
    soup = BeautifulSoup(res.text, 'html.parser')
    
    article_url = None
    # 検索結果から最新の記事URLを取得
    for a in soup.select('table.s_news_list a'):
        if keyword in a.text:
            article_url = "https://kabutan.jp" + a.get('href', '')
            break
            
    if not article_url:
        return []

    time.sleep(1)  # IPブロック回避
    
    res_art = requests.get(article_url)
    soup_art = BeautifulSoup(res_art.text, 'html.parser')
    text = soup_art.get_text()
    
    # 記事本文から「<1234>」のような4桁の銘柄コードを抽出
    tickers = re.findall(r'<(\d{4})>', text)
    # 重複を排除してリスト化
    return list(dict.fromkeys(tickers))

def extract_financial_data(code):
    """個別銘柄の財務データを取得し、条件判定・計算を行う"""
    try:
        # 1. 基本情報ページ
        base_url = f"https://kabutan.jp/stock/?code={code}"
        res_base = requests.get(base_url)
        soup_base = BeautifulSoup(res_base.text, 'html.parser')
        
        name_tag = soup_base.select_one('h2')
        if not name_tag:
            return None
        name = name_tag.text.split(' ')[0]
        
        # 2. 財務ページへアクセス
        time.sleep(1)  # 個別ページアクセス時も必ず待機
        fin_url = f"https://kabutan.jp/stock/finance?code={code}"
        res_fin = requests.get(fin_url)
        soup_fin = BeautifulSoup(res_fin.text, 'html.parser')

        # ※以下は株探のHTML構造からの抽出例。サイト構造に応じて調整してください
        # 配当利回り
        yield_text = soup_base.find('th', string=re.compile('利回り')).find_next_sibling('td').text
        dividend_yield = float(re.sub(r'[^\d.]', '', yield_text)) if yield_text else 0.0
        
        # --- 以下の変数は、実際の財務テーブルの td 要素等から取得するロジックに置き換えてください ---
        equity_ratio = 40.0      # 例: 自己資本比率
        eps = 100.0              # 例: 1株益
        bps = 1000.0             # 例: 1株純資産
        dps = 50.0               # 例: 1株配当
        settlement_month = "3月" # 例: 決算月
        dividend_up = "有"       # 例: 過去実績と会社予想の比較から判定
        
        # 指標の計算
        payout_ratio = (dps / eps) * 100 if eps > 0 else 999
        doe = (dps / bps) * 100 if bps > 0 else 0.0

        # スクリーニング条件の判定
        if dividend_yield >= 5.0 and equity_ratio >= 35.0 and payout_ratio < 70.0:
            return {
                "code": code,
                "name": name,
                "yield": dividend_yield,
                "equity_ratio": equity_ratio,
                "month": settlement_month,
                "payout_ratio": payout_ratio,
                "doe": doe,
                "dividend_up": dividend_up
            }
    except Exception as e:
        print(f"Error extracting {code}: {e}")
    return None

def main():
    keywords = ["高配当利回り銘柄ベスト30", "高配当利回り株ベスト50"]
    all_tickers = []
    
    # 2つの記事から銘柄を収集
    for kw in keywords:
        tickers = get_latest_article_tickers(kw)
        all_tickers.extend(tickers)
        time.sleep(1)
        
    all_tickers = list(dict.fromkeys(all_tickers)) # 両方の記事に掲載されている重複を排除
    
    results = []
    for code in all_tickers:
        data = extract_financial_data(code)
        if data:
            results.append(data)
            
    # メッセージの構築
    if results:
        message = "\n【高配当株スクリーニング結果】\n"
        for r in results:
            message += f"\n■{r['code']} {r['name']}\n"
            message += f"利回り: {r['yield']}%\n"
            message += f"自己資本比率: {r['equity_ratio']}%\n"
            message += f"配当性向: {r['payout_ratio']:.1f}%\n"
            message += f"DOE: {r['doe']:.1f}%\n"
            message += f"決算月: {r['month']}\n"
            message += f"増配発表: {r['dividend_up']}\n"
            message += "-" * 15
    else:
        message = "\n今回の条件に合致する銘柄はありませんでした。"
        
    send_line_notify(message)

if __name__ == "__main__":
    main()
