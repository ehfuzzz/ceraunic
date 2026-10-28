# Vercel entrypoint. scripts/deploy-engine.sh copies wi/ (engine, api, auction, eval ladder/fees, elasticity
# portal estimator) and demo-data/ next to this file in a git-less bundle.
from wi.api.app import app  # noqa: F401
