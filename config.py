import os

# config.py dosyasının bulunduğu ana dizini alır (D:\ShoeHunterAI)
BASE_DIR = os.path.abspath(os.path.dirname(__file__))

class Config:
    SECRET_KEY = os.environ.get("SHOEHUNTER_SECRET_KEY", "shoehunter_ai_2026")
    
    # Veritabanı yolunu yeni 'veritabani' klasöründeki database.db dosyasına yönlendiriyoruz
    DB_PATH = os.path.join(BASE_DIR, "veritabani", "database.db")
    SQLALCHEMY_DATABASE_URI = f"sqlite:///{DB_PATH}"
    
    SQLALCHEMY_TRACK_MODIFICATIONS = False