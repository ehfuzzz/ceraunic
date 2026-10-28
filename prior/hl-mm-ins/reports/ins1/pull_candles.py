import json,urllib.request,time,datetime as dt,sys,os
B="https://api.elections.kalshi.com/trade-api/v2"
def get(u):
    for k in range(6):
        try: return json.load(urllib.request.urlopen(u,timeout=30))
        except Exception as e:
            err=e; time.sleep(2*(k+1))
    print("ERR",u[:100],err,flush=True); return {}
res={}
for ser in ["KXHIGHNY","KXHIGHTEWR","KXHIGHTTTN","KXHIGHCHI","KXHIGHMIA"]:
    settled=[];cur=None
    while True:
        d=get(f"{B}/markets?series_ticker={ser}&status=settled&limit=1000"+(f"&cursor={cur}" if cur else ""))
        settled+=d.get("markets",[]); cur=d.get("cursor")
        if not cur or len(settled)>3000: break
        time.sleep(0.4)
    print(ser,"settled",len(settled),flush=True)
    for m in settled:
        ct=int(dt.datetime.fromisoformat(m["close_time"].replace("Z","+00:00")).timestamp())
        c=get(f"{B}/series/{ser}/markets/{m['ticker']}/candlesticks?start_ts={ct-3*86400}&end_ts={ct+3600}&period_interval=60")
        m["candles"]=c.get("candlesticks",[])
        time.sleep(0.35)
    res[ser]=settled
    json.dump(res,open("candles.json","w"))
print("CANDLES-DONE",flush=True)
