"""feeds.json の RSS を読み、新しい記事の見出しを data/rss.jsonl に足す（30分ごと、.github/workflows/pages.yml）。

1行 = {u: 元記事のリンク, t: 見出し（末尾の（媒体名）を外したもの）, d: 日付, s: 媒体名, cat: RSS の分類, feed: RSS の名前, items: 振り分けの手がかり, anime_title}
記事そのものは読まない。RSS ごとに1秒あける。読めない RSS は飛ばして次へ。"""
import email.utils, html, json, os, re, time
import urllib.request
from urllib.parse import urlsplit, parse_qsl, urlencode

def canon(u):
    """同じ記事かどうかを見るためのリンク：http/https・www・末尾の / の違いと、追跡用の値（utm_ や ?c= や時事通信の &g= など）を外す"""
    p = urlsplit((u or '').strip())
    q = [(k, v) for k, v in parse_qsl(p.query) if not (k.startswith('utm_') or k in DROP_Q)]
    return re.sub(r'^www\.', '', p.netloc.lower()) + p.path.rstrip('/') + ('?' + urlencode(sorted(q)) if q else '')
DROP_Q = {'c', 'g', 'from', 'ref', 'rf', 'fbclid', 'gclid', 'display', 'page', 'cx_testId', 'cx_testVariant', 'cx_artPos', 'via', 'source', 'share'}

HERE = os.path.dirname(os.path.abspath(__file__))
OUT = os.path.join(HERE, 'data', 'rss.jsonl')
UA = 'Mozilla/5.0 (compatible; anime-news-all; +https://nzanke.github.io/anime-news-all/)'

have = set()
if os.path.exists(OUT):
    for l in open(OUT, encoding='utf-8'): have.add(canon(json.loads(l)['u']))
added = 0
with open(OUT, 'a', encoding='utf-8') as out:
    for f in json.load(open(os.path.join(HERE, 'feeds.json'), encoding='utf-8'))['feeds']:
        try:
            x = urllib.request.urlopen(urllib.request.Request(f['url'], headers={'User-Agent': UA}), timeout=30).read().decode('utf-8', 'replace')
        except Exception as e:
            print('読めませんでした:', f['name'], e); time.sleep(1); continue
        n = 0
        for it in re.findall(r'<item\b.*?</item>', x, re.S):
            g = lambda k: html.unescape((re.search(r'<' + k + r'>(?:<!\[CDATA\[)?(.*?)(?:\]\]>)?</' + k + '>', it, re.S) or [None, ''])[1].strip())
            u, t = g('link'), g('title')
            if not u or canon(u) in have: continue
            m = re.match(r'(.*?)\s*[(（]([^()（）]{1,30})[)）]\s*$', t)
            title, site = (m.group(1), m.group(2)) if m else (t, '')
            try: d = email.utils.parsedate_to_datetime(g('pubDate')).astimezone(__import__('datetime').timezone(__import__('datetime').timedelta(hours=9))).strftime('%Y-%m-%d')
            except Exception: d = ''
            r = {'u': u, 't': title, 'd': d, 's': site, 'cat': g('category'), 'feed': f['name'], 'items': f.get('items', [])}
            if f.get('anime_title'): r['anime_title'] = True
            out.write(json.dumps(r, ensure_ascii=False) + '\n'); have.add(canon(u)); n += 1
        print(f"{f['name']}：{n}件 追加"); added += n
        time.sleep(1)
print('RSS 合計', added, '件 追加')
