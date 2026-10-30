# 翻牌（Memorama）測試：兩人規則（純規則函式）、單人完整一局與計分、成績上傳／失敗補送、同一台兩人對戰、設定每個值
import sys, re, json
from playwright.sync_api import sync_playwright
import common
from common import *

R = Runner()

FAKE_FB = r"""
(function(){
  window.__db = window.__db || {}; window.__ops = window.__ops || [];
  if (window.firebase && window.firebase.__fake) return;
  const DB = window.__db, ops = window.__ops, clone = x => JSON.parse(JSON.stringify(x));
  const depth = p => p.split('/').length;
  function docRef(path){ return { path, id: path.split('/').pop(),
    async get(){ return { exists: path in DB, data: () => DB[path] && clone(DB[path]) }; },
    async set(d){ ops.push({k:'set', p:path, d:clone(d)}); DB[path] = clone(d); },
    async update(d){ DB[path] = Object.assign(DB[path]||{}, clone(d)); },
    async delete(){ delete DB[path]; },
    onSnapshot(){ return () => {}; } }; }
  function colRef(path){ const q = { doc: id => docRef(path + '/' + id),
    async add(d){ if (window.__failAdd) throw new Error('add-fail'); ops.push({k:'add', p:path, d:clone(d)}); const id = 'A' + ops.length; DB[path + '/' + id] = clone(d); return { id }; },
    where(){ return q; }, orderBy(){ return q; }, limit(){ return q; },
    async get(){ const ks = Object.keys(DB).filter(k => k.startsWith(path + '/') && depth(k) === depth(path) + 1);
      const rows = ks.map(k => clone(DB[k])).sort((a,b)=>(b.score||0)-(a.score||0));
      return { empty: rows.length === 0, docs: rows.map(r => ({ data: () => r })), size: rows.length, forEach(fn){ rows.forEach(r => fn({ data: () => r })); } }; } };
    return q; }
  const auth = { currentUser: null, async signInAnonymously(){ auth.currentUser = { uid: window.__uid || 'UID1' }; return { user: auth.currentUser }; } };
  const fsInst = { collection: colRef, async runTransaction(fn){ return fn({ get: r => r.get(), set(r, d){ DB[r.path] = clone(d); }, update(r, d){ DB[r.path] = Object.assign(DB[r.path]||{}, clone(d)); } }); } };
  const fire = () => fsInst; fire.FieldValue = { serverTimestamp: () => 'TS', delete: () => null, increment: () => 1 };
  fire.Timestamp = { now: () => ({ toMillis: () => Date.now() }), fromMillis: m => ({ toMillis: () => m }) };
  window.firebase = { __fake: true, apps: [], auth: () => auth, firestore: fire, initializeApp(){ return {}; } };
})();
"""
def route(r):
    u = r.request.url
    if u.startswith('file:'): return r.continue_()
    if 'gstatic.com/firebasejs' in u:
        if common.BLOCK_FB: return r.abort()
        return r.fulfill(status=200, content_type='application/javascript', body=FAKE_FB if 'firebase-app-compat' in u else '')
    r.abort()
common.BLOCK_FB = False
common.route = route

def page(p, query='', settings=None, mode=None, flags=None, width=1100, height=800):
    init = "window.confirm=()=>true;"
    if mode: init += "localStorage.setItem('memorama_mode',%s);" % json.dumps(mode)
    for k, v in (flags or {}).items(): init += "window.%s=%s;" % (k, json.dumps(v))
    return open_page(p, query, settings=settings, width=width, height=height, wait=1500, extra_init=init)

def solo_start(pg, name='Ana'):
    pg.fill('#player-name', name); pg.click('#confirm-name-btn'); pg.wait_for_timeout(400)

def pairs_of(pg):
    return pg.evaluate("""()=>{ const m={}; [...board.querySelectorAll('.card')].forEach((c,i)=>{(m[c.dataset.id]=m[c.dataset.id]||[]).push(i);}); return Object.values(m); }""")

def flip(pg, i): pg.evaluate("(i)=>board.querySelectorAll('.card')[i].click()", i)

with sync_playwright() as p:
    # ───── 1) 純規則：計分 ─────
    b, pg, errs = page(p)
    for args, want in (((18, 18, 0), 1000), ((18, 18, 60), 940), ((18, 36, 100), 550), ((18, 18, 300), 700), ((18, 18, 999), 700), ((18, 100, 50), 376)):
        got = pg.evaluate("(a)=>calculateScore(a[0],a[1],a[2])", list(args))
        R.check(got == want, f'單人計分 {args[0]}對/{args[1]}步/{args[2]}秒 → {want}（得 {got}）')
    # ───── 2) 純規則：兩人輪流（對戰／合作）─────
    st = pg.evaluate("""()=>{ const s={deck:['1i','1t','2i','2t','3i','3t','4i','4t'],matched:Array(8).fill(-1),open:[],openBy:-1,turn:0,scores:[0,0],moves:0,lastFlip:null,status:'playing',flipSeq:0}; window.__s=s; return s; }""")
    def ap(i, who, typ='vs', s='window.__s'):
        return pg.evaluate("([i,w,t,sn])=>{const n=applyFlip(window[sn]||window.__s,i,w,t); return n;}", [i, who, typ, '__s'])
    R.check(pg.evaluate("applyFlip(__s,0,1,'vs')") is None, '不是你的回合翻牌：不接受')
    R.check(pg.evaluate("applyFlip(__s,99,0,'vs')") is None and pg.evaluate("applyFlip(__s,-1,0,'vs')") is None, '翻不存在的牌：不接受')
    pg.evaluate("window.__a=applyFlip(__s,0,0,'vs')")
    R.check(pg.evaluate("__a.open") == [0] and pg.evaluate("__a.openBy") == 0, '翻第一張：open=[0]')
    R.check(pg.evaluate("applyFlip(__a,0,0,'vs')") is None, '重複翻同一張：不接受')
    pg.evaluate("window.__b=applyFlip(__a,1,0,'vs')")   # 1i,1t 配對成功
    R.check(pg.evaluate("[__b.scores, __b.turn, __b.open, __b.moves]") == [[1, 0], 0, [], 1], '對戰配對成功：該玩家 +1，繼續翻（回合不換）')
    R.check(pg.evaluate("__b.matched.slice(0,2)") == [0, 0], '配到的牌記錄是誰配到')
    R.check(pg.evaluate("applyFlip(__b,0,0,'vs')") is None, '已配對的牌：不能再翻')
    pg.evaluate("window.__c=applyFlip(applyFlip(__b,2,0,'vs'),4,0,'vs')")   # 2i,3i 配錯
    R.check(pg.evaluate("[__c.open.length, __c.turn, __c.moves]") == [2, 0, 2], '配錯：兩張都翻開，等蓋回去才換人')
    R.check(pg.evaluate("applyFlip(__c,6,0,'vs')") is None, '兩張都翻開時不能翻第三張')
    R.check(pg.evaluate("applyCover(__c,999,'vs')") is None, '蓋牌序號不對：忽略（避免重複蓋）')
    pg.evaluate("window.__d=applyCover(__c,__c.flipSeq,'vs')")
    R.check(pg.evaluate("[__d.open.length, __d.turn, __d.openBy]") == [0, 1, -1], '正確序號蓋牌：換對方回合')
    # 合作：配對成功也換人
    pg.evaluate("window.__e=applyFlip(applyFlip(__s,0,0,'coop'),1,0,'coop')")
    R.check(pg.evaluate("[__e.scores, __e.turn]") == [[1, 0], 1], '合作模式配對成功：換對方（兩人翻的次數一樣多）')
    # 結束
    pg.evaluate("""(()=>{ let s={deck:['1i','1t','2i','2t'],matched:Array(4).fill(-1),open:[],openBy:-1,turn:0,scores:[0,0],moves:0,lastFlip:null,status:'playing',flipSeq:0};
      s=applyFlip(s,0,0,'vs'); s=applyFlip(s,1,0,'vs'); s=applyFlip(s,2,0,'vs'); s=applyFlip(s,3,0,'vs'); window.__f=s; })()""")
    R.check(pg.evaluate("[__f.status, __f.scores]") == ['finished', [2, 0]], '全部配完：status=finished、分數 2:0')
    R.check(pg.evaluate("applyFlip(__f,0,0,'vs')") is None, '遊戲結束後不能再翻')
    R.check(not errs, '沒有網頁錯誤 %s' % errs)
    b.close()

    # ───── 3) 單人：名字必填、一局流程 ─────
    b, pg, errs = page(p)
    pg.click('#confirm-name-btn'); pg.wait_for_timeout(200)
    R.check(pg.is_visible('#name-screen') and pg.inner_text('#name-error').strip() != '', '沒填名字：不開始，顯示提示')
    solo_start(pg, 'Ana')
    R.check(pg.is_visible('#game-screen') and pg.evaluate("isPlaying"), '填名字後開始')
    R.check(pg.evaluate("board.querySelectorAll('.card').length") == 36, '36 張牌（18 組）')
    pr = pairs_of(pg)
    R.check(len(pr) == 18 and all(len(x) == 2 for x in pr), '18 個詞各有 2 張')
    R.check(pg.evaluate("[...board.querySelectorAll('.card')].every(c=>c.dataset.type==='img' || c.dataset.type==='text')") and
            all(pg.evaluate("(a)=>[board.querySelectorAll('.card')[a[0]].dataset.type,board.querySelectorAll('.card')[a[1]].dataset.type].sort().join()", x) == 'img,text' for x in pr), '每組一張圖＋一張字')
    # 配錯 → 再點任一張會立刻蓋回去
    a, c = pr[0][0], pr[1][0]
    flip(pg, a); flip(pg, c); pg.wait_for_timeout(100)
    R.check(pg.evaluate("moves") == 1 and pg.evaluate("pendingMismatch !== null"), '翻兩張不同的：步數 1、等待蓋回')
    flip(pg, pr[2][0]); pg.wait_for_timeout(100)
    R.check(pg.evaluate("document.querySelectorAll('.card.flipped').length") == 1, '配錯後直接點下一張：舊的兩張立刻蓋回，只剩新翻的一張')
    flip(pg, pr[2][1]); pg.wait_for_timeout(100)
    R.check(pg.evaluate("matchedPairs") == 1 and pg.evaluate("document.querySelectorAll('.card.matched').length") == 2, '翻到一組：配對成功、2 張標記 matched')
    R.check(pg.evaluate("flippedCards.length") == 0, '配對後可繼續翻')
    # 已配對的牌再點：沒反應
    m0 = pg.evaluate("moves"); flip(pg, pr[2][0]); R.check(pg.evaluate("moves") == m0 and pg.evaluate("flippedCards.length") == 0, '點已配對的牌：沒反應')
    # 同一張連點兩下不算兩張
    flip(pg, pr[3][0]); flip(pg, pr[3][0]); R.check(pg.evaluate("flippedCards.length") == 1, '同一張連點：只算一張')
    # 完成剩下全部
    flip(pg, pr[3][1])
    for pair in pr[4:] + [pr[0], pr[1]]:
        flip(pg, pair[0]); flip(pg, pair[1])
    pg.wait_for_timeout(1500)
    R.check(pg.evaluate("matchedPairs") == 18, '18 組全配完')
    R.check(pg.is_visible('#score-modal'), '跳出結算視窗')
    mv, tm = pg.evaluate("moves"), pg.evaluate("timer")
    want = pg.evaluate("(a)=>calculateScore(18,a[0],a[1])", [mv, tm])
    R.check(pg.inner_text('#final-score') == str(want), f'結算分數＝公式：{want}（{mv} 步 {tm} 秒）')
    pg.wait_for_timeout(500)
    ops = [o for o in pg.evaluate("window.__ops") if o['k'] == 'add' and o['p'] == 'memory_game_leaderboard']
    R.check(len(ops) == 1, '成績上傳排行榜一筆')
    if ops:
        d = ops[0]['d']
        R.check(d['name'] == 'Ana' and d['score'] == want and d['moves'] == mv and d['script'] == 'trad' and d['lang'] == 'es', '上傳內容：名字、分數、步數、字形、語言正確：%s' % {k: d[k] for k in ('name', 'score', 'moves', 'script', 'lang')})
    R.check(pg.evaluate("readQueue().length") == 0, '上傳成功：待補送佇列是空的')
    pg.click('#show-leaderboard-from-score-btn'); pg.wait_for_timeout(500)
    R.check('Ana' in pg.inner_text('#leaderboard-list'), '排行榜視窗列出 Ana')
    pg.click('#close-leaderboard-btn'); pg.wait_for_timeout(200)
    R.check(not pg.is_visible('#leaderboard-modal'), '關閉排行榜視窗')
    pg.click('#start-btn'); pg.wait_for_timeout(400)      # 側欄的「重新開始」
    R.check(pg.evaluate("[moves, matchedPairs, timer]") == [0, 0, 0] and pg.evaluate("isPlaying") and not pg.is_visible('#score-modal'), '重新開始：步數／配對／時間歸零')
    R.check(not errs, '沒有網頁錯誤 %s' % errs)
    b.close()

    # ───── 4) 上傳失敗：存進本機，恢復後補送 ─────
    b, pg, errs = page(p, flags={'__failAdd': True})
    solo_start(pg, 'Bo')
    for pair in pairs_of(pg): flip(pg, pair[0]); flip(pg, pair[1])
    pg.wait_for_timeout(1800)
    R.check(pg.evaluate("readQueue().length") == 1 and pg.evaluate("readQueue()[0].name") == 'Bo', '上傳失敗：成績存進本機待補送佇列')
    R.check(pg.inner_text('#save-status').strip() != '', '結算視窗顯示「稍後補送」狀態：' + pg.inner_text('#save-status'))
    pg.evaluate("window.__failAdd=false; window.dispatchEvent(new Event('online'))"); pg.wait_for_timeout(800)
    R.check(pg.evaluate("readQueue().length") == 0 and len([o for o in pg.evaluate("window.__ops") if o['k'] == 'add']) == 1, '恢復連線（online 事件）：自動補送，佇列清空')
    b.close()
    # 完全沒有 Firebase
    common.BLOCK_FB = True
    b, pg, errs = page(p)
    solo_start(pg, 'Cy')
    for pair in pairs_of(pg): flip(pg, pair[0]); flip(pg, pair[1])
    pg.wait_for_timeout(1800)
    R.check(pg.is_visible('#score-modal') and pg.evaluate("readQueue().length") == 1, '沒有 Firebase：照常結算，成績留在本機佇列')
    pg.click('#show-leaderboard-from-score-btn'); pg.wait_for_timeout(300)
    R.check(pg.inner_text('#leaderboard-loading').strip() != '', '排行榜打不開：顯示連線失敗')
    R.check(not errs, '沒有網頁錯誤 %s' % errs)
    b.close()
    common.BLOCK_FB = False

    # ───── 5) 同一台兩人對戰 ─────
    b, pg, errs = page(p, mode='local')
    R.check(pg.is_visible('#player2-name'), '同一台模式：出現第二位玩家名字欄')
    pg.fill('#player-name', 'Ana'); pg.click('#confirm-name-btn'); pg.wait_for_timeout(200)
    R.check(pg.is_visible('#name-screen') and pg.inner_text('#name-error').strip() != '', '只填一個名字：不開始，提示兩人都要填')
    pg.fill('#player2-name', 'Bea'); pg.click('#confirm-name-btn'); pg.wait_for_timeout(500)
    R.check(pg.is_visible('#game-screen') and pg.evaluate("MP.kind") == 'local', '兩個名字都填：開始同一台對戰')
    R.check(pg.evaluate("MP.names") == ['Ana', 'Bea'] and pg.evaluate("MP.s.turn") == 0, '玩家 Ana、Bea；第一局 Ana 先')
    deck = pg.evaluate("MP.s.deck")
    ids = {}
    for i, c in enumerate(deck): ids.setdefault(int(c[:-1]), []).append(i)
    prs = list(ids.values())
    # 用真的點牌：Ana 配對成功仍是 Ana 的回合
    pg.evaluate("(a)=>{board.querySelectorAll('.card')[a[0]].click(); board.querySelectorAll('.card')[a[1]].click();}", prs[0])
    pg.wait_for_timeout(100)
    R.check(pg.evaluate("[MP.s.scores, MP.s.turn]") == [[1, 0], 0], '點兩張相同的：Ana +1，還是 Ana 的回合')
    # 配錯：1.5 秒後自動蓋回並換人（真實等待一次）
    pg.evaluate("(a)=>{board.querySelectorAll('.card')[a[0]].click(); board.querySelectorAll('.card')[a[1]].click();}", [prs[1][0], prs[2][0]])
    pg.wait_for_timeout(300)
    R.check(pg.evaluate("MP.s.open.length") == 2 and pg.evaluate("MP.s.turn") == 0, '配錯：兩張翻開著')
    pg.evaluate("(i)=>board.querySelectorAll('.card')[i].click()", prs[3][0]); pg.wait_for_timeout(100)
    R.check(pg.evaluate("MP.s.open.length") == 2, '翻開著的時候點第三張：不接受')
    pg.wait_for_timeout(2300)
    R.check(pg.evaluate("[MP.s.open.length, MP.s.turn]") == [0, 1], '約 2 秒後自動蓋回，換 Bea')
    # Bea 全部配走剩下的 → 結束；比分 1:17 Bea 贏
    for pr_ in prs[1:]:
        pg.evaluate("(a)=>{const c=board.querySelectorAll('.card'); if(MP.s.status==='playing'){mpTap(a[0]);mpTap(a[1]);}}", pr_)
    pg.wait_for_timeout(1500)
    R.check(pg.evaluate("MP.s.status") == 'finished' and pg.evaluate("MP.s.scores") == [1, 17], '全部配完：比分 1:17')
    R.check(pg.is_visible('#score-modal') and 'Bea' in pg.inner_text('#end-title'), '結算視窗宣布贏家 Bea：' + pg.inner_text('#end-title'))
    R.check(pg.inner_text('#vs-score').replace(' ', '') in ('1:17',), '顯示比分 1:17')
    pg.click('#play-again-btn'); pg.wait_for_timeout(500)
    R.check(pg.evaluate("MP.s.turn") == 1 and pg.evaluate("MP.s.scores") == [0, 0], '再玩一局：分數歸零，換 Bea 先手（輪流先手）')
    # 平手 9:9
    ids = {}
    for i, c in enumerate(pg.evaluate("MP.s.deck")): ids.setdefault(int(c[:-1]), []).append(i)
    prs = list(ids.values())
    seq = []
    pg.evaluate("""(prs)=>{ // Bea(1) 先手：配 9 組，故意配錯一次換 Ana，Ana 配 9 組
      for(let k=0;k<9;k++){ mpTap(prs[k][0]); mpTap(prs[k][1]); }
      mpTap(prs[9][0]); mpTap(prs[10][0]); mpCover(MP.s.flipSeq);
      for(let k=9;k<18;k++){ mpTap(prs[k][0]); mpTap(prs[k][1]); } }""", prs)
    pg.wait_for_timeout(1500)
    R.check(pg.evaluate("MP.s.scores") == [9, 9] and pg.evaluate("MP.s.status") == 'finished', '9:9 平手（先手 Bea 9 組、換 Ana 9 組）')
    R.check(pg.inner_text('#end-title').strip() == pg.evaluate("t('tie')"), '平手顯示「平手」：' + pg.inner_text('#end-title'))
    R.check(not errs, '沒有網頁錯誤 %s' % errs)
    b.close()

    # ───── 6) 連線模式：沒有網路時不當掉 ─────
    common.BLOCK_FB = True
    b, pg, errs = page(p, mode='ovs')
    pg.fill('#player-name', 'Ana'); pg.click('#create-room-btn'); pg.wait_for_timeout(800)
    R.check(pg.is_visible('#name-screen') and pg.inner_text('#name-error').strip() != '', '沒網路按「建立房間」：留在首頁並顯示錯誤：' + pg.inner_text('#name-error')[:40])
    pg.fill('#player-name', ''); pg.click('#create-room-btn'); pg.wait_for_timeout(300)
    R.check(pg.inner_text('#name-error').strip() != '', '沒名字按建立房間：提示')
    b.close()
    common.BLOCK_FB = False

    # ───── 7) 設定每個值 ─────
    PY = re.compile('[āáǎàēéěèīíǐìōóǒòūúǔùǖǘǚǜ]'); ZY = re.compile('[ㄅ-ㄩ]')
    base = {'v': 1, 'script': 'trad', 'lang': 'es', 'phon': 'pinyin', 'rate': 'normal'}
    for key, vals in (('script', ['trad', 'simp']), ('lang', ['es', 'en', 'zh']), ('phon', ['pinyin', 'zhuyin', 'both', 'off']), ('rate', ['slow', 'normal', 'fast'])):
        for v in vals:
            label = f'{key}={v}'
            b, pg, errs = page(p, settings=dict(base, **{key: v}))
            btn = pg.inner_text('#confirm-name-btn')
            if key == 'lang':
                if v == 'zh': R.check(not re.search('[A-Za-zÁÉÍÓÚñ]{3,}', btn), f'{label}：純中文按鈕「{btn}」')
                else: R.check(btn == pg.evaluate("UI['%s'].enter" % v), f'{label}：按鈕「{btn}」')
            solo_start(pg, 'Ana')
            info = pg.evaluate("""()=>{ const c=[...board.querySelectorAll('.card[data-type=text]')][0]; const it=vocabById[c.dataset.id];
              return { hz:c.querySelector('.hanzi').textContent, ph:c.querySelector('.phon').textContent, it:{trad:it.trad,simp:it.simp,pinyin:it.pinyin,zhuyin:it.zhuyin}, id:c.dataset.id }; }""")
            if key == 'script': R.check(info['hz'] == (info['it']['simp'] if v == 'simp' else info['it']['trad']), f'{label}：字卡字形「{info["hz"]}」')
            if key == 'phon':
                ph = info['ph']
                got = (bool(PY.search(ph)) or (v == 'pinyin' and bool(re.search('[a-z]', ph))), bool(ZY.search(ph)))
                want = {'pinyin': (True, False), 'zhuyin': (False, True), 'both': (True, True), 'off': (False, False)}[v]
                R.check(got == want, f'{label}：字卡讀音「{ph.replace(chr(10), "/")}」')
            if key == 'rate':
                pg.evaluate("window.__spoken.length=0"); pg.evaluate("flipCard(board.querySelectorAll('.card')[0])")
                r = pg.evaluate("window.__spoken.map(s=>s.rate)"); want_r = {'slow': 0.45, 'normal': 0.65, 'fast': 0.85}[v]
                R.check(r and abs(r[-1] - want_r) < 1e-6, f'{label}：翻牌念出速度 {r[-1] if r else None}（應為 {want_r}）')
            R.check(not errs, f'{label}：沒有網頁錯誤 {errs}')
            b.close()
    # 面板點選 → 存檔；牌面即時更新；數字開關
    b, pg, errs = page(p, settings=base)
    solo_start(pg, 'Ana')
    for k, v in (('script', 'simp'), ('phon', 'zhuyin'), ('lang', 'en'), ('rate', 'fast')):
        pg.evaluate("(a)=>changeSetting(a[0],a[1])", [k, v])
        R.check(json.loads(pg.evaluate("localStorage.getItem('hanziGames.settings')"))[k] == v, f'改 {k}={v}：存進共用設定')
    hz = pg.evaluate("(()=>{const c=[...board.querySelectorAll('.card[data-type=text]')][0]; return [c.querySelector('.hanzi').textContent, vocabById[c.dataset.id].simp, c.querySelector('.phon').textContent, vocabById[c.dataset.id].zhuyin]})()")
    R.check(hz[0] == hz[1] and hz[2] == hz[3], '遊戲中改設定：牌面字形與讀音立刻跟著變')
    pg.evaluate("changeSetting('nums','on')"); R.check(pg.evaluate("document.body.classList.contains('show-nums')"), '「顯示牌號」開：body 有 show-nums')
    pg.evaluate("changeSetting('nums','off')"); R.check(not pg.evaluate("document.body.classList.contains('show-nums')"), '「顯示牌號」關')
    # 別的遊戲改設定
    pg.evaluate("localStorage.setItem('hanziGames.settings', JSON.stringify({v:1,script:'trad',lang:'zh',phon:'off',rate:'slow'})); window.dispatchEvent(new StorageEvent('storage',{key:'hanziGames.settings'}))")
    pg.wait_for_timeout(200)
    R.check(pg.evaluate("[settings.script,settings.lang,settings.phon,settings.rate]") == ['trad', 'zh', 'off', 'slow'], '其他遊戲改了共用設定：這邊即時同步')
    b.close()

print('FAILS', R.fails); sys.exit(1 if R.fails else 0)
