import pandas as pd, pickle, numpy as np
from common import RAW, OUT
G=str(RAW)+"/"
d=pickle.load(open(G+"daily.pkl","rb"))["CVG"]
for y in (2023,2024,2025):
    a=pd.read_csv(G+f"asos-cvg-q4-{y}.csv"); a=a[a.tmpf!="M"]; a["tmpf"]=a.tmpf.astype(float)
    a["t"]=pd.to_datetime(a.valid); a=a.set_index("t")
    # top-of-hour style: one obs per clock hour (routine METAR ~:52); mean by local calendar day
    h=a.tmpf.resample("1h").mean(); dm=h.resample("1D").mean()
    hdd_h=(65-dm).clip(lower=0)
    q=d.loc[f"{y}-10-01":f"{y}-12-31"]
    hdd_mid=q.hdd
    j=pd.concat([hdd_h.rename("hourly"),hdd_mid.rename("midrange")],axis=1).dropna()
    print(y,"Q4 days",len(j),"sum HDD hourly-mean",round(j.hourly.sum(),1),"sum HDD (max+min)/2",round(j.midrange.sum(),1),"diff",round(j.hourly.sum()-j.midrange.sum(),1),"daily diff sd",round((j.hourly-j.midrange).std(),2))
