// アニメニュース検索：newsall.json を読み、まとまり（色のボタン）・項目（その下のボタン。複数可）・検索・サイトでその場で絞り込む
(function () {
  var $ = function (id) { return document.getElementById(id); };
  var PAGE = 200, all = [], res = [], shown = 0, grp = '', picked = {}, G = {}, GI = {}, groups = [];
  var HUE = window.HUE || {};
  // 項目の印（一覧の左に出す。記事の最初の項目）
  var AB = { '制作決定': '決', '放送・公開日': '日', 'キャスト': '声', 'スタッフ': 'ス', '主題歌・音楽': '♪', 'PV・ビジュアル': 'PV', '原作': '原',
    'イベント': '催', 'グッズ・コラボ': '品', '展示': '展', '配信': '配', '映画興行': '興', 'ランキング': '位', '発行部数': '部', '受賞': '賞',
    '会社・業界': '業', '訃報': '訃', 'インタビュー・コメント': '話', 'レポート・コラム': '記', 'その他': '他' };
  var WD = '日月火水木金土';
  function esc(s) { return String(s || '').replace(/[&<>"]/g, function (c) { return { '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;' }[c]; }); }
  function norm(s) { return String(s || '').normalize('NFKC').toLowerCase().replace(/[\s・!！?？:：~〜～\-－「」『』【】]/g, ''); }
  function hue(i) { return HUE[GI[i]] || 70; }
  function row(e) {
    var m = /^(\d{4})-(\d{2})-(\d{2})/.exec(e.d || ''), i0 = e.g[0];
    var dd = m ? +m[3] + '<small>' + WD[new Date(+m[1], +m[2] - 1, +m[3]).getDay()] + '</small>' : '<span class="dq">—</span>';
    var tags = e.g.map(function (i) { return '<span class="tg ti" data-i="' + esc(i) + '">' + esc(i) + '</span>'; }).join('') +
      (e.n ? '<span class="tg tw" data-n="' + esc(e.n) + '">' + esc(e.n) + '</span>' : '');
    return '<li class="ur sr"><span class="ud">' + dd + '</span>' +
      '<span class="ic" style="--h:' + hue(i0) + '" title="' + esc(i0) + '">' + esc(AB[i0] || '他') + '</span>' +
      '<span class="sb"><a class="un" href="' + esc(e.u) + '" target="_blank" rel="noopener">' + esc(e.t) + '</a>' +
      '<span class="tags">' + tags + '</span></span><span class="st">' + esc(e.s) + '</span></li>';
  }
  var lastG = '';
  function mon(e) { var m = /^(\d{4})-(\d{2})/.exec(e.d || ''); return m ? m[1] + '年' + (+m[2]) + '月' : '日付なし'; }
  function render(more) {
    if (!more) { $('list').innerHTML = ''; shown = 0; lastG = ''; }
    var h = '';
    res.slice(shown, shown + PAGE).forEach(function (e) { var g = mon(e); if (g !== lastG) { h += '<li class="ug">' + esc(g) + '</li>'; lastG = g; } h += row(e); });
    $('list').insertAdjacentHTML('beforeend', h);
    shown = Math.min(shown + PAGE, res.length);
    $('more').hidden = shown >= res.length;
  }
  function subs() {   // 選んだまとまりの項目ボタン
    if (!grp) { $('sub').hidden = true; $('sub').innerHTML = ''; return; }
    $('sub').innerHTML = G[grp].map(function (i) {
      return '<button type="button" data-i="' + esc(i) + '" style="--h:' + hue(i) + '"' + (picked[i] ? ' class="on"' : '') + '>' + esc(i) + '<span class="n"></span></button>';
    }).join('');
    $('sub').hidden = G[grp].length < 2;
  }
  function inGroup(e, g) { return e.g.some(function (i) { return GI[i] === g; }); }
  function search() {
    var terms = $('q').value.split(/\s+/).map(norm).filter(Boolean), site = $('site').value;
    var base = all.filter(function (e) { return (!site || e.s === site) && terms.every(function (t) { return e._t.indexOf(t) >= 0; }); });
    [].forEach.call(document.querySelectorAll('#seg button'), function (b) {
      var g = b.getAttribute('data-g'); b.querySelector('.n').textContent = ' ' + (g ? base.filter(function (e) { return inGroup(e, g); }).length : base.length).toLocaleString();
    });
    var inG = grp ? base.filter(function (e) { return inGroup(e, grp); }) : base;
    [].forEach.call(document.querySelectorAll('#sub button'), function (b) {
      var i = b.getAttribute('data-i'); b.querySelector('.n').textContent = ' ' + inG.filter(function (e) { return e.g.indexOf(i) >= 0; }).length.toLocaleString();
    });
    var ps = Object.keys(picked);
    res = ps.length ? inG.filter(function (e) { return ps.some(function (i) { return e.g.indexOf(i) >= 0; }); }) : inG;
    if ($('old').checked) res = res.slice().reverse();
    $('count').textContent = res.length.toLocaleString() + ' 件 / 全 ' + all.length.toLocaleString() + ' 件';
    render(false);
    var qs = [];
    if ($('q').value) qs.push('q=' + encodeURIComponent($('q').value));
    if (grp) qs.push('g=' + encodeURIComponent(grp));
    if (ps.length) qs.push('i=' + encodeURIComponent(ps.join(',')));
    try { history.replaceState(null, '', qs.length ? '?' + qs.join('&') : location.pathname); } catch (x) {}
  }
  function setGroup(g) {
    grp = g; picked = {};
    [].forEach.call(document.querySelectorAll('#seg button'), function (x) { x.classList.toggle('on', x.getAttribute('data-g') === g); });
    subs();
  }
  fetch(window.NEWS).then(function (r) { return r.json(); }).then(function (j) {
    groups = j.groups || [];
    groups.forEach(function (x) { G[x[0]] = x[1]; x[1].forEach(function (i) { GI[i] = x[0]; }); });
    all = j.items || [];
    all.forEach(function (e) { e._t = norm([e.t, e.n, e.s].join(' ')); });
    var p = new URLSearchParams(location.search);
    if (p.get('q')) $('q').value = p.get('q');
    if (p.get('g') && G[p.get('g')]) { setGroup(p.get('g')); (p.get('i') || '').split(',').forEach(function (i) { if (GI[i] === grp) picked[i] = 1; }); subs(); }
    search();
  });
  var timer;
  $('q').addEventListener('input', function () { clearTimeout(timer); timer = setTimeout(search, 150); });
  ['site', 'old'].forEach(function (id) { $(id).addEventListener('change', search); });
  $('seg').addEventListener('click', function (ev) {
    var b = ev.target.closest('button'); if (!b) return;
    setGroup(b.getAttribute('data-g')); search();
  });
  $('sub').addEventListener('click', function (ev) {
    var b = ev.target.closest('button'); if (!b) return;
    var i = b.getAttribute('data-i');
    if (picked[i]) delete picked[i]; else picked[i] = 1;
    b.classList.toggle('on', !!picked[i]); search();
  });
  $('list').addEventListener('click', function (ev) {   // 記事の下の項目・作品名を押すと、その項目だけ／その作品名で検索
    var t = ev.target.closest('.tg'); if (!t) return;
    if (t.getAttribute('data-n')) { $('q').value = t.getAttribute('data-n'); search(); window.scrollTo(0, 0); return; }
    var i = t.getAttribute('data-i'); if (!i) return;
    setGroup(GI[i]); picked = {}; picked[i] = 1; subs(); search(); window.scrollTo(0, 0);
  });
  $('more').addEventListener('click', function () { render(true); });
})();
