import os
from dotenv import load_dotenv

load_dotenv()


class Config:
    # 키움증권 REST API
    APP_KEY = os.getenv("KIWOOM_APP_KEY", "")
    APP_SECRET = os.getenv("KIWOOM_APP_SECRET", "")
    BASE_URL = os.getenv("KIWOOM_BASE_URL", "https://openapi.koreainvestment.com:29443")
    ACCOUNT_NO = os.getenv("KIWOOM_ACCOUNT_NO", "")
    IS_PAPER_TRADING = os.getenv("IS_PAPER_TRADING", "true").lower() == "true"

    # 계좌번호 분리
    @property
    def cano(self):
        """계좌번호 앞 8자리"""
        return self.ACCOUNT_NO.replace("-", "")[:8]

    @property
    def acnt_prdt_cd(self):
        """계좌상품코드 뒤 2자리"""
        parts = self.ACCOUNT_NO.split("-")
        return parts[1] if len(parts) > 1 else "01"

    # Flask
    FLASK_HOST = "0.0.0.0"
    FLASK_PORT = 5000
    FLASK_DEBUG = True
