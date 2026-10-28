import json
from common import databento_key
key=databento_key()
import databento as db
c=db.Historical(key)
W=["H1","H2","H3","H4","H5","H6","H7","HR","HS","HQ","K1","K2","K3","K4","K5","K6","K7","KR","KS","KQ"]
allw=[x+".FUT" for x in W]; nychi=["H2.FUT","H4.FUT","K2.FUT","K4.FUT"]
res={}
def q(name,syms,schema,start,end):
    kw=dict(dataset="GLBX.MDP3",symbols=syms,stype_in="parent",schema=schema,start=start,end=end)
    try:
        cost=c.metadata.get_cost(**kw); n=c.metadata.get_record_count(**kw); sz=c.metadata.get_billable_size(**kw)
        res[name]=dict(cost_usd=round(cost,4),records=n,bytes=sz)
    except Exception as e: res[name]=str(e)[:160]
q("stats_nychi_2022-10_2026-10",nychi,"statistics","2022-10-01","2026-10-24")
q("stats_all20_2022-10_2026-10",allw,"statistics","2022-10-01","2026-10-24")
q("stats_all20_2010-06_2026-10",allw,"statistics","2010-06-06","2026-10-24")
q("defn_all20_2022-10_2026-10",allw,"definition","2022-10-01","2026-10-24")
q("ohlcv1d_all20_2022-10_2026-10",allw,"ohlcv-1d","2022-10-01","2026-10-24")
q("trades_all20_2022-10_2026-10",allw,"trades","2022-10-01","2026-10-24")
q("trades_all20_2025-10_2026-10",allw,"trades","2025-10-01","2026-10-24")
q("mbp1_all20_2025-10_2026-10",allw,"mbp-1","2025-10-01","2026-10-24")
q("mbo_all20_2025-10_2026-10",allw,"mbo","2025-10-01","2026-10-24")
q("trades_all20_2010-06_2026-10",allw,"trades","2010-06-06","2026-10-24")
for k,v in res.items(): print(k, v)
from common import OUT
json.dump(res,open(OUT/"db_cost.json","w"),indent=1)
