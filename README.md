# ShoeHunter AI / AI Buy Advisor

ShoeHunter AI, Turkiye pazarinda ayakkabi fiyat, stok, beden ve firsat takibi yapmak icin hazirlanan yerel bir uygulamadir.

Bu indirilmis surum iki katman tasir:

- `backend/`: FastAPI + MongoDB tabanli yeni API. AI Arama, AI Koc, Buy Advisor, Debug Lab, urun ailesi ve scheduler burada.
- `frontend/`: React arayuz. Dashboard, urunler, AI Arama, AI Koc, uyarilar, ayarlar, profil ve Debug Lab ekranlari burada.
- Kokteki `app.py` ve `web/`: onceki Flask/SQLite paneli. Geriye uyumluluk icin duruyor.

## Yerel Calistirma

Backend icin:

```powershell
cd backend
copy .env.example .env
python -m pip install -r requirements.txt
python -m uvicorn server:app --host 127.0.0.1 --port 8000 --reload
```

Frontend icin:

```powershell
cd frontend
copy .env.example .env
pnpm install
pnpm start
```

Varsayilan adresler:

- Backend API: `http://127.0.0.1:8000/api`
- Frontend: `http://127.0.0.1:3000`

## Gerekli Servisler

Yeni backend MongoDB ister.

```powershell
MONGO_URL=mongodb://localhost:27017
DB_NAME=shoehunter_ai
```

AI Koc istege baglidir. Ucretsiz/deneme icin once Gemini veya Groq kullanabilirsin:

```powershell
GEMINI_API_KEY=
GEMINI_MODEL=gemini-3.5-flash
GROQ_API_KEY=
GROQ_MODEL=llama-3.3-70b-versatile
```

Ucretli OpenAI API ile kullanmak istersen:

```powershell
OPENAI_API_KEY=
OPENAI_MODEL=gpt-4.1-mini
```

Eski Emergent entegrasyonu icin `EMERGENT_LLM_KEY` de desteklenir. Anahtar onceligi `GEMINI_API_KEY`, `GROQ_API_KEY`, `OPENAI_API_KEY`, `EMERGENT_LLM_KEY` seklindedir. Bu anahtarlar yoksa AI Koc kibarca kapali doner; AI Arama temel sorgu ile calismaya devam eder.

Telegram istege baglidir:

```powershell
TELEGRAM_BOT_TOKEN=
TELEGRAM_CHAT_ID=
```

## Hedeflenen Ozellikler

- Link ile takip
- Intersport fiyat, sepet indirimi, beden ve stok okuma
- Zero-link AI Arama
- Playwright tabanli JS site aramasi
- AI Koc model onerileri
- AI Buy Advisor: AL / ALINABILIR / BEKLE / BELIRSIZ karari
- Spektrum modu: renk fark etmez urun ailesi takibi
- Debug Lab
- Telegram bildirimi
- Manuel ve otomatik toplu kontrol

## Hata Kontrolu

Kokteki Flask tarafinin temel kontrolu:

```powershell
python scripts/check_project.py
```

Backend soz dizimi kontrolu:

```powershell
python -m py_compile backend\server.py backend\services.py backend\engines.py backend\insights.py backend\family.py backend\ai_service.py backend\browser_search.py
```
