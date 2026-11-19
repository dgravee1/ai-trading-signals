import os
import json
import yfinance as yf
import feedparser
import requests
from datetime import datetime
import google.generativeai as genai
from strategies import calculate_indicators, evaluate_technical_strategies
from database import save_signal, update_active_signals_status, log_event

# قائمة شاملة لأزواج الفوريكس والذهب والفضة والنفط
ASSETS = [
    # المعادن والطاقة (السلع)
    {"symbol": "GC=F", "tv_symbol": "OANDA:XAUUSD", "name": "الذهب (XAU/USD)", "category": "السلع والمعادن", "decimals": 2},
    {"symbol": "SI=F", "tv_symbol": "OANDA:XAGUSD", "name": "الفضة (XAG/USD)", "category": "السلع والمعادن", "decimals": 3},
    {"symbol": "CL=F", "tv_symbol": "TVC:USOIL", "name": "النفط الخام (WTI)", "category": "السلع والمعادن", "decimals": 2},
    {"symbol": "BZ=F", "tv_symbol": "TVC:UKOIL", "name": "نفط برنت (BRENT)", "category": "السلع والمعادن", "decimals": 2},
    
    # أزواج الفوريكس الرئيسية (Majors)
    {"symbol": "EURUSD=X", "tv_symbol": "FX:EURUSD", "name": "EUR/USD", "category": "الفوريكس الرئيسي", "decimals": 5},
    {"symbol": "GBPUSD=X", "tv_symbol": "FX:GBPUSD", "name": "GBP/USD", "category": "الفوريكس الرئيسي", "decimals": 5},
    {"symbol": "USDJPY=X", "tv_symbol": "FX:USDJPY", "name": "USD/JPY", "category": "الفوريكس الرئيسي", "decimals": 3},
    {"symbol": "USDCHF=X", "tv_symbol": "FX:USDCHF", "name": "USD/CHF", "category": "الفوريكس الرئيسي", "decimals": 5},
    {"symbol": "USDCAD=X", "tv_symbol": "FX:USDCAD", "name": "USD/CAD", "category": "الفوريكس الرئيسي", "decimals": 5},
    {"symbol": "AUDUSD=X", "tv_symbol": "FX:AUDUSD", "name": "AUD/USD", "category": "الفوريكس الرئيسي", "decimals": 5},
    {"symbol": "NZDUSD=X", "tv_symbol": "FX:NZDUSD", "name": "NZD/USD", "category": "الفوريكس الرئيسي", "decimals": 5},

    # أزواج التقاطعات القوية (Crosses)
    {"symbol": "GBPJPY=X", "tv_symbol": "FX:GBPJPY", "name": "GBP/JPY", "category": "تقاطعات الفوريكس", "decimals": 3},
    {"symbol": "EURJPY=X", "tv_symbol": "FX:EURJPY", "name": "EUR/JPY", "category": "تقاطعات الفوريكس", "decimals": 3},
    {"symbol": "EURGBP=X", "tv_symbol": "FX:EURGBP", "name": "EUR/GBP", "category": "تقاطعات الفوريكس", "decimals": 5},
    {"symbol": "EURAUD=X", "tv_symbol": "FX:EURAUD", "name": "EUR/AUD", "category": "تقاطعات الفوريكس", "decimals": 5},
    {"symbol": "GBPAUD=X", "tv_symbol": "FX:GBPAUD", "name": "GBP/AUD", "category": "تقاطعات الفوريكس", "decimals": 5}
]

# ذاكرة مؤقتة لآخر حالة لكل زوج لعرضها مباشرة في الموقع
LATEST_MARKET_STATE = {}
LATEST_NEWS = []
LAST_SCAN_TIME = "لم يبدأ الفحص بعد"

def fetch_economic_news():
    """
    يجلب آخر الأخبار الاقتصادية والمالية من مصادر RSS مجانية ومباشرة.
    """
    global LATEST_NEWS
    feeds = [
        "https://www.investing.com/rss/news_1.rss",   # أخبار الفوريكس
        "https://www.investing.com/rss/news_11.rss",  # أخبار السلع والذهب
        "https://feeds.finance.yahoo.com/rss/2.0/headline?s=GC=F,EURUSD=X&region=US&lang=en-US"
    ]
    news_items = []
    for url in feeds:
        try:
            feed = feedparser.parse(url)
            for entry in feed.entries[:4]:
                news_items.append({
                    "title": entry.get("title", ""),
                    "published": entry.get("published", "الآن"),
                    "link": entry.get("link", "#")
                })
        except Exception:
            continue
    if news_items:
        LATEST_NEWS = news_items[:10]
    return LATEST_NEWS

def ask_gemini_ai(asset_name: str, tech_data: dict, news_headlines: list) -> dict:
    """
    يرسل نتائج التحليل الفني + الأخبار إلى Gemini AI لتأكيد الصفقة أو رفضها.
    """
    api_key = os.getenv("GEMINI_API_KEY", "").strip()
    if not api_key:
        # في حال عدم وضع مفتاح Gemini، يعتمد النظام على الفلترة الفنية الصارمة
        return {
            "approved": True,
            "final_action": tech_data["signal"],
            "confidence": tech_data["confidence"],
            "summary": f"توافق فني ({tech_data['confidence']}%) بناءً على: " + " | ".join(tech_data["reasons"][:2])
        }

    try:
        genai.configure(api_key=api_key)
        model = genai.GenerativeModel("gemini-2.0-flash")
        
        news_text = "\n".join([f"- {n['title']}" for n in news_headlines[:5]])
        prompt = f"""
        أنت محلل مالي وخبير تداول مؤسساتي (Institutional Trader).
        قم بتقييم هذه الفرصة التداولية على فريم 5 دقائق للأصل: {asset_name}
        
        البيانات الفنية المحسوبة:
        - الإشارة الفنية الأولية: {tech_data['signal']}
        - السعر الحالي: {tech_data['current_price']}
        - مؤشر RSI: {tech_data['rsi']}
        - متوسط EMA 200: {tech_data['ema200']}
        - الدعم اللحظي: {tech_data['support']} | المقاومة اللحظية: {tech_data['resistance']}
        - الأسباب الفنية: {', '.join(tech_data['reasons'])}
        
        أحدث عناوين الأخبار الاقتصادية:
        {news_text}
        
        المطلوب: أجب بصيغة JSON فقط بدون أي نص إضافي خارج JSON:
        {{
            "approved": true أو false (وافق فقط إذا كانت الإشارة منطقية ولا تتعارض مع خبر خطير),
            "final_action": "BUY" أو "SELL" أو "WAIT",
            "confidence": رقم بين 60 و 95,
            "summary": "شرح احترافي ومختصر باللغة العربية في جملتين يوضح سبب الدخول والمخاطر"
        }}
        """
        response = model.generate_content(prompt)
        raw_text = response.text.strip()
        if raw_text.startswith("```json"):
            raw_text = raw_text[7:-3].strip()
        elif raw_text.startswith("```"):
            raw_text = raw_text[3:-3].strip()
        result = json.loads(raw_text)
        return result
    except Exception as e:
        return {
            "approved": True,
            "final_action": tech_data["signal"],
            "confidence": tech_data["confidence"],
            "summary": "تحليل فني مؤكد (تجاوز الذكاء الاصطناعي مؤقتاً): " + "، ".join(tech_data["reasons"][:2])
        }

def run_market_scan():
    """
    الدورة الرئيسية التي تعمل كل 5 دقائق في الخلفية لفحص جميع الأزواج.
    """
    global LATEST_MARKET_STATE, LAST_SCAN_TIME
    now_str = datetime.utcnow().strftime("%Y-%m-%d %H:%M:%S UTC")
    LAST_SCAN_TIME = now_str
    log_event("بدء فحص السوق الشامل (فريم 5 دقائق)...")
    
    news = fetch_economic_news()
    current_prices = {}

    for asset in ASSETS:
        sym = asset["symbol"]
        decimals = asset["decimals"]
        try:
            # جلب بيانات فريم 5 دقائق لآخر 5 أيام
            ticker = yf.Ticker(sym)
            df = ticker.history(period="5d", interval="5m")
            
            if df.empty or len(df) < 50:
                continue

            df = calculate_indicators(df)
            tech = evaluate_technical_strategies(df)
            
            price = round(tech["current_price"], decimals)
            current_prices[sym] = price
            atr = tech["atr"]

            # حساب وقف الخسارة والأهداف بناءً على ATR (إدارة مخاطر احترافية)
            if tech["signal"] == "BUY":
                sl = round(price - (atr * 1.5), decimals)
                tp1 = round(price + (atr * 1.5), decimals)
                tp2 = round(price + (atr * 3.0), decimals)
            elif tech["signal"] == "SELL":
                sl = round(price + (atr * 1.5), decimals)
                tp1 = round(price - (atr * 1.5), decimals)
                tp2 = round(price - (atr * 3.0), decimals)
            else:
                sl = tp1 = tp2 = price

            ai_summary = "السوق في منطقة تذبذب أو انتظار تأكيد كسر مستويات."
            final_action = tech["signal"]
            final_conf = tech["confidence"]

            # إذا وجد المحرك الفني فرصة حقيقية، نستشير الذكاء الاصطناعي
            if tech["signal"] in ["BUY", "SELL"] and tech["confidence"] >= 65:
                ai_res = ask_gemini_ai(asset["name"], tech, news)
                if ai_res.get("approved") and ai_res.get("final_action") in ["BUY", "SELL"]:
                    final_action = ai_res["final_action"]
                    final_conf = ai_res.get("confidence", tech["confidence"])
                    ai_summary = ai_res.get("summary", "")

                    # حفظ التوصية في قاعدة البيانات وإرسالها لتيليغرام (إن وجد)
                    signal_payload = {
                        "timestamp": now_str,
                        "symbol": sym,
                        "display_name": asset["name"],
                        "category": asset["category"],
                        "action": final_action,
                        "entry_price": price,
                        "stop_loss": sl,
                        "tp1": tp1,
                        "tp2": tp2,
                        "confidence": final_conf,
                        "ai_analysis": ai_summary,
                        "tech_reasons": tech["reasons"]
                    }
                    save_signal(signal_payload)
                    send_telegram_alert(signal_payload)
                else:
                    final_action = "WAIT"
                    ai_summary = ai_res.get("summary", "تم رفض الإشارة من طرف فلتر الذكاء الاصطناعي.")

            LATEST_MARKET_STATE[sym] = {
                "symbol": sym,
                "tv_symbol": asset["tv_symbol"],
                "name": asset["name"],
                "category": asset["category"],
                "price": price,
                "action": final_action,
                "confidence": final_conf,
                "sl": sl,
                "tp1": tp1,
                "tp2": tp2,
                "rsi": tech["rsi"],
                "support": round(tech["support"], decimals),
                "resistance": round(tech["resistance"], decimals),
                "ai_summary": ai_summary,
                "reasons": tech["reasons"],
                "updated_at": now_str
            }

        except Exception as e:
            print(f"Error scanning {sym}: {e}")
            continue

    # تحديث حالة التوصيات السابقة (هل ضربت الهدف أو الستوب)
    update_active_signals_status(current_prices)
    log_event(f"اكتمل الفحص بنجاح لـ {len(LATEST_MARKET_STATE)} زوج مالي.")

def send_telegram_alert(sig: dict):
    """
    اختياري: يرسل التوصية فوراً إلى تيليغرام إذا قمت بإضافة التوكن في الإعدادات.
    """
    token = os.getenv("TELEGRAM_BOT_TOKEN", "").strip()
    chat_id = os.getenv("TELEGRAM_CHAT_ID", "").strip()
    if not token or not chat_id:
        return
    
    emoji = "🟢 شراء (BUY)" if sig["action"] == "BUY" else "🔴 بيع (SELL)"
    text = (
        f"🚨 *توصية ذكية جديدة (فريم 5 دقائق)* 🚨\n\n"
        f"💎 *الأصل:* {sig['display_name']}\n"
        f"📊 *النوع:* {emoji}\n"
        f"💰 *سعر الدخول:* `{sig['entry_price']}`\n"
        f"🛑 *وقف الخسارة (SL):* `{sig['stop_loss']}`\n"
        f"🎯 *الهدف الأول (TP1):* `{sig['tp1']}`\n"
        f"🚀 *الهدف الثاني (TP2):* `{sig['tp2']}`\n"
        f"🧠 *نسبة الثقة:* {sig['confidence']}%\n\n"
        f"📝 *تحليل AI:* {sig['ai_analysis']}"
    )
    try:
        requests.post(
            f"https://api.telegram.org/bot{token}/sendMessage",
            json={"chat_id": chat_id, "text": text, "parse_mode": "Markdown"},
            timeout=5
        )
    except Exception:
        pass
