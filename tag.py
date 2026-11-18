"""アニメニュース検索の一覧（data/newsall.json）を作る：記事を項目に振り分け、同じ話題をまとめる。

  python3 tag.py

入力は2つ。
  - data/newsall_sites.json … MANTANWEB・アニメイトタイムズの見出しの一覧。非公開の anime-database が毎日記事を読んで作り
    （articles/newsall_export.py。本文を見る判定＝読者アンケート・映画欄の実写映画はそちらで済ませてある）、公開の anime-world 経由で届く
  - data/rss.jsonl … RSS（feeds.json）の見出し。rss.py が30分ごとに足す

振り分けは見出しだけを決まった規則（正規表現）で見る（LLM には読ませない）。1本の記事が複数の項目に入ってよい。
どれにも当たらないものは「その他」。本文は書き出さない（日付・見出し・リンク・サイト・見出しの作品名・項目だけ）。
項目の並びとまとまりは依頼者の判断（2026-11-17）：作品の動き／イベント・商品／配信・成績・受賞／業界・人・記事。
"""
import glob, json, os, re, sys, unicodedata

HERE = os.path.dirname(os.path.abspath(__file__))
OUT = sys.argv[1] if len(sys.argv) > 1 else os.path.join(HERE, 'data', 'newsall.json')
N = r'[0-9０-９一二三四五六七八九十]'

# (まとまり, 項目, 規則)。見出しを NFKC にしてから当てる
ITEMS = [
    ('作品の動き', '制作決定', r'アニメ化|映画化|(制作|製作|続編|新作|新シリーズ|' + N + r'{1,2}期|シーズン\d)[^。！!]{0,20}?(決定|発表|始動|進行中|制作中|製作中)|プロジェクト.{0,4}始動|(シーズン|第)\s*' + N + r'+\s*期?\s*(制作|製作)|始動を発表|(アニメ|劇場版|新作)[^。]{0,24}(制作|製作)(?!会社|陣|スタッフ|現場|秘話)|完全新作'),
    ('作品の動き', '放送・公開日', r'放送日|放送開始|放送スタート|放送決定|放送局|放送時期|放送枠|(より|から)(放送|公開|上映)|(放送|公開)へ|公開日|公開決定|上映開始|上映決定|劇場公開|ロードショー|\d+月\d+日(公開|放送)|(放送|公開)日決定|\d+月(\d+日)?(から|より)?(放送|公開|上映)|上映|(放送|配信|上映|から|より|\d日)スタート|放映'),
    ('作品の動き', 'キャスト', r'キャスト|声優|出演|(役|役柄)(は|に|で|を)|アフレコ|新キャラ|演じる|CV|声を担当|吹き替え|吹替|ボイス'),
    ('作品の動き', 'スタッフ', r'スタッフ|監督|脚本|シリーズ構成|キャラクターデザイン|キャラデザ|アニメーション制作|制作スタジオ|音楽(は|を)(担当)?'),
    ('作品の動き', '主題歌・音楽', r'主題歌|オープニング|エンディング|OPテーマ|EDテーマ|(^|[^A-Za-z])(OP|ED)([^A-Za-z]|$)|挿入歌|サントラ|サウンドトラック|楽曲|シングル|アルバム|(^|[^A-Za-z])MV|ノンクレジット|劇伴|キャラソン|キャラクターソング|歌う|歌唱'),
    ('作品の動き', 'PV・ビジュアル', r'PV|KV|イラスト|描き下ろし|VISUAL|Visual|ビジュアル|フォトギャラリー|予告|週替わり映像|動画公開|冒頭|映像|特報|ティザー|ビジュアル|映像(公開|解禁)|本編映像|ポスター|ノンクレ|(^|[^A-Za-z])CM([^A-Za-z]|$)|イラスト(公開|解禁)'),
    ('作品の動き', '原作', r'原作|連載|マンガ|漫画|コミック|単行本|小説|ラノベ|ライトノベル|巻頭|表紙|第\d+話(?!.*(放送|配信))|最終回|完結|コミカライズ|実写'),
    ('イベント・商品', 'イベント', r'イベント|ステージ|舞台(あいさつ|挨拶)|上映会|(?<!ラブ)ライブ|LIVE|フェス|祭典|映画祭|企画|AnimeJapan|披露|ジャンプフェスタ|開催|トークショー|生配信|生放送|特番|応援上映|ファンミーティング|コンサート'),
    ('イベント・商品', 'グッズ・コラボ', r'グッズ|コラボ|フィギュア|カフェ|ポップアップ|POP ?UP|キャンペーン|プライズ|くじ|ぬいぐるみ|アクリル|タイアップ|Blu-ray|ブルーレイ|BD|DVD|画集|ムック|設定資料|発売|予約|商品|限定版|特典|ガチャ|スタンプ|ガンプラ|プラモ|超合金|METAL|ROBOT魂|魂ネイション|魂ウェブ|Figuarts|ソフビ|(^|[^A-Za-z])(HG|MG|RG|PG)([^A-Za-z]|$)|HI-METAL|プレバン|再販|ステッカー|カードゲーム|ゲーム(化|アプリ|発売)|GUNDAM UNIVERSE|カレンダー|年賀|絵本|ブック|スタチュー|アイテム|付録|cafe|Cafe|ストア|ショップ|店舗|新店|味|ポテト|ローソン|ファミマ|セブン'),
    ('イベント・商品', '展示', r'(?<![発進])展(?![開望])|展示|原画|ミュージアム|美術館|博物館'),
    ('配信・成績・受賞', '配信', r'配信|Netflix|ネトフリ|Prime Video|プライム・?ビデオ|ディズニープラス|Disney\+|dアニメ|ABEMA|U-NEXT|DMM TV|Hulu|Lemino|見放題|独占|YouTube'),
    ('配信・成績・受賞', '映画興行', r'興行収入|興収|動員|週末|観客数|万人突破|公開\d+日間'),
    ('配信・成績・受賞', 'ランキング', r'ランキング|首位|' + N + r'+位|TOP\s?\d+|ベスト\d+|人気投票|投票|アンケート|視聴数|再生数|再生回数'),
    ('配信・成績・受賞', '発行部数', r'発行部数|部数|万部'),
    ('配信・成績・受賞', '受賞', r'受賞|ノミネート|文化功労者|文化勲章|顕彰|アワード|グランプリ(を|に)?(受賞|獲得|輝)|(?<![鑑懸観激])賞(?![品味])|選出'),
    ('業界・人・記事', '会社・業界', r'設立|新会社|子会社|買収|合併|決算|売上|株式|人事|社長|代表取締役|就任|退任|退社|移籍|提携|上場|倒産|破産|事業|投資|出資|ファンド|市場|産業|資金調達|業界|労働|アニメーター|制作会社|スタジオ(が|を|の)?設立|経産省|文化庁|政府|規制|AI|生成AI|海賊版|著作権|求人|募集|オーディション'),
    ('業界・人・記事', '訃報', r'死去|亡くなった|亡くなる|逝去|訃報|永眠|死亡|お別れの会|しのぶ会|追悼'),
    ('業界・人・記事', 'インタビュー', r'インタビュー|対談|鼎談|座談会|に聞く|に聞いた|語る|語った|語り|が明かす|演技|胸中|秘話|裏側'),
    ('業界・人・記事', 'コメント', r'コメント|メッセージ|意気込み|喜び|本人が'),
    ('業界・人・記事', 'レポート・コラム', r'レポート|レポ|リポート|レビュー|コラム|解説|振り返|考察|なぜ|理由|まとめ|特集|魅力|トレンド|徹底|分析|今週|1週間'),
]
RX = [(g, i, re.compile(r)) for g, i, r in ITEMS]
# 先行カット・あらすじの記事は載せない（収集でも外しているが、制作決定ニュースから写した記事もあるので念のため）
SKIP = re.compile(r'先行カット|先行場面カット|場面カット|あらすじ|先行公開(?:カット|場面)|次回予告|^[^：:]{1,60}[：:]\s*第\s*\d+\s*話\s*[「『]|第\s*\d+\s*話\s*[「『][^」』]+[」』]\s*(?:場面|カット|放送|配信|予告)')
START = '2026-10-17'   # 集め始めた日（一覧ページに残っている古い記事は載せない）
# アニメイトタイムズの読者アンケート系の記事（募集・結果発表）は載せない（依頼者の判断、2026-11-17）。作品の公式の人気投票は残す
SURVEY = re.compile(r'アニメイトタイムズでは[^。]{0,80}?(アンケート|募集)')   # 見出しの「アンケート」ではなく、本文の「アニメイトタイムズでは…アンケートを実施／…を大募集」で決める（別の文脈のアンケートは残す）
ANIME = re.compile(r'アニメ|劇場版|声優|OVA|OAD|Vtuber|VTuber|ジブリ|漫画家|マンガ家|特撮')

def nf(s): return unicodedata.normalize('NFKC', s or '')

def work(r, t):
    """見出しの作品名（検索のきっかけに出すだけ。MANTANWEB は見出しの頭の「名前：」、ほかは『』）"""
    if r.get('site') == 'MANTANWEB':
        m = re.match(r'([^:「」『』]{1,40}?):', t)
        if m and not re.search(r'^\d|^第|週|ランキング|解説|特集|インタビュー', m.group(1)): return m.group(1).strip()
    m = re.search(r'『([^』]{1,60})』', t) or re.search(r'「([^」]{2,40})」', t)
    return re.sub(r'^(TVアニメ|テレビアニメ|劇場版|劇場アニメ|映画|アニメ)\s*', '', m.group(1)).replace('「', '').replace('」', ' ').strip() if m else ''

items, seen = [], set()
def records():
    p = os.path.join(HERE, 'data', 'newsall_sites.json')
    if os.path.exists(p):
        for x in json.load(open(p, encoding='utf-8')):
            yield {'url': x['u'], 'title': x['t'], 'date': x['d'], 'site': x['s'], 'anime': 1}
    p = os.path.join(HERE, 'data', 'rss.jsonl')
    if os.path.exists(p):
        for l in open(p, encoding='utf-8'):
            x = json.loads(l)
            yield {'url': x['u'], 'title': x['t'], 'date': x['d'], 'site': x['s'], 'anime': 0 if x.get('anime_title') else 1, 'ceek_items': x.get('items', [])}
if True:
    for r in records():
        if r['url'] in seen: continue
        seen.add(r['url'])
        t = nf(r.get('title') or r.get('list_title'))
        if not t or SKIP.search(t) or (r.get('date') or '9') < START: continue
        if r.get('site') == 'アニメイトタイムズ' and SURVEY.search(nf(r.get('body', ''))): continue
        if not r.get('anime') and not ANIME.search(t + nf(r.get('body', ''))[:400]): continue   # アニメ欄以外の一覧（映画欄）の実写映画など
        n = work(r, t)
        # 作品名・催しの名前などの中の言葉では項目を決めない（『死亡遊戯で飯を食う。』が訃報になる）：『』の中身と、MANTANWEB の見出しの頭の作品名「名前：」を外して判定する
        # 【インタビュー】【レビュー】などの【】は記事の種類なので残す。「」は催し・店の名前（「animate cafe 香港」）にも使われるので残す
        ct = re.sub(r'『[^』]*』', '、', t)
        if r.get('site') == 'MANTANWEB' and n and t.startswith(n) and not re.search(r'フェス|展|イベント|カフェ|ショップ|チャンネル|ネイション|Con|祭|(監督|社長|プロデューサー|P|役|さん)$', n): ct = ct[len(n):].lstrip(':： ')
        tags = [i for g, i, rx in RX if rx.search(ct)] or ['その他']
        if r.get('ceek_items') and not set(tags) & set(r['ceek_items']): tags = [x for x in tags if x != 'その他'] + [r['ceek_items'][0]]   # RSS の手がかり（feeds.json の items。訃報・人事の RSS なら訃報か会社・業界のどちらかには入れる）
        if 'ランキング' in tags and ('映画興行' in tags or '発行部数' in tags): tags.remove('ランキング')   # 興行・部数の順位はそちらに（ランキングは、それらを含まない○位・ランキング）
        e = {'d': r.get('date') or '', 't': r.get('title') or t, 'u': r['url'], 's': r.get('site') or '', 'g': tags}
        if n: e['n'] = n
        items.append(e)
items.sort(key=lambda e: (e['d'], e['u']), reverse=True)

# ---- 同じ話題の記事を1行にまとめる（見出しの2文字ずつの組の重なり。前後3日以内。両方に作品名があって違えばまとめない）
import datetime
def bigr(t):
    s = re.sub(r'[\s・!！?？:：~〜～\-－「」『』【】()（）、。,.＆&/／“”"]', '', nf(t).lower())
    return {s[i:i + 2] for i in range(len(s) - 1)}
def day(d):
    try: return datetime.date.fromisoformat(d).toordinal()
    except Exception: return 0
SAME = 0.4
def mark(t): return tuple(re.findall(r'第\s*\d+\s*[弾回話期章部]|前編|後編|中編|\d+日目', nf(t)))
clusters = []   # [代表, [記事...], 組の集合]
for e in sorted(items, key=lambda e: (e['d'], e['u'])):
    b, dd = bigr(e['t']), day(e['d'])
    best, bs = None, 0
    for c in clusters[-400:]:
        if abs(day(c[0]['d']) - dd) > 3: continue
        if e.get('n') and c[0].get('n') and re.sub(r'\s', '', e['n']) != re.sub(r'\s', '', c[0]['n']): continue
        if e['s'] in {x['s'] for x in c[1]}: continue   # 同じサイトは同じ話を2度載せないので、まとめるのは違うサイトの記事だけ
        if mark(e['t']) != mark(c[0]['t']) and mark(e['t']) and mark(c[0]['t']): continue   # 第2弾と第3弾、前編と後編
        sim = 2 * len(b & c[2]) / max(1, len(b) + len(c[2]))
        if sim > bs: best, bs = c, sim
    if best and bs >= SAME: best[1].append(e)
    else: clusters.append([e, [e], b])
out = []
for c in clusters:
    es = c[1]
    m = max(es, key=lambda x: (x['s'] in ('MANTANWEB', 'アニメイトタイムズ'), len(x['t'])))   # 代表：アニメの専門サイトの、見出しの長いもの
    r = dict(m); r['d'] = min(x['d'] for x in es if x['d']) if any(x['d'] for x in es) else m['d']
    r['g'] = [i for i in [x for g in ITEMS for x in [g[1]]] + ['その他'] if any(i in x['g'] for x in es)]
    if len(r['g']) > 1 and 'その他' in r['g']: r['g'].remove('その他')
    if len(es) > 1: r['o'] = [[x['s'], x['u'], x['t']] for x in es if x is not m]; r['c'] = len(es)
    out.append(r)
items = sorted(out, key=lambda e: (e['d'], e['u']), reverse=True)
groups = []
for g, i, _ in ITEMS:
    if not groups or groups[-1][0] != g: groups.append([g, []])
    groups[-1][1].append(i)
groups.append(['その他', ['その他']])
json.dump({'groups': groups, 'items': items}, open(OUT, 'w', encoding='utf-8'), ensure_ascii=False, separators=(',', ':'))
from collections import Counter
c = Counter(x for e in items for x in e['g'])
print('書き出し', len(items), '件 →', OUT)
for g, its in groups: print(' ', g, '：', '、'.join(f'{i} {c[i]}' for i in its))
