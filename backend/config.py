
import os
from dotenv import load_dotenv

load_dotenv()

ML_BASE_URL = os.getenv("ML_BASE_URL", "http://127.0.0.1:8001")

# ML timeout (30 secods by default)
ML_TIMEOUT = int(os.getenv("ML_TIMEOUT", "30"))

_default_data_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "data"))
DATA_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "data"))


# image parser settings
SITE_BASE_URL = os.getenv("SITE_BASE_URL", "https://vino-svoe.ru")

# true / flase either lets the algorithm to scrape images from the website or prohibits it and demands loading from local cache 
ALLOW_ON_DEMAND_FETCH = os.getenv("ALLOW_ON_DEMAND_FETCH", "true").lower() == "true"

# parsing timeout in seconds
FETCH_DEADLINE = int(os.getenv("FETCH_DEADLINE", "10"))