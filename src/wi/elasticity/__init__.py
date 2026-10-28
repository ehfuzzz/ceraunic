"""EVAL-06 elasticity engine: learn weather sensitivity from daily sales, size a Kalshi hedge.

design.py  regressors (numpy + stdlib only; shared by the evaluation and the portal)
fit.py     OLS with Newey-West HAC in numpy (checked against statsmodels in the eval run)
shrink.py  DerSimonian-Laird / Paule-Mandel priors, leave-one-out, credibility shrinkage
hedge.py   contracts, premium at asks/bids with fees, ladder payout, P&L legs
evaluate.py HE_cover / HE_ladder, block bootstrap
portal.py  estimate(sales_rows, weather_rows, priors) for the engine API (numpy only)
"""
