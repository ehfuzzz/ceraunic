import pickle, json, calendar, datetime as dt
import pandas as pd, numpy as np
from common import RAW, OUT
G=str(RAW)+"/"
data=pickle.load(open(G+"daily.pkl","rb"))
def mon(d,y,m,k): return d.loc[f"{y}-{m:02d}",k].sum()
def clim_days(d,dates,k,yrs):
    # expected DD for each date: mean over prior `yrs` years of same calendar day +-3 days
    tot=0.0
    for x in dates:
        vals=[]
        for yb in range(1,yrs+1):
            c=x.replace(year=x.year-yb) if not (x.month==2 and x.day==29) else x.replace(year=x.year-yb,day=28)
            vals.extend(d.loc[c-pd.Timedelta(days=3):c+pd.Timedelta(days=3),k].tolist())
        tot+=np.mean(vals)
    return tot
res=[]
for code,d in data.items():
  for k,months in (("hdd",[11,12,1,2,3]),("cdd",[6,7,8])):
    for y in range(2016,2027):
      for m in months:
        last=dt.date(y,m,calendar.monthrange(y,m)[1])
        if pd.Timestamp(last)>d.index.max(): continue
        real=mon(d,y,m,k)
        c30=np.mean([mon(d,y-i,m,k) for i in range(1,31)]); c10=np.mean([mon(d,y-i,m,k) for i in range(1,11)])
        for L in (30,15,7,1):
          f=pd.Timestamp(last)-pd.Timedelta(days=L)  # forecast made on day f, data known through f-1
          first=pd.Timestamp(y,m,1)
          known_end=f-pd.Timedelta(days=1)
          known=d.loc[first:known_end,k].sum() if known_end>=first else 0.0
          rem=pd.date_range(max(first,f),pd.Timestamp(last))
          fc=known+clim_days(d,rem,k,10)
          res.append(dict(city=code,idx=k,y=y,m=m,season=(y if m>=7 else y-1),L=L,real=real,c30=c30,c10=c10,todate_c10=fc))
R=pd.DataFrame(res); R.to_csv(str(OUT)+"/bench.csv",index=False)
def summ(sub):
    o={}
    for f in ("c30","c10","todate_c10"):
        e=sub.real-sub[f]; o[f]=(round(e.mean(),1),round(e.std(),1),round(np.sqrt((e**2).mean()),1))
    o["n"]=len(sub); return o
print("err = realized - forecast; (mean, sd, rmse)")
for (c,k),g in R.groupby(["city","idx"]):
    for L in (30,15,7,1):
        s=g[g.L==L]; s4=s[s.season>=2022]
        print(c,k,"L",L,"| 2016-26",summ(s),"| last4 seasons",summ(s4))
# variance share of one day
print("\nper-day share of monthly variance (LGA/ORD/CVG), 1996-2025")
for code,d in data.items():
  for k,m in (("hdd",1),("cdd",7),("hdd",10)):
    ys=range(1996,2026); M=np.array([mon(d,y,m,k) for y in ys])
    nd=calendar.monthrange(2001,m)[1]
    D=np.array([[d.loc[f"{y}-{m:02d}-{i:02d}",k] for i in range(1,nd+1)] for y in ys])
    r2=[np.corrcoef(D[:,i],M)[0,1]**2 for i in range(nd) if D[:,i].std()>0]
    vshare=D.var(axis=0).sum()/M.var()
    a=(d.loc[f"1996-{m:02d}":"2025-12","avg"])
    print(code,k,"month",m,"sd(month)",round(M.std(),1),"mean",round(M.mean(),1),"mean R2 one day",round(np.mean(r2),3),"sum daily var / month var",round(vshare,2))
