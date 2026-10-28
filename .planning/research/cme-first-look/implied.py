import pickle, pandas as pd, numpy as np
from common import RAW, OUT
G=str(RAW)+"/"
data=pickle.load(open(G+"daily.pkl","rb"))
S={"LGA":{"10-01":180,"10-19":190,"10-20":184,"10-21":166,"10-22":168,"10-23":160},
   "ORD":{"10-01":315,"10-19":181,"10-20":181,"10-21":173,"10-22":172,"10-23":173},
   "CVG":{"10-19":173,"10-20":157,"10-21":154,"10-22":151,"10-23":145}}
def climo(d,dates,yrs=10):
    t=0
    for x in dates:
        v=[]
        for yb in range(1,yrs+1):
            c=x.replace(year=x.year-yb); v+=d.loc[c-pd.Timedelta(days=3):c+pd.Timedelta(days=3),"hdd"].tolist()
        t+=np.mean(v)
    return t
print("city trade_date settle known_HDD(thru D-1) implied_rest days_rest implied_avgT_rest | todate+climo10 forecast | climo10 rest | climo10 full-month")
for c,ss in S.items():
    d=data[c]
    full=np.mean([d.loc[f"{y}-10","hdd"].sum() for y in range(2016,2026)])
    for td,st in ss.items():
        D=pd.Timestamp("2026-"+td)
        known=d.loc["2026-10-01":D-pd.Timedelta(days=1),"hdd"].sum()
        rest=pd.date_range(D,"2026-10-31"); cr=climo(d,rest)
        imp=st-known; n=len(rest)
        print(c,td,st,round(known,1),round(imp,1),n,round(65-imp/n,1),"|",round(known+cr,1),"|",round(cr,1),"|",round(full,1))
    print(c,"realized HDD 10-19..10-23:",d.loc["2026-10-19":"2026-10-23","hdd"].tolist())
