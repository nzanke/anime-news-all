"""アニメニュース検索（https://nzanke.github.io/anime-news-all/）を組み立てる。
データは data/newsall.json（非公開の anime-database の articles/newsall_tag.py が書き出し、公開の anime-world を経由して届く）。
記事の本文は持たず、日付・見出し・リンク・サイトと、見出しから読み取った作品名・項目だけを載せる。"""
import hashlib, html, json, os, shutil
from collections import Counter

HERE = os.path.dirname(os.path.abspath(__file__))
D = lambda *p: os.path.join(HERE, *p)
OUT = D('_site')
SITE = 'アニメニュース検索'
esc = lambda s: html.escape(str(s or ''))
if os.path.exists(OUT): shutil.rmtree(OUT)
os.makedirs(OUT)
for f in ('style.css', 'news.js'): shutil.copy(D('static', f), OUT)
open(os.path.join(OUT, '.nojekyll'), 'w').close()
NEWS = json.load(open(D('data', 'newsall.json'), encoding='utf-8'))
nj = json.dumps(NEWS, ensure_ascii=False, separators=(',', ':'))
open(os.path.join(OUT, 'newsall.json'), 'w', encoding='utf-8').write(nj)
V = lambda b: hashlib.sha1(b).hexdigest()[:8]
CSS_V, NJS_V, NEWS_V = V(open(D('static', 'style.css'), 'rb').read()), V(open(D('static', 'news.js'), 'rb').read()), V(nj.encode())

FONTS = ('<link rel="preconnect" href="https://fonts.googleapis.com"><link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>'
         '<link rel="stylesheet" href="https://fonts.googleapis.com/css2?family=BIZ+UDPGothic:wght@400;700&display=swap">'
         # 半角の数字・英字・記号だけ BIZ UDゴシック（text= でその文字だけの字体にし、日本語は BIZ UDPゴシック に落ちる）
         '<link rel="stylesheet" href="https://fonts.googleapis.com/css2?family=BIZ+UDGothic:wght@400;700&display=swap&text=%21%22%23%24%25%26%27%28%29%2A%2B%2C-.%2F0123456789%3A%3B%3C%3D%3E%3F%40ABCDEFGHIJKLMNOPQRSTUVWXYZ%5B%5C%5D%5E_%60abcdefghijklmnopqrstuvwxyz%7B%7C%7D~">')
HUE = {'新作情報': 250, 'イベント情報': 25, 'アイテム情報': 345, 'コラボ情報': 45, 'その他': 200}
GROUPS = NEWS['groups']
items_txt = ''.join(f'<p><b>{esc(x[0])}</b>：{"、".join(esc(i) for i in x[1])}{"（小カテゴリを選ぶと記事が出ます）" if len(x) > 2 else ""}</p>' for x in GROUPS)
ABOUT = f'''<details class="about"><summary><span class="qi">?</span>このサイトについて</summary><div class="aboutbox"><p class="abh">このサイトについて</p>
<p>アニメのニュースを毎日集め、項目ごとに絞り込めるようにした一覧です。上の色のボタンでまとまりを選ぶと、その下に細かい項目が出ます。項目は1回押すとその項目で絞り込み（複数選べます）、2回押すとその項目を除外、3回押すと元に戻ります。除外した項目は、まとまりを切り替えても効いたままです（「除外中」の項目を押すと除外をやめます）。1本の記事が複数の項目に入ることがあります。どの項目にも当たらない記事は「その他」の「未分類」です。「その他」のカテゴリは、小カテゴリを選んだときだけ記事が出ます。</p>
{items_txt}
<p><b>同じ話題</b>：違うサイトが同じ話題を伝えた記事は1行にまとめ、伝えた記事の数を右に出しています（見出しの似ている度合いで機械的にまとめているため、誤りが混じることがあります）。「伝えた記事の多い順」で、多くのサイトが伝えた話題から並べます。</p>
<p><b>検索</b>：スペースで区切ると、すべての語を含むものだけを出します。記事の下の作品名を押すと、その作品名で検索します。</p>
<p><b>集めている記事</b>：MANTANWEB と アニメイトタイムズ のアニメの記事（先行カット・あらすじの記事は除いています）と、新聞各紙などのアニメに関する記事（訃報・人事など）。毎日夕方に新着を集めます。過去の記事は2026年10月17日から集めています。</p>
<p><b>載せているもの</b>：記事の日付・見出し・リンクと、見出しから読み取った作品名と項目。記事の本文は載せていません。項目の読み取りは見出しの言葉から決まった規則で機械的に行っているため、誤りが混じることがあります。</p>
<p>アニメの制作決定と放送日・公開日だけを見るなら <a href="https://nzanke.github.io/anime-news/">アニメ制作決定ニュース</a>。</p>
</div></details>'''

nsites = [x for x, _ in Counter(e['s'] for e in NEWS['items']).most_common()]
btns = ''.join(f'<button type="button" data-g="{esc(g)}" style="--h:{h}"{" class=on" if not g else ""}>{esc(t)}<span class="n"></span></button>'
               for g, t, h in [('', 'すべて', 250)] + [(x[0], x[0], HUE.get(x[0], 70)) for x in GROUPS])
body = f'''<div class="seg" id="seg">{btns}</div>
<div id="sub" hidden></div>
<div id="exrow" hidden></div>
<div class="sbar"><input type="search" id="q" placeholder="作品名・題名で検索">
<select id="site"><option value="">すべてのサイト</option>{"".join(f'<option>{esc(x)}</option>' for x in nsites)}</select></div>
<div class="opts"><label><input type="checkbox" id="old"> 古い順</label><label><input type="checkbox" id="big"> 伝えた記事の多い順</label></div>
<div class="cbar"><p class="count" id="count"></p>{ABOUT}</div>
<ul class="ulist" id="list"></ul>
<button class="more" id="more" hidden>さらに表示</button>'''
doc = f'''<!DOCTYPE html>
<html lang="ja"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>{esc(SITE)}</title><meta name="description" content="アニメのニュースを毎日集め、制作決定・キャスト・主題歌・イベント・グッズ・興行収入・受賞・インタビューなどの項目で絞り込める一覧">
{FONTS}<link rel="stylesheet" href="style.css?v={CSS_V}"></head>
<body><div class="wrap">
<h1 class="sitename"><a href="index.html">{esc(SITE)}</a></h1>
<main>
{body}
</main>
<footer class="site"><p>MANTANWEB・アニメイトタイムズ・新聞各紙などの記事の見出しとリンクを毎日集めて並べています（記事の本文は載せていません）。制作決定は <a href="https://nzanke.github.io/anime-news/">アニメ制作決定ニュース</a>、インタビュー記事は <a href="https://nzanke.github.io/anime-world/">アニメインタビュー検索</a>。</p></footer>
</div><script>window.NEWS="newsall.json?v={NEWS_V}";window.HUE={json.dumps(HUE, ensure_ascii=False)}</script><script src="news.js?v={NJS_V}"></script><script data-goatcounter="https://nzanke.goatcounter.com/count" async src="//gc.zgo.at/count.js"></script></body></html>
'''
open(os.path.join(OUT, 'index.html'), 'w', encoding='utf-8').write(doc)
print('組み立て', len(NEWS['items']), '件')
