"""CME weather redo. Local existing data only; see REDO-PREREG.txt.
Run: uv run --no-project --with databento --with pandas --with scipy python <this script>
No credentials, networking, git operations, or import of the old scoring script.
"""
import calendar
import datetime as dt
import hashlib
import json
import re
import warnings
from collections import Counter
from functools import lru_cache
from pathlib import Path

import databento as db
import numpy as np
import pandas as pd
from scipy.special import ndtr
from scipy.stats import t as student
from common import CITIES, RAW, OUT

warnings.filterwarnings('ignore', category=FutureWarning)
SEAL = pd.Timestamp('2026-10-23T17:00Z')
ROOT = {root: (city, kind, icao) for city, h, k, _, icao, _ in CITIES for root, kind in [(h,'hdd'),(k,'cdd')]}
PAT = re.compile(r'^('+'|'.join(sorted(ROOT,key=len,reverse=True))+r')([FGHJKMNQUVXZ])(\d)$')
MONTH = dict(zip('FGHJKMNQUVXZ',range(1,13)))
PRIMARY = ['KORD','KLGA','KCVG']
AUDIT = {}

def decode(x):
    m=x.symbol.str.extract(PAT)
    x=x[m[0].notna()].copy(); m=m.loc[x.index]
    x['root']=m[0]; x['mon']=m[1].map(MONTH); x['yd']=m[2].astype(int)
    x['cyear']=2020+x.yd
    x.loc[x.cyear < x.tdate.dt.year-2,'cyear']+=10
    x['contract']=x.root+x.mon.astype(str).str.zfill(2)+'-'+x.cyear.astype(str)
    x['month_start']=pd.to_datetime(dict(year=x.cyear,month=x.mon,day=1))
    x['month_end']=x.month_start+pd.offsets.MonthEnd(0)
    return x[(x.month_start>=pd.Timestamp('2022-10-01')) & (x.month_end<=pd.Timestamp('2026-09-30'))]


def load_stats():
    pieces=[]; raw=0
    p=RAW/'glbx-weather-stats-2022-10-01-2026-10-24.dbn.zst'
    for x in db.DBNStore.from_file(p).to_df(count=100000):
        # Filter receipt before inspecting values, symbols, or reference dates.
        x=x[x.index<SEAL].copy(); raw+=len(x)
        x=x[x.stat_type.isin([3,6,9])].copy()
        x['recv']=x.index; x=x.reset_index(drop=True)
        x['tdate']=pd.to_datetime(x.ts_ref,utc=True,errors='coerce').dt.tz_localize(None).dt.normalize()
        x=x[x.tdate.between('2001-01-01','2099-01-01')].copy()
        x=decode(x)
        pieces.append(x)
    x=pd.concat(pieces,ignore_index=True)
    # UTC cutoff corresponding to end of assessment day, handles daylight saving.
    x['cutoff']=(x.tdate+pd.Timedelta(days=1)).dt.tz_localize('America/Chicago').dt.tz_convert('UTC')
    x['on_time']=x.recv<x.cutoff
    s=x[x.stat_type==3].copy()
    s['actual']=(s.stat_flags&2)>0; s['final_flag']=(s.stat_flags&1)>0
    s['weekday']=s.recv.dt.tz_convert('America/Chicago').dt.dayofweek<5
    s['valid']=s.actual & s.weekday & s.on_time
    valid_keys=set(zip(s.loc[s.valid,'contract'],s.loc[s.valid,'tdate']))
    any_keys=set(zip(s.contract,s.tdate))
    s['has_valid']=[(a,b) in valid_keys for a,b in zip(s.contract,s.tdate)]
    lag=(s.recv-s.ts_ref).dt.total_seconds()/3600
    AUDIT['statistics']={'raw_preseal_records':raw,'expired_universe_records':len(x),
        'raw_settlement_records':len(s),'eligible_settlement_records':int(s.valid.sum()),
        'raw_contract_days':len(any_keys),'selected_contract_days':len(valid_keys),
        'no_qualifying_actual_weekday_on_time_days':len(any_keys-valid_keys),
        'snapshot_only_days':int((~s.has_valid).groupby([s.contract,s.tdate]).first().sum()),
        'receipt_lag_hours_p50_p99':[float(lag.quantile(.5)),float(lag.quantile(.99))],
        'selection':'all eligible retained until final-flag then latest receipt selection; daily downsampling preregistered'}
    only_snapshot=s.groupby(['contract','tdate']).apply(lambda g: bool((~g.actual | ~g.weekday).all()),include_groups=False)
    AUDIT['statistics']['snapshot_only_days']=int(only_snapshot.sum())
    S=s[s.valid].sort_values(['contract','tdate','final_flag','recv']).groupby(['contract','tdate']).tail(1).copy()
    for typ,col in [(6,'cleared_vol'),(9,'oi')]:
        # Ex-post class label, never a price or forecast input. Reporting lags are common.
        v=x[x.stat_type==typ].sort_values('recv').groupby(['contract','tdate']).quantity.last().rename(col)
        S=S.set_index(['contract','tdate']).join(v).reset_index()
    missing_volume=int(S.cleared_vol.isna().sum())
    S['cleared_vol']=S.cleared_vol.fillna(0)
    S=S.sort_values(['contract','tdate'])
    S['prev']=S.groupby('contract').price.shift()
    S['prev_date']=S.groupby('contract').tdate.shift()
    S['prev_gap']=(S.tdate-S.prev_date).dt.days
    S['changed']=(S.price!=S.prev)&S.prev.notna()&S.prev_gap.le(5)
    S['inwin']=S.tdate.between(S.month_start-pd.Timedelta(days=15),S.month_end)
    S['cls']=np.where((S.cleared_vol>0)&S.inwin&S.changed,'A',
                      np.where((S.cleared_vol==0)&S.inwin,'B',np.where(~S.inwin,'C','excluded_activity_stale')))
    S['lead']=(S.month_end-S.tdate).dt.days
    S=S[S.lead>=0].copy()
    S[['city','kind','icao']]=pd.DataFrame(S.root.map(ROOT).tolist(),index=S.index)
    S['season']=np.where(S.kind=='hdd',S.month_start.dt.year-(S.mon<10).astype(int),S.cyear)
    S['ym']=S.month_start.dt.strftime('%Y-%m')
    AUDIT['statistics']['selected_day_gap_p99']=float(S.prev_gap.quantile(.99))
    AUDIT['class_counts']=S.groupby('cls').agg(rows=('price','size'),contracts=('contract','nunique'),lots=('cleared_vol','sum')).reset_index().to_dict('records')
    AUDIT['statistics']['missing_cleared_volume_days']=missing_volume
    event_lag=(s.recv-s.ts_event).dt.total_seconds()
    AUDIT['statistics']['exchange_to_receive_seconds_p50_p99']=[float(event_lag.quantile(.5)),float(event_lag.quantile(.99))]
    AUDIT['statistics']['eligible_record_retention_before_daily_selection']=1.0
    # This is written before any scored forecast comparison.
    (OUT/'redo-feed-audit.json').write_text(json.dumps(AUDIT,indent=2,default=str)+'\n')
    print('RAW-FEED AUDIT WRITTEN; baseline calculation begins',flush=True)
    return S


def load_weather():
    result={}
    for *_,icao,ghcn in CITIES:
        raw=json.loads((RAW/f'acis-{icao}.json').read_text())
        d=pd.DataFrame(raw['data'],columns=['date','tx','tn'])
        d['date']=pd.to_datetime(d.date)
        d['avg']=(pd.to_numeric(d.tx,errors='coerce')+pd.to_numeric(d.tn,errors='coerce'))/2
        result[icao]=d.set_index('date').avg.dropna()
    return result

DAILY=load_weather()
DAY_VALUES={icao: {d.date().toordinal():float(v) for d,v in a.items()} for icao,a in DAILY.items()}

def degree(a,kind):
    return np.maximum(0,65-a) if kind=='hdd' else np.maximum(0,a-65)

def complete_sum(icao,kind,start,end):
    if start>end: return 0.
    idx=pd.date_range(start,end)
    a=DAILY[icao].reindex(idx)
    return float(degree(a,kind).sum()) if a.notna().all() else np.nan

@lru_cache(None)
def slope(icao,cutyear):
    a=DAILY[icao]; a=a[(a.index.year>=cutyear-30)&(a.index.year<cutyear)]
    g=a.groupby(a.index.year)
    ann=g.mean(); counts=g.count()
    full=[y for y in ann.index if counts[y]==(366 if calendar.isleap(y) else 365)]
    assert len(full)>=10, (icao,cutyear,len(full))
    assert a.index.max()<pd.Timestamp(cutyear,1,1)
    return float(np.polyfit(full,ann.loc[full],1)[0])

@lru_cache(None)
def expected(icao,kind,target,cutoff,trend):
    vals=[]
    # Select sample years from assessment-date cutoff, never contract year.
    n=30 if trend else 10
    b=slope(icao,cutoff.year) if trend else 0.
    for y in range(cutoff.year-1,cutoff.year-n-1,-1):
        try: c=dt.date(y,target.month,target.day)
        except ValueError: c=dt.date(y,target.month,28)
        ordinal=c.toordinal(); end=cutoff.date().toordinal()
        idx=[z for z in range(ordinal-3,ordinal+4) if z<end]
        assert not idx or max(idx)<end
        w=np.array([DAY_VALUES[icao][z] for z in idx if z in DAY_VALUES[icao]])
        if len(w): vals.extend(degree(w+b*(target.year-y),kind))
    return float(np.mean(vals)) if vals else np.nan


def load_mos():
    lookup={}; coverage=[]
    for *_,icao,ghcn in CITIES:
        parts=[pd.read_csv(p,usecols=['runtime','ftime','n_x']) for p in sorted((RAW/'mos').glob(f'MEX-{icao}-*.csv'))]
        assert len(parts)==4, icao
        m=pd.concat(parts,ignore_index=True)
        m['runtime']=pd.to_datetime(m.runtime,utc=True); m['ftime']=pd.to_datetime(m.ftime,utc=True)
        m['n_x']=pd.to_numeric(m.n_x,errors='coerce')
        m=m[(m.runtime<SEAL)&m.n_x.between(-150,150)].copy()
        duplicates=m.duplicated(['runtime','ftime'])
        conflicts=m.groupby(['runtime','ftime']).n_x.nunique().gt(1).sum()
        assert not conflicts, (icao,'conflicting MOS archive rows')
        m=m.drop_duplicates(['runtime','ftime'])
        assert m.runtime.dt.hour.isin([0,12]).all()
        assert m.ftime.dt.hour.isin([0,12]).all()
        coverage.append({'icao':icao,'rows':len(m),'runs':m.runtime.nunique(),
                         'duplicate_boundary_rows':int(duplicates.sum()),'first_run':str(m.runtime.min()),'last_run':str(m.runtime.max())})
        lookup[icao]={(r.value,f.value):float(v) for r,f,v in m.itertuples(index=False,name=None)}
    AUDIT['mos_archive']=coverage
    return lookup

MOS=load_mos()

def mos_extreme(icao,target,T,which):
    # Each value is explicitly indexed by initialization AND valid time.
    run=T.tz_localize('UTC')
    if which=='max': valid=(target+pd.Timedelta(days=1)).tz_localize('UTC')
    else:
        valid=target.tz_localize('UTC')+pd.Timedelta(hours=12)
        if target==T: run-=pd.Timedelta(hours=12)
    for age in [0,12]:
        rr=run-pd.Timedelta(hours=age)
        assert rr < (T+pd.Timedelta(days=1)).tz_localize('UTC')
        v=MOS[icao].get((rr.value,valid.value))
        if v is not None: return v,age,rr
    return None,None,None

def normal_dd(mu,sig,kind):
    z=(65-mu) if kind=='hdd' else (mu-65)
    if sig==0:return max(0.,z)
    return float(z*ndtr(z/sig)+sig*np.exp(-.5*(z/sig)**2)/np.sqrt(2*np.pi))

@lru_cache(None)
def benchmarks(icao,kind,T,ms,me):
    known=complete_sum(icao,kind,ms,T-pd.Timedelta(days=1))
    if not np.isfinite(known): return None
    rest=pd.date_range(max(ms,T),me)
    trend=known; climo=known; mos=known; plug=known; mt=known; perfect=known
    stats=Counter(); runmax=None; forecast_days=[]
    for d in rest:
        a=expected(icao,kind,d,T,False); b=expected(icao,kind,d,T,True)
        climo+=a; trend+=b
        if 0<=(d-T).days<=6:
            tx,ax,rx=mos_extreme(icao,d,T,'max'); tn,an,rn=mos_extreme(icao,d,T,'min')
            stats['requested_days']+=1
            if tx is not None and tn is not None:
                assert rx <= T.tz_localize('UTC') and rn<=T.tz_localize('UTC')
                mu=(tx+tn)/2; sig=2.5+.5*(d-T).days
                v=normal_dd(mu,sig,kind); p=normal_dd(mu,0,kind)
                stats['mos_days']+=1; stats['older_run_extrema']+=int(ax==12)+int(an==12)
                runmax=max(x for x in [runmax,rx,rn] if x is not None)
                forecast_days.append((str(d.date()),tx,tn,str(rx),str(rn)))
            else:
                v=a;p=a;stats['climo_fallback_days']+=1
        else:v=a;p=a
        mos+=v;plug+=p;mt+=(v if (d-T).days<=6 else b)
        # Explicit hindsight diagnostic only, never primary verdict input.
        if d==T: perfect+=complete_sum(icao,kind,d,d)
        else: perfect+=v
    return dict(base_10y=climo,base_trend=trend,base_mos=mos,base_mos_plugin=plug,
                base_mos_trend=mt,base_mos_T_hindsight=perfect,known=known,
                obs_last_date=str(min(T-pd.Timedelta(days=1),me).date()) if T>ms else None,
                mos_latest_runtime=str(runmax) if runmax is not None else None,
                mos_days_json=json.dumps(forecast_days),**dict(stats))


def robust(x,groups):
    d=pd.DataFrame({'x':np.asarray(x,dtype=float),'g':np.asarray(groups)}).dropna()
    n=len(d); G=d.g.nunique()
    if not n:return dict(mean=None,se=None,n=0,seasons=0,ci95=None,mde80=None,mde_normal=None)
    mu=float(d.x.mean())
    if G<2:return dict(mean=mu,se=None,n=n,seasons=int(G),ci95=None,mde80=None,mde_normal=None)
    # OLS intercept score for a row-weighted mean; finite-G CR1 correction.
    scores=(d.x-mu).groupby(d.g).sum()
    se=float(np.sqrt(G/(G-1)*np.sum(scores**2)/n**2))
    critical=student.ppf(.975,G-1)
    return dict(mean=mu,se=se,n=n,seasons=int(G),ci95=[float(mu-critical*se),float(mu+critical*se)],
                mde80=float((critical+student.ppf(.8,G-1))*se),mde_normal=2.8*se)


def summarize(g):
    if len(g)==0:return None
    result=dict(rows=len(g),contracts=int(g.contract.nunique()),seasons=sorted(int(x) for x in g.season.unique()),
                actual_leads={str(int(k)):int(v) for k,v in g.lead.value_counts().sort_index().items()},
                price=robust(g.price-g.outcome,g.season),trend_gap=robust(g.price-g.base_trend,g.season),
                mos_gap=robust(g.price-g.base_mos,g.season),
                price_month_se=robust(g.price-g.outcome,g.ym)['se'])
    for col in ['price','base_10y','base_trend','base_mos','base_mos_plugin','base_mos_trend','base_mos_T_hindsight']:
        e=g[col]-g.outcome
        result[col+'_bias']=robust(e,g.season)
        result[col+'_rmse']=float(np.sqrt(np.mean(e**2)))
    result['paired_sqerror_gap']=robust((g.price-g.outcome)**2-(g.base_mos-g.outcome)**2,g.season)
    result['mos_coverage']={k:int(g.get(k,pd.Series(dtype=float)).fillna(0).sum()) for k in ['requested_days','mos_days','older_run_extrema','climo_fallback_days']}
    result['by_city']=[dict(icao=i,rows=len(v),price=robust(v.price-v.outcome,v.season),mos_gap=robust(v.price-v.base_mos,v.season)) for i,v in g.groupby('icao')]
    p=result['price']; d=result['mos_gap']
    sign=np.sign(p['mean']); cities=sum(np.sign(v['price']['mean'])==sign for v in result['by_city'] if v['icao'] in PRIMARY)
    if p['ci95'] and p['ci95'][0]*p['ci95'][1]>0 and cities>=2 and d['se'] is not None and abs(d['mean'])>=2*d['se']:
        verdict='hedging-pressure rule met diagnostically'
    elif p['se'] is not None and abs(p['mean'])<=p['se'] and result['price_rmse']<=result['base_mos_rmse']:
        verdict='prices-outcome rule met descriptively'
    else: verdict='inconclusive under registered rule'
    result['registered_rule']=verdict
    result['inference']='direction only; fewer than 20 season clusters; settlement proxy is not block execution price'
    return result


def corruption_checks():
    # Future-year perturbation must not change a prior assessment, including a next-year contract.
    T=pd.Timestamp('2023-12-05'); target=pd.Timestamp('2024-01-15'); orig=DAILY['KORD'].copy()
    before=expected('KORD','hdd',target,T,True)
    DAILY['KORD'].loc[DAILY['KORD'].index>=T]+=500
    original_lookup=DAY_VALUES['KORD'].copy()
    for d in list(DAY_VALUES['KORD']):
        if d>=T.date().toordinal(): DAY_VALUES['KORD'][d]+=500
    expected.cache_clear(); slope.cache_clear()
    after=expected('KORD','hdd',target,T,True)
    DAILY['KORD']=orig; expected.cache_clear();slope.cache_clear()
    DAY_VALUES['KORD']=original_lookup
    assert before==after, 'future observations leaked'
    # Missing an accrued observation must fail closed instead of treating it as zero.
    assert np.isnan(complete_sum('KSAC','hdd',pd.Timestamp('2026-02-01'),pd.Timestamp('2026-02-20')))
    # Unequal cluster sizes: independently evaluate the intercept sandwich formula.
    x=np.array([0.,0.,0.,10.]); labels=np.array([0,0,0,1]); mu=x.mean()
    expect=np.sqrt(2*sum(sum(x[labels==g]-mu)**2 for g in [0,1])/len(x)**2)
    assert np.isclose(robust(x,labels)['se'],expect)
    # Real archived card: Sep 1 2022 00Z KORD, max Sep1=87; min Sep2=67 (not Sep1).
    tx,_,_=mos_extreme('KORD',pd.Timestamp('2022-09-01'),pd.Timestamp('2022-09-01'),'max')
    tn,_,_=mos_extreme('KORD',pd.Timestamp('2022-09-02'),pd.Timestamp('2022-09-01'),'min')
    assert (tx,tn)==(87.,67.)
    AUDIT['corruption_checks']=['future-weather perturbation invariant','missing accrual fails closed','unequal-cluster sandwich parity','MOS archived-card date alignment']


def main():
    corruption_checks()
    S=load_stats()
    U=S.drop_duplicates('contract').copy()
    U['outcome']=[complete_sum(i,k,a,b) for i,k,a,b in zip(U.icao,U.kind,U.month_start,U.month_end)]
    missing=U[U.outcome.isna()][['contract','icao','month_start','month_end']]
    AUDIT['incomplete_outcomes']=missing.astype(str).to_dict('records')
    S=S.join(U.set_index('contract').outcome,on='contract')
    # Publish all nineteen reviewed final discrepancies independently of validity exclusions.
    old=pd.read_csv(OUT/'premium_rows.csv').drop_duplicates('contract')
    old['difference']=old.final-old.acis_final
    bad=old[old.difference.abs()>1].copy()
    reviewed={'H002-2024','H111-2023','H302-2024','H412-2024','H502-2024','H702-2024','H711-2023','HQ02-2024','HR02-2024','HS02-2024','HS11-2023','HW02-2024','HW11-2023','K008-2024','K009-2024','K208-2023','K508-2023','KP08-2023','KQ08-2023'}
    bad['review_flagged_19']=bad.contract.isin(reviewed)
    assert int(bad.review_flagged_19.sum())==19
    bad[['contract','final','acis_final','difference','review_flagged_19']].to_csv(OUT/'redo-final-corrections.csv',index=False)
    AUDIT['old_finals_over_1dd']=len(bad)
    AUDIT['old_finals_over_2dd']=int((old.difference.abs()>2).sum())
    U[U.outcome.notna()].groupby(['kind','season']).agg(contracts=('contract','nunique'),cities=('icao','nunique'),months=('ym','nunique')).reset_index().to_csv(OUT/'redo-season-coverage.csv',index=False)
    rows=[]
    for cid,g in S[S.outcome.notna()].groupby('contract'):
        for L in [30,15,7,1]:
            target=g.month_end.iloc[0]-pd.Timedelta(days=L)
            h=g[g.tdate.between(target-pd.Timedelta(days=2),target)]
            if len(h):
                r=h.iloc[-1].to_dict();r.update(row_kind='lead',lead_bucket=L);rows.append(r)
        for _,v in g[g.cls=='A'].iterrows():
            r=v.to_dict();r.update(row_kind='activity_day',lead_bucket=None);rows.append(r)
    R=pd.DataFrame(rows)
    bb=[benchmarks(i,k,T,a,b) for i,k,T,a,b in zip(R.icao,R.kind,R.tdate,R.month_start,R.month_end)]
    ok=[v is not None for v in bb]
    AUDIT['incomplete_accrual_rows']=int(sum(not x for x in ok))
    R=pd.concat([R.loc[ok].reset_index(drop=True),pd.DataFrame([b for b in bb if b is not None])],axis=1)
    assert np.isfinite(R[['outcome','base_10y','base_trend','base_mos']].values).all()
    assert (R.recv<R.cutoff).all()
    assert R.actual.all()
    assert (R.recv.dt.tz_convert('America/Chicago').dt.dayofweek<5).all()
    R.to_csv(OUT/'redo-rows.csv',index=False)
    summary={'panels':{},'activity':{}}
    for sample in ['primary','pool13']:
        q=R[R.icao.isin(PRIMARY)].copy() if sample=='primary' else R.copy()
        if sample=='primary':q=q[((q.kind=='hdd')&q.season.between(2022,2025))|((q.kind=='cdd')&q.season.between(2023,2026))]
        for kind in ['hdd','cdd']:
            z=q[q.kind==kind]
            summary['activity'][sample+'_'+kind]=summarize(z[z.row_kind=='activity_day'])
            for L in [7,1,15,30]:
                for cls in ['AB','B','A']:
                    w=z[(z.row_kind=='lead')&(z.lead_bucket==L)&z.cls.isin(list(cls))]
                    summary['panels'][f'{sample}_{kind}_L{L}_{cls}']=summarize(w)
    # A clean Globex execution-price sensitivity, whole-day VWAP, no block inference.
    tr=db.DBNStore.from_file(RAW/'glbx-weather-trades-2022-10-01-2026-10-24.dbn.zst').to_df()
    tr=tr[tr.index<SEAL].copy();tr['recv']=tr.index
    tr['tdate']=(tr.index.tz_convert('America/Chicago')+pd.Timedelta(hours=7)).normalize().tz_localize(None)
    tr=decode(tr.reset_index(drop=True));tr['pv']=tr.price*tr['size']
    gx=tr.groupby(['contract','tdate']).agg(pv=('pv','sum'),quantity=('size','sum'),prints=('price','size'))
    gx['vwap']=gx.pv/gx.quantity
    G=S.drop(columns=['quantity']).set_index(['contract','tdate']).join(gx).reset_index()
    G=G[G.vwap.notna()&G.outcome.notna()].copy();G['settle_price']=G.price;G['price']=G.vwap
    b=[benchmarks(i,k,T,a,e) for i,k,T,a,e in zip(G.icao,G.kind,G.tdate,G.month_start,G.month_end)]
    valid=[v is not None for v in b]
    G=pd.concat([G.loc[valid].reset_index(drop=True),pd.DataFrame([v for v in b if v is not None])],axis=1)
    G.to_csv(OUT/'redo-globex.csv',index=False)
    summary['globex']={k:summarize(g) for k,g in G.groupby('kind')}
    AUDIT['globex']={'prints':len(tr),'total_quantity':int(tr['size'].sum()),'matched_days':len(G),
                     'matched_quantity':int(G.quantity.sum()),'settle_vwap_mae':float((G.settle_price-G.price).abs().mean()),
                     'settle_vwap_max':float((G.settle_price-G.price).abs().max())}
    AUDIT['scored_class_counts']=R[R.row_kind=='activity_day'].groupby('kind').agg(rows=('price','size'),contracts=('contract','nunique'),seasons=('season','nunique')).reset_index().to_dict('records')
    AUDIT['sample_exclusions']='ACIS month incomplete; no valid weekday actual same-day receipt; activity unchanged or previous valid settle gap >5 days; fixed lead lag >2 days'
    summary['audit']=AUDIT
    # Hash evidence and code without touching any credentials or other lanes.
    paths=[Path(__file__),OUT/'REDO-PREREG.txt',OUT/'fetch_mos.py']+sorted(RAW.glob('*.dbn.zst'))+sorted(RAW.glob('acis-*.json'))+sorted((RAW/'mos').glob('*.csv'))
    summary['input_sha256']={str(p.relative_to(OUT.parents[2])):hashlib.sha256(p.read_bytes()).hexdigest() for p in paths}
    (OUT/'redo-summary.json').write_text(json.dumps(summary,indent=2,default=str,allow_nan=False)+'\n')
    print(json.dumps({'checks':AUDIT['corruption_checks'],'activity':AUDIT['scored_class_counts'],'finals_over1':len(bad),'finals_over2':AUDIT['old_finals_over_2dd'],'rows':len(R)},indent=2))

if __name__=='__main__':main()
