import pickle, numpy as np, math
from common import RAW
d=pickle.load(open(str(RAW)+"/daily.pkl","rb"))["CVG"]
nd=lambda y,m:d.loc[f"{y}-{m:02d}","hdd"].sum()
oct_rest=lambda y:d.loc[f"{y}-10-24":f"{y}-10-31","hdd"].sum()
yrs10=range(2016,2026); yrs30=range(1996,2026)
rest=[oct_rest(y)+nd(y,11)+nd(y,12) for y in yrs30]
print("Oct24-Dec31 HDD: mean10",round(np.mean([oct_rest(y)+nd(y,11)+nd(y,12) for y in yrs10]),1),"mean30",round(np.mean(rest),1),"sd30",round(np.std(rest,ddof=1),1))
print("Nov mean10",round(np.mean([nd(y,11) for y in yrs10]),1),"Dec mean10",round(np.mean([nd(y,12) for y in yrs10]),1))
known=d.loc["2026-10-01":"2026-10-23","hdd"].sum()
cme=145+530+819
sd=np.std(rest,ddof=1)
for mu_name,mu in (("CME marks",cme),("10y climo",known+np.mean([oct_rest(y)+nd(y,11)+nd(y,12) for y in yrs10]))):
    print(mu_name,"Q4 mean",round(mu,1),{k:round(0.5*(1+math.erf((k-mu)/(sd*math.sqrt(2)))),2) for k in (1250,1300,1350,1400,1450,1500,1550,1600,1650)})
