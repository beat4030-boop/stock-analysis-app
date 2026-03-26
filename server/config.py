import os
from dotenv import load_dotenv

load_dotenv()


class Config:
    # 키움증권 REST API (openapi.kiwoom.com)
    APP_KEY = os.getenv("KIWOOM_APP_KEY", "")
    SECRET_KEY = os.getenv("KIWOOM_SECRET_KEY", "")
    BASE_URL = os.getenv("KIWOOM_BASE_URL", "https://mockapi.kiwoom.com")
    ACCOUNT_NO = os.getenv("KIWOOM_ACCOUNT_NO", "")
    IS_PAPER_TRADING = os.getenv("IS_PAPER_TRADING", "true").lower() == "true"

    # Flask
    FLASK_HOST = "0.0.0.0"
    FLASK_PORT = 5000
    FLASK_DEBUG = True
