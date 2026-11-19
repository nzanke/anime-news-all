"""アニメニュース検索の一覧（data/newsall.json）を作る：記事を項目に振り分け、同じ話題をまとめる。

  python3 tag.py

入力は2つ。
  - data/newsall_sites.json … MANTANWEB・アニメイトタイムズの見出しの一覧。非公開の anime-database が毎日記事を読んで作り
    （articles/newsall_export.py。本文を見る判定＝読者アンケート・映画欄の実写映画はそちらで済ませてある）、公開の anime-world 経由で届く
  - data/rss.jsonl … RSS（feeds.json）の見出し。rss.py が30分ごとに足す

振り分けは見出しだけを決まった規則（正規表現）で見る（LLM には読ませない）。1本の記事が複数の項目に入ってよい。
どれにも当たらないものは「その他」。本文は書き出さない（日付・見出し・リンク・サイト・見出しの作品名・項目だけ）。
項目の並びとまとまり（2026-11-18 細分化の案）：作品の動き／イベント／商品／コラボ／配信・成績・受賞／業界・社会／人・記事／コラム（2026-11-18）。
"""
import glob, json, os, re, sys, unicodedata

HERE = os.path.dirname(os.path.abspath(__file__))
OUT = sys.argv[1] if len(sys.argv) > 1 else os.path.join(HERE, 'data', 'newsall.json')
from rules import N, ITEMS, RX, ANIME, LIVE, LEAD_ITEMS, NOT_ANIME, nf, is_anime_title   # 規則は rules.py に（rss.py・非公開側の書き出しの判定と共通）

# ---- 表示するカテゴリ（依頼者の判断、2026-11-18）。上の ITEMS は細かい判定の単位で、表示のときにここでまとめる。
# 大カテゴリ4つ（新作情報・イベント情報・アイテム情報・コラボ情報）は押すとカテゴリ内の記事が全部出る。
# 「その他」は小カテゴリを選んだときだけ記事が出る（sub_only）。
SHOW = [
    ('新作情報', ['制作決定（テレビアニメ化）', '制作決定（映画化）', '制作決定（その他）', '放送・公開日', 'キャスト公開', 'スタッフ公開',
              '音楽情報公開', '映像解禁', 'ビジュアル公開', 'SNS開設', 'コメント公開'], False),
    ('イベント情報', ['舞台あいさつ', '上映会', '再上映', '先行上映', '映画祭', 'ライブ・コンサート', '大型催し・ステージ', '同時視聴会', '特番', '展覧会', '原画展', '展示情報', 'イベントレポート'], False),
    ('アイテム情報', ['入場者特典', '劇場販売商品', '紙媒体', 'ビデオソフト', '音楽ソフト', 'くじ', 'フェア・ポップアップ', 'ゲーム', 'その他アイテム'], False),
    ('コラボ情報', ['コラボグッズ', 'コラボビジュアル', 'その他コラボ'], False),
    ('その他', ['配信', 'テレビ放送', 'アニソン', '再放送・再配信', 'コスプレ', 'フィギュア・模型', '無料配信', '原作', '受賞・興行', 'ビジネス', '政治', '社会', 'コラム', '訃報', '海外の反応', 'インタビュー', '声優ニュース', '権利・AI', '芸能・スポーツ×アニメ', '未分類'], True),
]
TO_SHOW = {'書籍': '紙媒体', '雑誌特集': '紙媒体', 'Blu-ray・書籍': '紙媒体', 'グッズ・アパレル・雑貨': 'その他アイテム', 'コラボビジュアル公開': 'コラボビジュアル', '飲食・食品コラボ': 'その他コラボ', '企業・自治体・観光コラボ': 'その他コラボ', 'スタッフ': 'スタッフ公開', '主題歌・音楽': '音楽情報公開', 'コメント': 'コメント公開', '映画興行': '受賞・興行', 'ランキング・チャート': '受賞・興行', '発行部数': '受賞・興行', '受賞・顕彰': '受賞・興行',
           '会社・経営': 'ビジネス', '決算': 'ビジネス', '市場・産業': 'ビジネス', '政策・行政': '政治',
           '各話レビュー・反応': 'コラム', 'コラム・解説': 'コラム', '海外の反応・海外展開': '海外の反応', 'その他': '未分類'}
SHOW_ORDER = [i for _, its, _ in SHOW for i in its]
GROUP_OF = {i: g for g, its, _ in SHOW for i in its}
def show(tags):
    if ('コラボグッズ' in tags or 'コラボビジュアル公開' in tags) and '飲食・食品コラボ' not in tags:   # グッズ・ビジュアルのコラボは「その他コラボ」に重ねない（飲食のコラボは残す）
        tags = [x for x in tags if x != '企業・自治体・観光コラボ']
    out = []
    for x in tags:
        y = TO_SHOW.get(x, x)
        if y in SHOW_ORDER and y not in out: out.append(y)
    out.sort(key=SHOW_ORDER.index)
    if len(out) > 1 and '未分類' in out: out.remove('未分類')
    return out or ['未分類']
# 先行カット・あらすじの記事は載せない（収集でも外しているが、制作決定ニュースから写した記事もあるので念のため）
SKIP = re.compile(r'先行カット|先行場面カット|場面カット|あらすじ|先行公開(?:カット|場面)|次回予告|^[^：:]{1,60}[：:]\s*第\s*\d+\s*話\s*[「『]|第\s*\d+\s*話\s*[「『][^」』]+[」』]\s*(?:場面|カット|放送|配信|予告)')
START = '2026-10-17'   # 集め始めた日（一覧ページに残っている古い記事は載せない）
# アニメイトタイムズの読者アンケート系の記事（募集・結果発表）は載せない（依頼者の判断、2026-11-17）。作品の公式の人気投票は残す
SURVEY = re.compile(r'アニメイトタイムズでは[^。]{0,80}?(アンケート|募集)')   # 見出しの「アンケート」ではなく、本文の「アニメイトタイムズでは…アンケートを実施／…を大募集」で決める（別の文脈のアンケートは残す）
# アニメ！アニメ！の「〇〇の配信はどこで見れる？」系の記事は載せない（依頼者の判断、2026-11-18）
WHERE = re.compile(r'どこで(見|観)(れ|られ|る)|どこで視聴|(見|観)れる(サブスク|配信)|見放題で(見|観)る方法')


def canon(u):
    """同じ記事かどうかを見るためのリンク：http/https・www・末尾の / の違いと、追跡用の値（utm_ や ?c= や時事通信の &g= など）を外す"""
    from urllib.parse import urlsplit, parse_qsl, urlencode
    p = urlsplit((u or '').strip())
    q = [(k, v) for k, v in parse_qsl(p.query) if not (k.startswith('utm_') or k in DROP_Q)]
    return re.sub(r'^www\.', '', p.netloc.lower()) + p.path.rstrip('/') + ('?' + urlencode(sorted(q)) if q else '')
DROP_Q = {'c', 'g', 'from', 'ref', 'rf', 'fbclid', 'gclid', 'display', 'page', 'cx_testId', 'cx_testVariant', 'cx_artPos', 'via', 'source', 'share'}


def key(u):
    """記事のリンクから番号を作る（分類づけページの key と同じ作り方：UTF-16 の文字ごとに h=h*31+c を32ビットで）"""
    h = 0
    b = u.encode('utf-16-le')
    for i in range(0, len(b), 2):
        h = (h * 31 + int.from_bytes(b[i:i + 2], 'little')) & 0xFFFFFFFF
    def b36(n):
        d = '0123456789abcdefghijklmnopqrstuvwxyz'; s = ''
        while True:
            s = d[n % 36] + s; n //= 36
            if not n: return s
    return 'a' + b36(h) + b36(len(b) // 2)
_lp = os.path.join(HERE, 'data', 'labels.json')
_L = json.load(open(_lp, encoding='utf-8')) if os.path.exists(_lp) else {'labels': {}, 'known': []}
LABELS, KNOWN = _L['labels'], set(_L['known'])

def work(r, t):
    """見出しの作品名（検索のきっかけに出すだけ。MANTANWEB は見出しの頭の「名前：」、ほかは『』）"""
    if r.get('site') == 'MANTANWEB':
        m = re.match(r'([^:「」『』]{1,40}?):', t)
        if m and not re.search(r'^\d|^第|週|ランキング|解説|特集|インタビュー', m.group(1)): return m.group(1).strip()
    m = re.search(r'『([^』]{1,60})』', t) or re.search(r'「([^」]{2,40})」', t)
    return re.sub(r'^(TVアニメ|テレビアニメ|劇場版|劇場アニメ|映画|アニメ)\s*', '', m.group(1)).replace('「', '').replace('」', ' ').strip() if m else ''

items, seen = [], set()
SEEN_T = {}
def _day(d):
    import datetime
    try: return datetime.date.fromisoformat(d).toordinal()
    except Exception: return 0
# MANTANWEB・アニメイトタイムズの自動取得の記事は使わない（依頼者の判断、2026-11-18。サイトの軸を RSS に戻す。過去の版は archive/2026-11-18）
USE_SITES = False
# 大カテゴリは RSS のカテゴリ（依頼者の判断、2026-11-18）。当面は大カテゴリだけで、小カテゴリはこのあと作る。RSS_CATS=False で以前の分け方（SHOW）に戻る
RSS_CATS = True
CAT_ORDER = ['エンタメ', '訃報・人事', '社会', '経済', 'IT', '国際', '中国・韓国', '政治', '地方・地域', 'サイエンス', 'スポーツ', 'その他']
def cat(r):
    c = re.sub(r'×アニメ$', '', r.get('feed') or '')
    return c if c in CAT_ORDER else 'その他'
def records():
    p = os.path.join(HERE, 'data', 'newsall_sites.json')
    if USE_SITES and os.path.exists(p):
        for x in json.load(open(p, encoding='utf-8')):
            yield {'url': x['u'], 'title': x['t'], 'date': x['d'], 'site': x['s'], 'anime': 1, 'lt': x.get('lt', []), 'la': x.get('la'), 'lx': x.get('lx')}
    FI = {f['name']: f for f in json.load(open(os.path.join(HERE, 'feeds.json'), encoding='utf-8'))['feeds']}   # 手がかりの項目はいまの feeds.json から（項目名を変えても効くように）
    p = os.path.join(HERE, 'data', 'rss.jsonl')
    if os.path.exists(p):
        for l in open(p, encoding='utf-8'):
            x = json.loads(l)
            yield {'url': x['u'], 'title': x['t'], 'date': x['d'], 'site': x['s'], 'anime': 0 if FI.get(x.get('feed'), {}).get('anime_title') else 1, 'feed': x.get('feed', ''), 'ceek_items': FI.get(x.get('feed'), {}).get('items', []), 'lt': x.get('lt', []), 'la': x.get('la'), 'lx': x.get('lx'), 'lw': x.get('lw'), 'lv': x.get('lv'), 'rss': 1}
if True:
    for r in records():
        cu = canon(r['url'])   # 同じ記事の重なり（自動取得と RSS、RSS どうし）を1本にする。先に読む自動取得のほうを残す
        if cu in seen: continue
        seen.add(cu)
        t = nf(r.get('title') or r.get('list_title'))
        tk = (re.sub(r'\s', '', nf(r.get('site'))), re.sub(r'[\s　]', '', t))   # 同じサイトで見出しがまったく同じ記事も、前後3日以内なら同じ記事
        dd = SEEN_T.get(tk)
        if dd is not None and r.get('date') and abs(_day(r['date']) - dd) <= 3: continue
        if r.get('date'): SEEN_T[tk] = _day(r['date'])
        if not t or SKIP.search(t) or (r.get('date') or '9') < START: continue
        if r.get('site') == 'アニメイトタイムズ' and SURVEY.search(nf(r.get('body', ''))): continue
        if r.get('rss') and not is_anime_title(t, r.get('site', '')): continue   # RSS：見出しだけで決める（RSS の文章は記事の途中の抜き出しが多いので使わない）。アニメ専門サイトは残す（rules.py、2026-11-19）
        if not r.get('anime') and not ANIME.search(t): continue
        if NOT_ANIME.search(t) and not ANIME.search(t): continue   # 特撮・スポーツ・株など（rules.py の NOT_ANIME）   # 見出しにアニメの語がない（anime_title の RSS）。RSS は「アニメ」で検索したものなので書き出しにはほぼ必ずアニメの語があり、手がかりにならない   # アニメ欄以外の一覧（映画欄）の実写映画など
        if 'アニメ!アニメ!' in nf(r.get('site')) and WHERE.search(t): continue
        lab = LABELS.get(key(r['url']))
        if lab and lab.get('x'): continue   # 「載せない」と分類された記事
        n = work(r, t)
        # 作品名・催しの名前などの中の言葉では項目を決めない（『死亡遊戯で飯を食う。』が訃報になる）：『』の中身と、MANTANWEB の見出しの頭の作品名「名前：」を外して判定する
        # 【インタビュー】【レビュー】などの【】は記事の種類なので残す。「」は催し・店の名前（「animate cafe 香港」）にも使われるので残す
        ct = re.sub(r'『[^』]*』', '、', t)
        if r.get('site') == 'MANTANWEB' and n and t.startswith(n) and not re.search(r'フェス|展|イベント|カフェ|ショップ|チャンネル|ネイション|Con|祭|(監督|社長|プロデューサー|P|役|さん)$', n): ct = ct[len(n):].lstrip(':： ')
        tags = [i for g, i, rx in RX if rx.search(ct)] or ['その他']
        lt = [x for x in (r.get('lt') or []) if x not in tags and x in LEAD_ITEMS]   # 書き出し（最初の200字）で当たった項目（rules.py の LEAD_ITEMS だけ）
        if lt: tags = [x for x in tags if x != 'その他'] + lt
        if r.get('ceek_items') and not set(tags) & set(r['ceek_items']): tags = [x for x in tags if x != 'その他'] + [r['ceek_items'][0]]   # RSS の手がかり（feeds.json の items。訃報・人事の RSS なら訃報か会社・経営のどちらかには入れる）
        if '制作決定（テレビアニメ化）' in tags:   # テレビアニメ化／映画化／その他（続編・配信・OVA など）の1つにする
            movie = re.search(r'劇場|映画', ct)
            tv = not movie and re.search(r'(テレビ|TV)アニメ化|(テレビ|TV)アニメ(制作|製作)?決定|(テレビ|TV)アニメ(として|が)?(制作|製作)|アニメ化', ct) and not re.search(r'OVA|OAD|配信アニメ|ショートアニメ|続編|第\s*\d+\s*期|' + N + r'{1,2}期|シーズン|Season|新シリーズ|新作', ct)
            keep = '制作決定（映画化）' if movie else '制作決定（テレビアニメ化）' if tv else '制作決定（その他）'
            tags = [x for x in tags if not x.startswith('制作決定') or x == keep]
        if '原画展' in tags and '展覧会' in tags and not re.search(r'展覧会|ミュージアム|美術館|博物館|企画展|特別展', ct): tags.remove('展覧会')
        if '先行上映' in tags and '上映会' in tags and not re.search(r'上映会|応援上映|IMAX|4DX', ct): tags.remove('上映会')
        if '無料配信' in tags and '配信' in tags: tags.remove('配信')
        if '決算' in tags and '会社・経営' in tags and not re.search(r'買収|合併|出資|提携|人事|社長|就任|設立', ct): tags.remove('会社・経営')
        if 'コラボビジュアル公開' in tags and 'ビジュアル公開' in tags: tags.remove('ビジュアル公開')
        if 'コラボグッズ' in tags and 'グッズ・アパレル・雑貨' in tags: tags.remove('グッズ・アパレル・雑貨')
        if '再上映' in tags and '上映会' in tags and not re.search(r'上映会|応援上映', ct): tags.remove('上映会')
        if '再放送・再配信' in tags:   # 新作以外の放送・配信は「再放送・再配信」だけに（依頼者の判断、2026-11-18）
            tags = [x for x in tags if x not in ('放送・公開日', '配信', 'テレビ放送')]
        if 'フィギュア・模型' in tags and 'ビデオソフト' in tags and not re.search(r'Blu-ray|ブルーレイ|DVD', ct): tags.remove('ビデオソフト')
        # アイテム情報の整理（依頼者の分類から、2026-11-18）
        if '音楽ソフト' in tags and re.search(r'首位|ランクイン|\d+位|チャート|スコープ', ct): tags.remove('音楽ソフト')
        if 'グッズ・アパレル・雑貨' in tags and (re.search(r'コラボ|×', ct) or '展覧会' in tags or '原画展' in tags or 'その他' in tags): tags.remove('グッズ・アパレル・雑貨')   # コラボ商品はコラボ情報、展覧会の物販はイベント情報の側
        if 'グッズ・アパレル・雑貨' in tags and set(tags) & {'入場者特典', 'フェア・ポップアップ', 'くじ', 'ビデオソフト', '音楽ソフト', '書籍', '雑誌特集', '劇場販売商品'} and not re.search(r'グッズ|商品|アパレル|雑貨', ct): tags.remove('グッズ・アパレル・雑貨')
        if '放送・公開日' in tags and re.search(r'(映画|劇場版|劇場アニメ).{0,40}(公開決定|上映決定|上映も決定|\d{4}年公開)', t) and not any(x.startswith('制作決定') for x in tags): tags.append('制作決定（映画化）')   # 映画の「公開決定」は映画化の知らせ（依頼者の分類から）
        if '音楽ソフト' in tags and re.search(r'ワンツー|上位|トップ\d*|ランキング', ct): tags.remove('音楽ソフト')
        if '配信' in tags and re.search(r'配信リリース|配信シングル|(曲|シングル|アルバム).{0,15}配信', ct) and not re.search(r'Netflix|ABEMA|dアニメ|Prime|U-NEXT|DMM|Hulu|Lemino|ディズニー', ct): tags.remove('配信')
        if '配信' in tags and '放送・公開日' in tags and re.search(r'配信開始|配信スタート|より配信|から配信', ct) and not re.search(r'見放題|独占配信|一挙', ct): tags.remove('配信')   # 新作の配信開始日は放送・公開日（依頼者の分類から）
        if '飲食・食品コラボ' in tags and 'グッズ・アパレル・雑貨' in tags: tags.remove('グッズ・アパレル・雑貨')
        if '企業・自治体・観光コラボ' in tags and re.search(r'映像|PV|ビジュアル|イラスト|描き下ろし|CM|ムービー|×.{0,25}コラボ|コラボ(決定|始動|企画)', ct) and not re.search(r'カフェ|メニュー|フード|店|ショップ|スタンプラリー|観光|旅|湯|ホテル|鉄道|駅|SA|PA|福袋|グッズ|商品|発売|販売|ナレーション|ガイド', ct):
            tags = [x for x in tags if x != '企業・自治体・観光コラボ'] + (['コラボビジュアル公開'] if 'コラボビジュアル公開' not in tags else [])   # 作品どうし・作品とイベントのコラボ告知や映像はコラボビジュアル（依頼者の分類から）
        if 'インタビュー' in tags and '企業・自治体・観光コラボ' in tags: tags.remove('企業・自治体・観光コラボ')
        if '展覧会' in tags and '展示情報' in tags: tags.remove('展示情報')
        if 'コメント' in tags and re.search(r'コメントも[\s　]*$', ct) and not re.search(r'コメント(到着|公開|が到着)', ct): tags.remove('コメント')
        if '主題歌・音楽' in tags and re.search(r'首位|ランクイン|\d+位|スコープ', ct): tags.remove('主題歌・音楽')
        if 'インタビュー' in tags:   # インタビュー記事には、話題に出た配役・監督・主題歌などの項目を付けない（依頼者の分類から、2026-11-18）
            tags = [x for x in tags if x not in ('キャスト公開', 'スタッフ', '原作', 'コラム・解説', '主題歌・音楽', '声優ニュース')]
        if 'フィギュア・模型' in tags and 'グッズ・アパレル・雑貨' in tags and not re.search(r'グッズ|アクリル|ぬいぐるみ|雑貨|アパレル', ct): tags.remove('グッズ・アパレル・雑貨')
        if 'フィギュア・模型' in tags and '展示情報' in tags and re.search(r'魂ネイション|ワンフェス|展示会', ct): tags.remove('展示情報')
        if '声優ニュース' in tags and 'キャスト公開' in tags and not re.search(r'結婚|出産|休業|活動休止|療養|復帰|写真集|ラジオ|生誕|誕生日|退所|卒業|グラビア', ct): tags.remove('声優ニュース')
        if ('上映会' in tags or '舞台あいさつ' in tags) and '放送・公開日' in tags and not re.search(r'公開日|公開決定|上映決定|上映開始|放送', ct): tags.remove('放送・公開日')
        if 'イベントレポート' in tags and 'コラム・解説' in tags and not re.search(r'コラム|解説|考察|なぜ|分析|読み解く', ct): tags.remove('コラム・解説')
        if 'ランキング・チャート' in tags and ('映画興行' in tags or '発行部数' in tags): tags.remove('ランキング・チャート')   # 興行・部数の順位はそちらに（ランキングは、それらを含まない○位・ランキング）
        g = show(tags)
        if lab and lab.get('r') and '全体' not in lab['r']:   # 大カテゴリごとに付けた分類：見た大カテゴリの分だけ差し替え、ほかは規則の判定
            g = show([x for x in g if GROUP_OF.get(x) not in lab['r']] + [x for x in show(lab.get('g', [])) if GROUP_OF.get(x) in lab['r']])
        elif lab:   # 全体で付けた分類は、その分類＋分類を付けたあとに増えた項目の規則の判定
            g = show([x for x in lab.get('g', [])] + [x for x in tags if x not in KNOWN and x != 'その他'])
        if RSS_CATS: g = [cat(r)]   # 当面は RSS のカテゴリだけを大カテゴリにする（細かい判定は下の k に残す）
        e = {'d': r.get('date') or '', 't': r.get('title') or t, 'u': r['url'], 's': r.get('site') or '', 'g': g}
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
SAME = 0.25   # 2026-11-18 依頼者「もっとカジュアルにまとめて」で 0.4 → 0.25
SAME_BR = 0.12   # 「」『』の中身（4文字以上）が同じなら、これだけ重なればまとめる
def brs(t): return {x for x in re.findall(r'[「『]([^」』]{4,60})[」』]', nf(t))}
def mark(t): return tuple(re.findall(r'第\s*\d+\s*[弾回話期章部]|前編|後編|中編|\d+日目', nf(t)))
clusters = []   # [代表, [記事...], 組の集合]
for e in sorted(items, key=lambda e: (e['d'], e['u'])):
    b, dd, br = bigr(e['t']), day(e['d']), brs(e['t'])
    best, bs = None, 0
    for c in clusters[-400:]:
        if abs(day(c[0]['d']) - dd) > 4: continue
        if e.get('n') and c[0].get('n') and re.sub(r'\s', '', e['n']) != re.sub(r'\s', '', c[0]['n']): continue
        if e['s'] in {x['s'] for x in c[1]}: continue   # 同じサイトは同じ話を2度載せないので、まとめるのは違うサイトの記事だけ
        if mark(e['t']) != mark(c[0]['t']) and mark(e['t']) and mark(c[0]['t']): continue   # 第2弾と第3弾、前編と後編
        sim = 2 * len(b & c[2]) / max(1, len(b) + len(c[2]))
        if br & c[3] and sim >= SAME_BR: sim = max(sim, SAME)
        if sim > bs: best, bs = c, sim
    if best and bs >= SAME: best[1].append(e); best[3] |= br
    else: clusters.append([e, [e], b, brs(e['t'])])
out = []
for c in clusters:
    es = c[1]
    m = max(es, key=lambda x: (x['s'] in ('MANTANWEB', 'アニメイトタイムズ'), len(x['t'])))   # 代表：アニメの専門サイトの、見出しの長いもの
    r = dict(m); r['d'] = min(x['d'] for x in es if x['d']) if any(x['d'] for x in es) else m['d']
    r['g'] = sorted({x for e in es for x in e['g']}, key=lambda x: CAT_ORDER.index(x) if x in CAT_ORDER else 99) if RSS_CATS else show([x for e in es for x in e['g']])
    if len(es) > 1: r['o'] = [[x['s'], x['u'], x['t']] for x in es if x is not m]; r['c'] = len(es)
    out.append(r)
items = sorted(out, key=lambda e: (e['d'], e['u']), reverse=True)
groups = [[c, [c]] for c in CAT_ORDER if any(c in e['g'] for e in items)] if RSS_CATS else [[g, its] + ([1] if sub else []) for g, its, sub in SHOW]   # 3つ目が 1 の大カテゴリは、小カテゴリを選んだときだけ記事を出す
json.dump({'groups': groups, 'items': items}, open(OUT, 'w', encoding='utf-8'), ensure_ascii=False, separators=(',', ':'))
from collections import Counter
c = Counter(x for e in items for x in e['g'])
print('書き出し', len(items), '件 →', OUT)
for g, its, *_ in groups: print(' ', g, '：', '、'.join(f'{i} {c[i]}' for i in its))
