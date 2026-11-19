import pandas as pd
import numpy as np

def calculate_indicators(df: pd.DataFrame) -> pd.DataFrame:
    """
    يحسب جميع المؤشرات الفنية العالمية على بيانات الشموع اليابانية.
    """
    if df.empty or len(df) < 50:
        return df

    close = df['Close']
    high = df['High']
    low = df['Low']

    # 1. المتوسطات المتحركة (EMA 9, 21, 50, 200) - استراتيجيات الاتجاه
    df['EMA_9'] = close.ewm(span=9, adjust=False).mean()
    df['EMA_21'] = close.ewm(span=21, adjust=False).mean()
    df['EMA_50'] = close.ewm(span=50, adjust=False).mean()
    df['EMA_200'] = close.ewm(span=200, adjust=False).mean()

    # 2. مؤشر القوة النسبية (RSI 14) - الزخم والتشبع
    delta = close.diff()
    gain = (delta.where(delta > 0, 0)).rolling(window=14).mean()
    loss = (-delta.where(delta < 0, 0)).rolling(window=14).mean()
    rs = gain / loss
    df['RSI'] = 100 - (100 / (1 + rs))

    # 3. مؤشر الماكد (MACD 12, 26, 9)
    ema12 = close.ewm(span=12, adjust=False).mean()
    ema26 = close.ewm(span=26, adjust=False).mean()
    df['MACD'] = ema12 - ema26
    df['MACD_Signal'] = df['MACD'].ewm(span=9, adjust=False).mean()
    df['MACD_Hist'] = df['MACD'] - df['MACD_Signal']

    # 4. البولينجر باند (Bollinger Bands 20, 2) - التقلب والانفجار السعري
    sma20 = close.rolling(window=20).mean()
    std20 = close.rolling(window=20).std()
    df['BB_Upper'] = sma20 + (std20 * 2)
    df['BB_Lower'] = sma20 - (std20 * 2)
    df['BB_Mid'] = sma20

    # 5. مؤشر الستوكاستيك (Stochastic Oscillator 14, 3, 3)
    low14 = low.rolling(window=14).min()
    high14 = high.rolling(window=14).max()
    df['Stoch_K'] = 100 * ((close - low14) / (high14 - low14))
    df['Stoch_D'] = df['Stoch_K'].rolling(window=3).mean()

    # 6. مؤشر متوسط المدى الحقيقي (ATR 14) - لحساب وقف الخسارة والأهداف بدقة
    tr1 = high - low
    tr2 = abs(high - close.shift())
    tr3 = abs(low - close.shift())
    tr = pd.concat([tr1, tr2, tr3], axis=1).max(axis=1)
    df['ATR'] = tr.rolling(window=14).mean()

    # 7. سحابة إيشيموكو (Ichimoku Tenkan & Kijun)
    nine_high = high.rolling(window=9).max()
    nine_low = low.rolling(window=9).min()
    df['Tenkan_Sen'] = (nine_high + nine_low) / 2

    period26_high = high.rolling(window=26).max()
    period26_low = low.rolling(window=26).min()
    df['Kijun_Sen'] = (period26_high + period26_low) / 2

    return df

def evaluate_technical_strategies(df: pd.DataFrame) -> dict:
    """
    يجمع إشارات الاستراتيجيات العالمية ويعطي تقييماً رقمياً ومنطقياً (Confluence Score).
    """
    if df.empty or len(df) < 50:
        return {"signal": "WAIT", "score": 0, "reasons": ["بيانات غير كافية"], "atr": 0}

    last = df.iloc[-1]
    prev = df.iloc[-2]
    price = float(last['Close'])
    atr = float(last['ATR']) if not pd.isna(last['ATR']) else price * 0.002

    buy_points = 0
    sell_points = 0
    reasons = []

    # الاستراتيجية 1: اتجاه EMA 200 العام
    if price > last['EMA_200']:
        buy_points += 1
        reasons.append("السعر يتداول فوق متوسط 200 (اتجاه عام صاعد)")
    else:
        sell_points += 1
        reasons.append("السعر يتداول تحت متوسط 200 (اتجاه عام هابط)")

    # الاستراتيجية 2: تقاطع المتوسطات السريعة (EMA 9 / EMA 21)
    if last['EMA_9'] > last['EMA_21']:
        buy_points += 1
        if prev['EMA_9'] <= prev['EMA_21']:
            buy_points += 1
            reasons.append("تقاطع ذهبي إيجابي حديث بين EMA 9 و EMA 21")
    else:
        sell_points += 1
        if prev['EMA_9'] >= prev['EMA_21']:
            sell_points += 1
            reasons.append("تقاطع سلبي حديث بين EMA 9 و EMA 21")

    # الاستراتيجية 3: مؤشر القوة النسبية (RSI)
    rsi = float(last['RSI'])
    if rsi < 32:
        buy_points += 2
        reasons.append(f"تشبع بيعي قوي على RSI ({rsi:.1f}) - احتمالية ارتداد صاعد")
    elif rsi > 68:
        sell_points += 2
        reasons.append(f"تشبع شرائي قوي على RSI ({rsi:.1f}) - احتمالية تصحيح هابط")
    elif 50 < rsi <= 68:
        buy_points += 1
    elif 32 <= rsi < 50:
        sell_points += 1

    # الاستراتيجية 4: زخم الماكد (MACD)
    if last['MACD'] > last['MACD_Signal'] and last['MACD_Hist'] > prev['MACD_Hist']:
        buy_points += 1
        reasons.append("زخم إيجابي متزايد على مؤشر MACD")
    elif last['MACD'] < last['MACD_Signal'] and last['MACD_Hist'] < prev['MACD_Hist']:
        sell_points += 1
        reasons.append("زخم سلبي متزايد على مؤشر MACD")

    # الاستراتيجية 5: البولينجر باند (ارتداد من الحدود)
    if price <= last['BB_Lower']:
        buy_points += 1.5
        reasons.append("ملامسة الحد السفلي للبولينجر باند (دعم ديناميكي)")
    elif price >= last['BB_Upper']:
        sell_points += 1.5
        reasons.append("ملامسة الحد العلوي للبولينجر باند (مقاومة ديناميكية)")

    # الاستراتيجية 6: إيشيموكو (Tenkan / Kijun)
    if last['Tenkan_Sen'] > last['Kijun_Sen']:
        buy_points += 1
    else:
        sell_points += 1

    # حساب الدعوم والمقاومات اللحظية (آخر 30 شمعة)
    recent_high = float(df['High'].tail(30).max())
    recent_low = float(df['Low'].tail(30).min())

    total_possible = 8.5
    if buy_points >= 5.0 and buy_points > sell_points + 2:
        signal = "BUY"
        confidence = min(int((buy_points / total_possible) * 100), 95)
    elif sell_points >= 5.0 and sell_points > buy_points + 2:
        signal = "SELL"
        confidence = min(int((sell_points / total_possible) * 100), 95)
    else:
        signal = "WAIT"
        confidence = 50

    return {
        "signal": signal,
        "confidence": confidence,
        "buy_score": round(buy_points, 1),
        "sell_score": round(sell_points, 1),
        "reasons": reasons,
        "rsi": round(rsi, 2),
        "ema200": round(float(last['EMA_200']), 5),
        "atr": atr,
        "support": round(recent_low, 5),
        "resistance": round(recent_high, 5),
        "current_price": price
    }
