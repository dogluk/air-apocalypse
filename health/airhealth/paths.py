from pathlib import Path

HEALTH = Path(__file__).resolve().parents[1]
REPO = HEALTH.parent
DATA = HEALTH / "data"          # committed, open tier
LOCAL = HEALTH / "data_local"   # git-ignored, IHME files
CHARTS = HEALTH / "charts"
FONTS = REPO / "fonts"
