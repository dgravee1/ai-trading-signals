import os
import threading
from contextlib import asynccontextmanager
from fastapi import FastAPI, Request
from fastapi.responses import HTMLResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from apscheduler.schedulers.background import BackgroundScheduler
from dotenv import load_dotenv

from database import init_db, get_recent_signals
import engine

load_dotenv()

scheduler = BackgroundScheduler()

@asynccontextmanager
async def lifespan(app: FastAPI):
    # تهيئة قاعدة البيانات عند تشغيل السيرفر
    init_db()
    # تشغيل أول فحص فوراً في الخلفية لكي لا يتأخر إقلاع الموقع
    threading.Thread(target=engine.run_market_scan, daemon=True).start()
    # جدولة الفحص التلقائي كل 5 دقائق 24/7
    scheduler.add_job(engine.run_market_scan, 'interval', minutes=5, id='market_scan_job')
    scheduler.start()
    yield
    scheduler.shutdown()

app = FastAPI(title="AI Forex & Gold Signals Pro", lifespan=lifespan)

@app.get("/", response_class=HTMLResponse)
async def serve_dashboard():
    with open("index.html", "r", encoding="utf-8") as f:
        return f.read()

@app.get("/api/dashboard")
async def get_dashboard_data():
    return JSONResponse({
        "last_scan": engine.LAST_SCAN_TIME,
        "market_state": list(engine.LATEST_MARKET_STATE.values()),
        "signals_history": get_recent_signals(40),
        "news": engine.LATEST_NEWS
    })

@app.get("/api/ping")
async def keep_alive():
    """
    رابط مخصص لخدمات الاستيقاظ المجانية (Cron-job.org / UptimeRobot)
    لإبقاء السيرفر مستيقظاً 24 ساعة حتى لو أغلقت هاتفك ومتصفحك.
    """
    return {"status": "alive", "last_scan": engine.LAST_SCAN_TIME}

@app.post("/api/scan-now")
async def trigger_manual_scan():
    threading.Thread(target=engine.run_market_scan, daemon=True).start()
    return {"status": "started", "message": "تم بدء فحص السوق اللحظي الآن..."}

if __name__ == "__main__":
    import uvicorn
    port = int(os.environ.get("PORT", 8000))
    uvicorn.run("main:app", host="0.0.0.0", port=port)
