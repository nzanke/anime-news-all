# アニメニュース検索

https://nzanke.github.io/anime-news-all/

アニメのニュースを毎日集め、項目（作品の動き／イベント・商品／配信・成績・受賞／業界・人・記事）で絞り込めるようにしたサイト。

- 30分ごとに `rss.py` が `feeds.json` の RSS を読んで `data/rss.jsonl` に足し、`tag.py` が MANTANWEB・アニメイトタイムズの見出しの一覧 `data/newsall_sites.json`（非公開の anime-database の `articles/newsall_export.py` が毎日作り、anime-world 経由で届く）と合わせて項目に振り分け、`data/newsall.json` を作る（`.github/workflows/pages.yml`）。
- `python3 build.py` で `_site/` に組み立てる。記事の本文は持たない。
