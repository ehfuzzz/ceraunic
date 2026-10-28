import json,csv,statistics as st,datetime as dt,collections,math,re,sys
S="."
res=json.load(open(f"{S}/candles.json"))
# NWS ASOS daily max
asos={}
for f in ["iem-ny.csv","iem-nj.csv","iem-il.csv","iem-fl.csv"]:
    for r in csv.DictReader(open(f"{S}/{f}")):
        try: asos[(r["station"],r["day"])]=float(r["max_temp_f"])
        except: pass
station={"KXHIGHNY":"NYC","KXHIGHTEWR":"EWR","KXHIGHTTTN":"TTN","KXHIGHCHI":"MDW","KXHIGHMIA":"MIA"}
nearby={"KXHIGHNY":["LGA","JFK"],"KXHIGHTEWR":["TTN"],"KXHIGHTTTN":["EWR"],"KXHIGHCHI":["ORD"],"KXHIGHMIA":["FLL","OPF"]}
def bracket(m):
    fl=m.get("floor_strike"); cap=m.get("cap_strike"); t=m.get("strike_type")
    if t=="between": return (float(fl),float(cap))
    if t=="less": return (-99.0,float(cap))
    if t=="greater": return (float(fl),999.0)
    return None
def H(T,K): return max(0.0,min(T-K,6.0))
def px_at(m,hours_before,close_ts):
    """yes ask/bid close of the last hourly candle ending <= close-hours_before"""
    tgt=close_ts-hours_before*3600; best=None
    for c in m.get("candles",[]):
        if c["end_period_ts"]<=tgt: best=c
    if not best: return None
    ya=best.get("yes_ask",{}).get("close_dollars"); yb=best.get("yes_bid",{}).get("close_dollars")
    if ya is None or yb is None: return None
    ya,yb=float(ya),float(yb)
    if ya<=0 or (ya>=0.99 and yb<0.90): return None
    return ya,yb
rows=[]
for ser,ms in res.items():
    byev=collections.defaultdict(list)
    for m in ms: byev[m["event_ticker"]].append(m)
    for ev,lad in byev.items():
        lad=[m for m in lad if bracket(m)]
        lad.sort(key=lambda m:bracket(m)[0])
        if len(lad)<4: continue
        win=[m for m in lad if m.get("result")=="yes"]
        if len(win)!=1: continue
        wb=bracket(win[0])
        # settlement value proxy: bracket midpoint (Kalshi integer °F; 'between' 72..73 covers 72 and 73)
        K=bracket(lad[1])[0]
        close_ts=int(dt.datetime.fromisoformat(lad[0]["close_time"].replace("Z","+00:00")).timestamp())
        day=lad[0]["close_time"][:10]
        # the market day is the day before close_time (close at 03:59Z next day, ET) -> local date
        d_local=dt.datetime.strptime(ev.split("-")[1],"%y%b%d").strftime("%Y-%m-%d")
        Tn=asos.get((station[ser],d_local))
        row=dict(ser=ser,ev=ev,day=d_local,K=K,win=wb,T_nws=Tn)
        # binning payoff (ladder pays H(mid) for the winning bracket)
        def ladpay(b): 
            lo,hi=b
            if lo<-50: return H(hi,K)
            if hi>500: return H(lo+1,K)
            return H((lo+hi)/2,K)
        row["ladder_pay"]=ladpay(wb)
        # NWS-based 'true' payoff and settlement-source mismatch
        if Tn is not None:
            row["H_nws"]=H(Tn,K)
            lo,hi=wb; row["src_match"]= (lo-0.5<=Tn<=hi+0.5) if lo>-50 and hi<500 else (Tn<=hi+0.5 if lo<-50 else Tn>=lo-0.5)
            for nb in nearby[ser]:
                Tb=asos.get((nb,d_local))
                if Tb is not None: row[f"H_{nb}"]=H(Tb,K)
        for hb in (24,12,2):
            prem=0;spread=0;ok=True;n=0
            for m in lad:
                q=ladpay(bracket(m))
                if q<=0: continue
                p=px_at(m,hb,close_ts)
                if p is None: ok=False;break
                ya,yb=p; prem+=q*ya; spread+=q*(ya-(ya+yb)/2); n+=q
            if ok: row[f"prem{hb}"]=prem; row[f"spr{hb}"]=spread; row[f"ncon{hb}"]=n
        rows.append(row)
json.dump(rows,open(f"{S}/rows.json","w"),indent=0)
print("city-days:",len(rows), collections.Counter(r["ser"] for r in rows)); print("executable at 24h:",collections.Counter(r["ser"] for r in rows if "prem24" in r))
def he(x,y):
    if len(x)<5: return float("nan")
    vy=st.pvariance(y); return 1-st.pvariance([a-b for a,b in zip(x,y)])/vy if vy>0 else float("nan")
print("\nT1 replication (premium at asks vs realised ladder payoff; error = payoff - premium):")
print(f"{'series':12s} h  n   mean_prem  mean_pay  mean_err  rmse   HE_vs_H_nws  spread_cost")
for ser in res:
    for hb in (24,12,2):
        rs=[r for r in rows if r["ser"]==ser and f"prem{hb}" in r and "H_nws" in r]
        if not rs: continue
        prem=[r[f"prem{hb}"] for r in rs]; pay=[r["ladder_pay"] for r in rs]; err=[p-q for p,q in zip(pay,prem)]
        # hedge effectiveness: exposure = H_nws (what the buyer actually loses); hedge payoff = ladder_pay
        print(f"{ser:12s} {hb:2d} {len(rs):3d}  {st.mean(prem):8.3f}  {st.mean(pay):8.3f}  {st.mean(err):8.3f}  {math.sqrt(st.mean([e*e for e in err])):6.3f}   {he([r['H_nws'] for r in rs],pay):6.3f}     {st.mean([r[f'spr{hb}'] for r in rs]):6.3f}")
print("\nT2 decomposition:")
for ser in res:
    rs=[r for r in rows if r["ser"]==ser and "H_nws" in r]
    if not rs: continue
    binn=[r["H_nws"]-r["ladder_pay"] for r in rs]
    mm=sum(1 for r in rs if not r["src_match"])
    print(f"{ser:12s} n={len(rs):3d} binning: mean {st.mean(binn):+.3f} rmse {math.sqrt(st.mean([b*b for b in binn])):.3f} | settlement-source mismatch (TWC bracket vs NWS ASOS): {mm}/{len(rs)} = {mm/len(rs):.1%} | mean H_nws {st.mean([r['H_nws'] for r in rs]):.3f} (share of days with H>0: {sum(1 for r in rs if r['H_nws']>0)/len(rs):.0%})")
    for nb in nearby[ser]:
        rs2=[r for r in rs if f"H_{nb}" in r]
        if len(rs2)<5: continue
        g=[r[f"H_{nb}"]-r["ladder_pay"] for r in rs2]
        print(f"    geography {nb} exposure hedged with {station[ser]} ladder: n={len(rs2)} mean {st.mean(g):+.3f} rmse {math.sqrt(st.mean([x*x for x in g])):.3f} HE={he([r[f'H_{nb}'] for r in rs2],[r['ladder_pay'] for r in rs2]):.3f} (own-station HE={he([r['H_nws'] for r in rs2],[r['ladder_pay'] for r in rs2]):.3f})")

print("\nT2d geography with bias/ratio correction (in-sample OLS of nearby-station payoff on ladder payoff):")
def ols(x,y):
    mx,my=st.mean(x),st.mean(y); vx=st.pvariance(x)
    b=sum((a-mx)*(c-my) for a,c in zip(x,y))/len(x)/vx if vx>0 else 0; a=my-b*mx
    res=[c-(a+b*d) for c,d in zip(y,x)]; return a,b,1-st.pvariance(res)/st.pvariance(y)
for ser in res:
    rs=[r for r in rows if r["ser"]==ser and "H_nws" in r]
    for nb in nearby[ser]:
        rs2=[r for r in rs if f"H_{nb}" in r]
        if len(rs2)<5: continue
        a,b,r2=ols([r["ladder_pay"] for r in rs2],[r[f"H_{nb}"] for r in rs2])
        print(f"  {ser:12s} {nb}: offset {a:+.2f} ratio {b:.2f} -> HE {r2:.3f}   (mean T diff {nb}-{station[ser]}: {st.mean([asos[(nb,r['day'])]-asos[(station[ser],r['day'])] for r in rs2 if (nb,r['day']) in asos]):+.2f} F)")
print("\nV1 sell-side (post at ask 24h before close, hold to settlement; per $1/F unit ladder):")
for ser in res:
    rs=[r for r in rows if r["ser"]==ser and "prem24" in r]
    if not rs: continue
    pnl=[r["prem24"]-r["ladder_pay"] for r in rs]; pnl.sort()
    print(f"  {ser:12s} n={len(rs)} mean {st.mean(pnl):+.3f}/day  worst day {pnl[0]:+.3f}  p10 {pnl[len(pnl)//10]:+.3f}  win rate {sum(1 for p in pnl if p>0)/len(pnl):.0%}  contracts/day {st.mean([r['ncon24'] for r in rs]):.1f}")
print("\nV3 rolling 30-day cover per $1/F unit: sum of daily spread cost and daily overround (premium - fair mid):")
for ser in res:
    rs=[r for r in rows if r["ser"]==ser and "prem24" in r]
    if not rs: continue
    spr=st.mean([r["spr24"] for r in rs]); over=st.mean([r["prem24"]-r["ladder_pay"] for r in rs])
    print(f"  {ser:12s} 30-day spread cost ${30*spr:.2f}, 30-day total overpay ${30*over:.2f}, vs 30-day expected payout ${30*st.mean([r['ladder_pay'] for r in rs]):.2f}")
