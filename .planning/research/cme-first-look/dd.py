import json, math, sys, datetime as dt
import pandas as pd, numpy as np
from common import RAW, OUT
G=str(RAW)+"/"
ST={"LGA":("USW00014732","KLGA"),"ORD":("USW00094846","KORD"),"CVG":("USW00093814","KCVG")}
def c2f(x): return math.floor(x/10*9/5+32+0.5)
def load(code):
    g,cli=ST[code]
    d=pd.read_csv(G+g+".csv",usecols=["DATE","TMAX","TMIN"],dtype=str)
    d=d.dropna(subset=["TMAX","TMIN"]); d["date"]=pd.to_datetime(d.DATE)
    d["tx"]=d.TMAX.str.strip().astype(int).map(c2f); d["tn"]=d.TMIN.str.strip().astype(int).map(c2f)
    d=d.set_index("date")[["tx","tn"]]; d["src"]="ghcn"
    c=pd.DataFrame(json.load(open(G+f"cli-{cli}-2026.json"))["results"])
    c=c[(c.high!="M")&(c.low!="M")]; c["date"]=pd.to_datetime(c.valid); c=c.set_index("date")
    both=d.index.intersection(c.index)
    agree=((d.loc[both,"tx"]==c.loc[both,"high"].astype(int))&(d.loc[both,"tn"]==c.loc[both,"low"].astype(int))).mean()
    extra=c.index.difference(d.index)
    e=pd.DataFrame({"tx":c.loc[extra,"high"].astype(int),"tn":c.loc[extra,"low"].astype(int),"src":"cli"})
    d=pd.concat([d,e]).sort_index()
    d["avg"]=(d.tx+d.tn)/2; d["hdd"]=(65-d.avg).clip(lower=0); d["cdd"]=(d.avg-65).clip(lower=0)
    return d, agree, len(both), list(extra.strftime("%m-%d"))
out={}
data={}
for code in ST:
    d,agree,nb,extra=load(code); data[code]=d
    out[code]={"ghcn_vs_cli_2026_agree":round(agree,4),"n_overlap":nb,"cli_fill_days":extra,
               "sep2026_cdd":float(d.loc["2026-09","cdd"].sum()),"sep2026_hdd":float(d.loc["2026-09","hdd"].sum()),
               "oct2026_hdd_through_10-23":float(d.loc["2026-10-01":"2026-10-23","hdd"].sum()),
               "last_day":str(d.index.max().date())}
    # data gaps check in recent years
    idx=pd.date_range("2016-01-01","2026-10-23"); out[code]["missing_days_2016+"]=int(len(idx.difference(d.index)))
print(json.dumps(out,indent=0))
json.dump(out,open(str(OUT)+"/validate.json","w"))
import pickle; pickle.dump(data,open(G+"daily.pkl","wb"))
