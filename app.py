import sys
import json
import time
from datetime import datetime
from concurrent.futures import ThreadPoolExecutor
import feedparser
import requests
from flask import Flask, render_template

app = Flask(__name__)

CACHE = {
    'time': 0,
    'grouped_articles': [],
    'site_articles': {},
    'sites': []
}

def fetch_feed(site):
    try:
        # Some feeds block python-urllib, using requests with a browser agent
        headers = {'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/100.0.4896.127 Safari/537.36'}
        resp = requests.get(site['url'], headers=headers, timeout=10)
        feed = feedparser.parse(resp.content)
        articles = []
        for entry in feed.entries[:20]: # Top 20 from each
            # Parse published time
            dt = None
            if hasattr(entry, 'published_parsed') and entry.published_parsed:
                dt = datetime.fromtimestamp(time.mktime(entry.published_parsed))
            elif hasattr(entry, 'updated_parsed') and entry.updated_parsed:
                dt = datetime.fromtimestamp(time.mktime(entry.updated_parsed))
            else:
                dt = datetime.now()
            
            articles.append({
                'title': entry.title,
                'link': entry.link,
                'site_name': site['name'],
                'site_link': feed.feed.link if hasattr(feed.feed, 'link') else site['url'],
                'dt': dt,
                'site_id': site.get('id', '')
            })
        return articles
    except Exception as e:
        print(f"Error fetching {site['name']}: {e}")
        return []

def refresh_cache_if_needed():
    now = time.time()
    # Cache for 10 minutes (600 seconds)
    if CACHE['time'] > 0 and now - CACHE['time'] < 600:
        return
        
    try:
        with open('sites.json', 'r', encoding='utf-8') as f:
            sites = json.load(f)
    except Exception:
        sites = []
        
    all_articles = []
    with ThreadPoolExecutor(max_workers=10) as executor:
        results = executor.map(fetch_feed, sites)
        for res in results:
            all_articles.extend(res)
            
    # Sort by datetime descending
    all_articles.sort(key=lambda x: x['dt'], reverse=True)
    
    # Extract top 5 articles for each site
    site_articles = {}
    for site in sites:
        site_articles[site['id']] = []
        
    for a in all_articles:
        s_id = a.get('site_id')
        if s_id in site_articles and len(site_articles[s_id]) < 5:
            site_articles[s_id].append(a)
    
    # Group by date formatted like "2/26"
    grouped = []
    current_date = None
    group_obj = None
    
    for a in all_articles:
        d_str = f"{a['dt'].month}/{a['dt'].day}"
        if current_date != d_str:
            if group_obj:
                grouped.append(group_obj)
            current_date = d_str
            group_obj = {
                'date': current_date,
                'articles': []
            }
        
        # Add formatted time like "15:30"
        a['time'] = a['dt'].strftime("%H:%M")
        group_obj['articles'].append(a)
        
    if group_obj:
        grouped.append(group_obj)
        
    CACHE['grouped_articles'] = grouped
    CACHE['site_articles'] = site_articles
    CACHE['sites'] = sites
    CACHE['time'] = now

@app.route('/')
def index():
    refresh_cache_if_needed()
    return render_template('index.html', 
                           grouped_articles=CACHE['grouped_articles'], 
                           sites=CACHE['sites'],
                           site_articles=CACHE['site_articles'])

if __name__ == '__main__':
    # Start app automatically when script is run
    import webbrowser
    import threading
    # Open browser slightly after starting
    threading.Timer(1.25, lambda: webbrowser.open("http://127.0.0.1:5000/")).start()
    app.run(debug=False, port=5000, host='127.0.0.1')
