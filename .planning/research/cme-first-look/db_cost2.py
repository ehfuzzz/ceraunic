from common import databento_key
key=databento_key()
import databento as db
c=db.Historical(key)
W=["H1","H2","H3","H4","H5","H6","H7","HR","HS","HQ","HW","H0","LP","K1","K2","K3","K4","K5","K6","K7","KR","KS","KQ","KW","K0","KP"]
fut=[x+".FUT" for x in W]
for name,syms,schema,s,e in [("fut26 trades 2010-26",fut,"trades","2010-06-06","2026-10-24"),("fut26 trades 2022-10..",fut,"trades","2022-10-01","2026-10-24"),("fut26 stats 2022-10..",fut,"statistics","2022-10-01","2026-10-24"),("fut26 defn 1 day",fut,"definition","2026-10-22","2026-10-23"),("fut26 mbp1 2022-10..",fut,"mbp-1","2022-10-01","2026-10-24")]:
    try:
        kw=dict(dataset="GLBX.MDP3",symbols=syms,stype_in="parent",schema=schema,start=s,end=e)
        print(name,"cost",round(c.metadata.get_cost(**kw),4),"records",c.metadata.get_record_count(**kw))
    except Exception as ex: print(name,"ERR",str(ex)[:150])
for o in ["H4.OPT","H3.OPT","HQX.OPT","H4Z.OPT"]:
    try:
        kw=dict(dataset="GLBX.MDP3",symbols=[o],stype_in="parent",schema="trades",start="2022-10-01",end="2026-10-24")
        print(o,"trades records",c.metadata.get_record_count(**kw),"cost",round(c.metadata.get_cost(**kw),4))
    except Exception as ex: print(o,"ERR",str(ex)[:120])
