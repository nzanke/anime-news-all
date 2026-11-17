# アニメニュース検索

https://nzanke.github.io/anime-news-all/

アニメのニュースを毎日集め、項目（作品の動き／イベント・商品／配信・成績・受賞／業界・人・記事）で絞り込めるようにしたサイト。

- 一覧のデータ `data/newsall.json` は、毎日の収集（非公開の anime-database の `articles/newsall_collect.py`・`articles/newsall_tag.py`）が公開の anime-world に置くものを、3時間ごとに取ってきて組み立てる（`.github/workflows/pages.yml`）。
- `python3 build.py` で `_site/` に組み立てる。記事の本文は持たない。
