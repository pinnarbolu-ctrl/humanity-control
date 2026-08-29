import os, time, math, json, sqlite3, statistics
from datetime import datetime, timezone, timedelta
import requests

BOT_TOKEN=(os.getenv('BOT_TOKEN','') or os.getenv('TELEGRAM_BOT_TOKEN','')).strip()
CHAT_IDS=[int(x) for x in os.getenv('CHAT_IDS','2097448038').split(',') if x.strip()]
SCAN_SECONDS=60
LOCAL_TZ=timezone(timedelta(hours=3))
REPORT_HOUR=20
LEARNING_DAYS=7
DATA_DIR=os.getenv('DATA_DIR','.').strip() or '.'
os.makedirs(DATA_DIR, exist_ok=True)
DB_PATH=os.path.join(DATA_DIR,'btcturk_market_learning.db')
TICKER_URL='https://api.btcturk.com/api/v2/ticker'
HORIZONS=(15,30,60,180)
MAIN_HORIZON=180


def tg(msg):
    if not BOT_TOKEN:
        print('[TELEGRAM YOK]\n'+msg); return False
    ok=False
    for cid in CHAT_IDS:
        try:
            r=requests.post(f'https://api.telegram.org/bot{BOT_TOKEN}/sendMessage',data={'chat_id':cid,'text':msg},timeout=15)
            print('[TELEGRAM OK]' if r.ok else '[TELEGRAM HATA]',cid,r.text[:200])
            ok=ok or r.ok
        except Exception as e: print('[TELEGRAM EXC]',cid,e)
    return ok


def db():
    c=sqlite3.connect(DB_PATH,timeout=30)
    c.execute('PRAGMA journal_mode=WAL')
    c.execute('PRAGMA synchronous=NORMAL')
    return c


def meta_get(c,k):
    r=c.execute('select value from meta where key=?',(k,)).fetchone(); return r[0] if r else None

def meta_set(c,k,v):
    c.execute('insert into meta(key,value) values(?,?) on conflict(key) do update set value=excluded.value',(k,str(v)))


def setup():
    c=db()
    c.execute('create table if not exists meta(key text primary key,value text)')
    c.execute('''create table if not exists snapshots(
      id integer primary key autoincrement, ts integer not null, symbol text not null,
      price real,bid real,ask real,high24 real,low24 real,open24 real,volume24 real,
      r1 real,r3 real,r5 real,r10 real,r30 real,r60 real,
      vol1 real,vol3 real,vol5 real,vol10 real,vr15 real,vr310 real,
      btc3 real,btc10 real,btc60 real,rsi14 real,ema12gap real,ema26gap real,macdgap real,
      stair5 real,range24 real,spread real, unique(ts,symbol))''')
    c.execute('create index if not exists ix_ss on snapshots(symbol,ts)')
    c.execute('''create table if not exists outcomes(
      snapshot_id integer,horizon integer,symbol text,ts integer,ret_end real,max_up real,max_down real,
      hit4 integer,hit7 integer,hit10 integer,
      primary key(snapshot_id,horizon))''')
    cols=[r[1] for r in c.execute('pragma table_info(outcomes)').fetchall()]
    if 'hit10' not in cols:
        c.execute('alter table outcomes add column hit10 integer default 0')
    c.execute('create index if not exists ix_oh on outcomes(horizon,hit4,hit7,hit10)')
    if meta_get(c,'start_ts') is None: meta_set(c,'start_ts',int(time.time()))
    if meta_get(c,'last_daily') is None: meta_set(c,'last_daily','')
    if meta_get(c,'final_sent') is None: meta_set(c,'final_sent','0')
    c.commit(); c.close()


def f(x,k):
    try:return float(x.get(k) or 0)
    except:return 0.0

def pct(a,b):
    return None if not b else (a/b-1)*100

def ticker():
    r=requests.get(TICKER_URL,timeout=20); r.raise_for_status()
    return [x for x in r.json().get('data',[]) if (x.get('pair') or '').upper().endswith('TRY') and f(x,'last')>0]


def history(c,symbol,ts,mins=70):
    return c.execute('select ts,price,volume24 from snapshots where symbol=? and ts>=? and ts<? order by ts',(symbol,ts-mins*60-90,ts)).fetchall()

def nearest(rows,target,tol=90):
    best=None; bd=None
    for r in rows:
        d=target-r[0]
        if 0<=d<=tol and (bd is None or d<bd): best=r;bd=d
    return best

def ret(rows,p,ts,m):
    r=nearest(rows,ts-m*60); return pct(p,r[1]) if r else None

def vdelta(rows,v,ts,m):
    r=nearest(rows,ts-m*60)
    if not r:return None
    d=v-r[2]; return d if d>=0 else None

def ema(vals,n):
    if len(vals)<n:return None
    e=sum(vals[:n])/n;k=2/(n+1)
    for x in vals[n:]:e=x*k+e*(1-k)
    return e

def rsi(vals,n=14):
    if len(vals)<n+1:return None
    ds=[vals[i]-vals[i-1] for i in range(1,len(vals))];g=[max(x,0) for x in ds];l=[max(-x,0) for x in ds]
    ag=sum(g[:n])/n; al=sum(l[:n])/n
    for i in range(n,len(ds)):ag=(ag*(n-1)+g[i])/n; al=(al*(n-1)+l[i])/n
    if al==0:return 100.0
    rs=ag/al;return 100-100/(1+rs)

def features(c,sym,ts,x,btc=None):
    p,bid,ask,hi,lo,op,v=[f(x,k) for k in ('last','bid','ask','high','low','open','volume')]
    rows=history(c,sym,ts); vals=[r[1] for r in rows if r[1]>0]+[p]; vals=vals[-40:]
    rr={m:ret(rows,p,ts,m) for m in (1,3,5,10,30,60)}
    vv={m:vdelta(rows,v,ts,m) for m in (1,3,5,10)}
    vr15=(vv[1]/(vv[5]/5)) if vv[1] is not None and vv[5] and vv[5]>0 else None
    vr310=((vv[3]/3)/(vv[10]/10)) if vv[3] is not None and vv[10] and vv[10]>0 else None
    e12,e26=ema(vals,12),ema(vals,26)
    stair=None
    if len(vals)>=5: stair=sum(1 for i in range(-4,0) if vals[i]>=vals[i-1])/4*100
    rng=((p-lo)/(hi-lo)*100) if hi>lo else None
    spread=((ask-bid)/((ask+bid)/2)*100) if bid>0 and ask>0 else None
    b3=(rr[3]-btc['r3']) if btc and rr[3] is not None and btc.get('r3') is not None else None
    b10=(rr[10]-btc['r10']) if btc and rr[10] is not None and btc.get('r10') is not None else None
    b60=(rr[60]-btc['r60']) if btc and rr[60] is not None and btc.get('r60') is not None else None
    return [p,bid,ask,hi,lo,op,v,rr[1],rr[3],rr[5],rr[10],rr[30],rr[60],vv[1],vv[3],vv[5],vv[10],vr15,vr310,b3,b10,b60,rsi(vals),pct(p,e12) if e12 else None,pct(p,e26) if e26 else None,((e12-e26)/p*100) if e12 and e26 else None,stair,rng,spread]

COLS='price,bid,ask,high24,low24,open24,volume24,r1,r3,r5,r10,r30,r60,vol1,vol3,vol5,vol10,vr15,vr310,btc3,btc10,btc60,rsi14,ema12gap,ema26gap,macdgap,stair5,range24,spread'
def insert_snap(c,ts,sym,vals):
    q=','.join('?' for _ in range(31))
    c.execute(f'insert or ignore into snapshots(ts,symbol,{COLS}) values({q})',[ts,sym]+vals)


def label(c,h,batch=800):
    cutoff=int(time.time())-h*60-120
    rows=c.execute('''select s.id,s.symbol,s.ts,s.price from snapshots s left join outcomes o on o.snapshot_id=s.id and o.horizon=? where s.ts<=? and o.snapshot_id is null order by s.ts limit ?''',(h,cutoff,batch)).fetchall()
    n=0
    for sid,sym,ts,entry in rows:
        fut=[r[0] for r in c.execute('select price from snapshots where symbol=? and ts>? and ts<=? order by ts',(sym,ts,ts+h*60)).fetchall() if r[0] and r[0]>0]
        if not fut or not entry:continue
        re=pct(fut[-1],entry); up=pct(max(fut),entry); dn=pct(min(fut),entry)
        c.execute('insert or replace into outcomes values(?,?,?,?,?,?,?,?,?,?)',
                  (sid,h,sym,ts,re,up,dn,int(up>=4),int(up>=7),int(up>=10)));n+=1
    c.commit();return n

FEATURES=[('r1','1dk momentum'),('r3','3dk momentum'),('r5','5dk momentum'),('r10','10dk momentum'),('r30','30dk momentum'),('r60','60dk momentum'),('vr15','1dk hacim/5dk ort'),('vr310','3dk hacim/10dk ort'),('btc3','BTC farkÄ± 3dk'),('btc10','BTC farkÄ± 10dk'),('btc60','BTC farkÄ± 60dk'),('rsi14','RSI14'),('ema12gap','EMA12 farkÄ±'),('ema26gap','EMA26 farkÄ±'),('macdgap','EMA12-26 farkÄ±'),('stair5','basamak skoru'),('range24','24s aralÄ±k konumu'),('spread','spread')]

def summarize(c,hit='hit4',days=7,minrows=50):
    since=int(time.time())-days*86400
    tot,hits=c.execute(f'select count(*),sum({hit}) from outcomes where horizon=? and ts>=?',(MAIN_HORIZON,since)).fetchone();tot=tot or 0;hits=hits or 0;base=hits/tot if tot else 0
    out=[]
    for col,name in FEATURES:
        rows=c.execute(f'select s.{col},o.{hit} from outcomes o join snapshots s on s.id=o.snapshot_id where o.horizon=? and o.ts>=? and s.{col} is not null',(MAIN_HORIZON,since)).fetchall()
        vals=[float(v) for v,_ in rows if v is not None and math.isfinite(float(v))]
        if len(vals)<minrows:continue
        try:q=statistics.quantiles(vals,n=4,method='inclusive')
        except:continue
        bins=[('dÃ¼ÅÃ¼k',None,q[0]),('orta-alt',q[0],q[1]),('orta-Ã¼st',q[1],q[2]),('yÃ¼ksek',q[2],None)]
        for bn,lo,hi in bins:
            ss=[int(h) for v,h in rows if v is not None and (lo is None or float(v)>=lo) and (hi is None or float(v)<hi)]
            if len(ss)<10:continue
            rate=sum(ss)/len(ss);lift=rate/base if base else 0
            out.append((lift,rate,len(ss),name,bn,lo,hi))
    out.sort(reverse=True);return tot,hits,base,out[:10]

def rngtxt(lo,hi):
    if lo is None:return f'<{hi:.2f}'
    if hi is None:return f'>={lo:.2f}'
    return f'{lo:.2f}-{hi:.2f}'

def report(c,days,final=False):
    a=summarize(c,'hit4',days,80 if final else 20)
    b=summarize(c,'hit7',days,80 if final else 20)
    d=summarize(c,'hit10',days,80 if final else 20)
    lines=[
        'ð§  7 GÃNLÃK BTC TURK PÄ°YASA RAPORU' if final else 'ð GÃNLÃK PÄ°YASA ÃÄRENME RAPORU',
        '',
        f'3s iÃ§inde +%4: %{a[2]*100:.1f} ({a[1]}/{a[0]})',
        f'3s iÃ§inde +%7: %{b[2]*100:.1f} ({b[1]}/{b[0]})',
        f'3s iÃ§inde +%10+: %{d[2]*100:.1f} ({d[1]}/{d[0]})'
    ]
    if a[3]:
        lines+=['','ð° +%4 yapanlarda Ã¶ne Ã§Ä±kanlar:']+[f'â¢ {x[3]} {rngtxt(x[5],x[6])} â %{x[1]*100:.1f}, bazÄ±n {x[0]:.2f}x (n={x[2]})' for x in a[3][:5]]
    if final and b[3]:
        lines+=['','ð +%7 yapanlarda Ã¶ne Ã§Ä±kanlar:']+[
            f'â¢ {x[3]} {rngtxt(x[5],x[6])} â %{x[1]*100:.1f}, bazÄ±n {x[0]:.2f}x (n={x[2]})'
            for x in b[3][:5]
        ]
    if final and d[3]:
        lines+=['','ð¥ +%10 ve Ã¼zeri yapanlarda Ã¶ne Ã§Ä±kanlar:']+[
            f'â¢ {x[3]} {rngtxt(x[5],x[6])} â %{x[1]*100:.1f}, bazÄ±n {x[0]:.2f}x (n={x[2]})'
            for x in d[3][:5]
        ]
    lines+=['','Not: Ä°lk hafta AL/SAT yok; bot piyasayÄ± Ã¶Äreniyor.']
    return '\n'.join(lines)

def report_check(c):
    now=datetime.now(LOCAL_TZ); today=now.strftime('%Y-%m-%d')
    if now.hour>=REPORT_HOUR and meta_get(c,'last_daily')!=today:
        tg(report(c,1,False));meta_set(c,'last_daily',today);c.commit()
    start=int(meta_get(c,'start_ts') or time.time())
    if time.time()-start>=LEARNING_DAYS*86400 and meta_get(c,'final_sent')!='1':
        tg(report(c,LEARNING_DAYS,True));meta_set(c,'final_sent','1');c.commit()


def scan():
    ts=int(time.time());ts-=ts%60; xs=ticker(); c=db()
    btc_x=next((x for x in xs if (x.get('pair') or '').upper()=='BTCTRY'),None)
    btc_f=None
    if btc_x:
        vals=features(c,'BTCTRY',ts,btc_x,None);btc_f={'r3':vals[8],'r10':vals[10],'r60':vals[12]}
    n=0
    for x in xs:
        sym=(x.get('pair') or '').upper()
        try:insert_snap(c,ts,sym,features(c,sym,ts,x,None if sym=='BTCTRY' else btc_f));n+=1
        except Exception as e:print('[FEATURE HATA]',sym,e)
    c.commit();lab=sum(label(c,h) for h in HORIZONS);report_check(c)
    sc=c.execute('select count(*) from snapshots').fetchone()[0]; oc=c.execute('select count(*) from outcomes').fetchone()[0]
    print(f'[ÃÄRENÄ°YOR] TRY={len(xs)} kayÄ±t={n} snapshots={sc} outcomes={oc} yeni={lab}')
    c.close()

def main():
    setup();print('BTC TURK PIYASA OGRENEN BOT V2 (+4/+7/+10)',DB_PATH)
    tg('ð§  PÄ°YASA ÃÄRENEN BOT BAÅLADI\nBtcTurk TRY piyasasÄ±nÄ±n tamamÄ±nÄ± kriter koymadan izleyecek.\nÄ°lk hafta AL/SAT yok; her gÃ¼n kÄ±sa rapor, 7. gÃ¼n +%4/+%7/+%10+ ortak Ã¶zellik raporu.')
    while True:
        t=time.time()
        try:scan()
        except Exception as e:print('[GENEL HATA]',e)
        time.sleep(max(5,SCAN_SECONDS-(time.time()-t)))

if __name__=='__main__':main()
