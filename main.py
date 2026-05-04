import os
import json
os.environ['TF_CPP_MIN_LOG_LEVEL'] = '2'

from flask import Flask, render_template, request, jsonify
import yfinance as yf
import pandas as pd
import numpy as np
import joblib
from tensorflow.keras.models import load_model
from datetime import datetime, timedelta
import pytz

app = Flask(__name__)

model  = load_model('model_skripsi_terbaik.h5')
scaler = joblib.load('scaler_skripsi_6_aset.pkl')

TICKERS = ["BTC-USD", "GC=F", "SI=F", "PL=F", "PA=F", "XRH0.L"]

# Kolom yang dipakai tiap mode
MODE_COLS = {
    'bivariate':   [0, 1],        # BTC + Emas (GC=F)
    'multivariate': [0, 1, 2, 3, 4, 5],  # semua 6 aset
}

# Mapping interval yfinance
INTERVAL_MAP = {
    '5m':   {'yf': '5m',  'days_back': 5,   'label': '5 Menit'},
    '10m':  {'yf': '5m',  'days_back': 5,   'label': '10 Menit'},   # resample dari 5m
    '15m':  {'yf': '15m', 'days_back': 7,   'label': '15 Menit'},
    '30m':  {'yf': '30m', 'days_back': 14,  'label': '30 Menit'},
    '1h':   {'yf': '1h',  'days_back': 30,  'label': '1 Jam'},
    '30d':  {'yf': '1d',  'days_back': 30,  'label': '30 Hari'},
    '60d':  {'yf': '1d',  'days_back': 60,  'label': '60 Hari'},
    '90d':  {'yf': '1d',  'days_back': 90,  'label': '90 Hari'},
}


# ─── HELPERS ────────────────────────────────────────────────────────────────

def calculate_metrics(actual, predicted):
    actual, predicted = np.array(actual), np.array(predicted)
    if len(actual) == 0:
        return 0, 0, 0, 0
    mae  = np.mean(np.abs(actual - predicted))
    rmse = np.sqrt(np.mean((actual - predicted) ** 2))
    mape = np.mean(np.abs((actual - predicted) / (actual + 1e-9))) * 100
    return round(mae, 2), round(rmse, 2), round(mape, 2), round(100 - mape, 2)


def fetch_daily(start, end):
    """Download data harian semua ticker."""
    df = yf.download(TICKERS, start=start, end=end + timedelta(days=1),
                     progress=False, auto_adjust=True)['Close']
    df.columns = [c.replace('^', '') for c in df.columns]
    return df.ffill().bfill()


def fetch_intraday(interval_key, n_bars=200):
    """
    Download data intraday untuk chart & prediksi terakhir.
    Mengembalikan DataFrame Close semua ticker dengan index datetime.
    """
    cfg = INTERVAL_MAP[interval_key]
    yf_interval = cfg['yf']
    days_back   = max(cfg['days_back'], 7)   # ambil cukup banyak

    end   = datetime.utcnow()
    start = end - timedelta(days=days_back)

    df = yf.download(TICKERS, start=start, end=end,
                     interval=yf_interval, progress=False,
                     auto_adjust=True)['Close']
    df.columns = [c.replace('^', '') for c in df.columns]
    df = df.ffill().bfill()

    # Resample 10m dari 5m jika perlu
    if interval_key == '10m':
        df = df.resample('10min').last().ffill()

    return df.tail(n_bars)


def predict_one(window_df, mode='bivariate'):
    """
    Prediksi satu langkah ke depan dari window 30 baris.
    mode: 'bivariate' atau 'multivariate'
    Selalu kembalikan harga BTC (kolom 0).
    """
    if len(window_df) < 30:
        return None

    tail = window_df.tail(30)
    # Pastikan semua 6 kolom tersedia untuk scaler
    full_data = tail[TICKERS].values if set(TICKERS).issubset(tail.columns) else tail.values

    scaled = scaler.transform(full_data)   # (30, 6)

    # Pilih kolom sesuai mode, tapi pad ke 3 kolom (arsitektur model: input [:3])
    if mode == 'bivariate':
        input_arr = scaled[:, :2]                       # BTC + Emas
        # pad kolom ke-3 dengan nol agar shape (30, 3) tetap masuk model
        input_arr = np.hstack([input_arr, np.zeros((30, 1))])
    else:
        input_arr = scaled[:, :3]                       # BTC+Emas+Perak (multivariate 3-feat)

    X = np.array([input_arr])                           # (1, 30, 3)
    pred_scaled = model.predict(X, verbose=0)

    dummy        = np.zeros((1, 6))
    dummy[0, 0]  = pred_scaled[0, 0]
    return float(scaler.inverse_transform(dummy)[0, 0])


# ─── ROUTES ─────────────────────────────────────────────────────────────────

@app.route('/')
def index():
    # ── param dari URL ──
    today_str     = datetime.now().strftime('%Y-%m-%d')
    target_date_str = request.args.get('target_date', today_str)
    history_range   = int(request.args.get('history_range', 30))
    interval_key    = request.args.get('interval', '30d')   # default: 30 hari

    # Jangan boleh maju ke masa depan untuk analisis
    target_date = pd.to_datetime(target_date_str)
    if target_date > pd.to_datetime(today_str):
        target_date     = pd.to_datetime(today_str)
        target_date_str = today_str

    # ── harga live BTC ──
    btc_live_df  = yf.download("BTC-USD", period="1d", interval="1m", progress=False, auto_adjust=True)['Close']
    harga_aktual = float(btc_live_df.iloc[-1]) if not btc_live_df.empty else 0.0

    # ── prediksi 24 jam ke depan (bivariate & multivariate) ──
    daily_window = fetch_daily(target_date - timedelta(days=60), target_date)

    prediksi_biv  = predict_one(daily_window[TICKERS], mode='bivariate')   or 0.0
    prediksi_mult = predict_one(daily_window[TICKERS], mode='multivariate') or 0.0

    # tanggal prediksi = besok
    next_day = (datetime.now() + timedelta(days=1)).strftime('%Y-%m-%d %H:%M')

    # ── data chart & analisis berdasarkan interval ──
    hist_dates, hist_actuals = [], []
    hist_preds_biv, hist_preds_mult = [], []

    if interval_key in ('30d', '60d', '90d'):
        # mode harian — pakai history_range
        data_daily = fetch_daily(
            target_date - timedelta(days=history_range + 60),
            target_date
        )
        for i in range(history_range, 0, -1):
            if len(data_daily) > (i + 30):
                window       = data_daily.iloc[-(i + 30):-i]
                actual_price = float(data_daily['BTC-USD'].iloc[-i])
                p_biv  = predict_one(window[TICKERS], mode='bivariate')
                p_mult = predict_one(window[TICKERS], mode='multivariate')
                if p_biv is None or p_mult is None:
                    continue
                hist_actuals.append(actual_price)
                hist_preds_biv.append(p_biv)
                hist_preds_mult.append(p_mult)
                hist_dates.append(data_daily.index[-i].strftime('%d/%m'))

    else:
        # mode intraday — ambil n_bars candle terakhir
        n_bars = {
            '5m': 100, '10m': 100, '15m': 80, '30m': 80, '1h': 72
        }.get(interval_key, 60)

        intra_df = fetch_intraday(interval_key, n_bars=n_bars + 35)

        for i in range(min(n_bars, len(intra_df) - 31), 0, -1):
            if len(intra_df) > (i + 30):
                window       = intra_df.iloc[-(i + 30):-i]
                actual_price = float(intra_df['BTC-USD'].iloc[-i])
                p_biv  = predict_one(window[TICKERS], mode='bivariate')
                p_mult = predict_one(window[TICKERS], mode='multivariate')
                if p_biv is None or p_mult is None:
                    continue
                hist_actuals.append(actual_price)
                hist_preds_biv.append(p_biv)
                hist_preds_mult.append(p_mult)
                ts = intra_df.index[-i]
                if interval_key in ('5m', '10m', '15m', '30m'):
                    hist_dates.append(ts.strftime('%H:%M'))
                else:
                    hist_dates.append(ts.strftime('%d/%m %H:%M'))

    # Gunakan bivariate sebagai hist_preds utama untuk chart & tabel
    hist_preds = hist_preds_biv

    mae_biv,  rmse_biv,  mape_biv,  acc_biv  = calculate_metrics(hist_actuals, hist_preds_biv)
    mae_mult, rmse_mult, mape_mult, acc_mult  = calculate_metrics(hist_actuals, hist_preds_mult)

    # Untuk tabel analisis & metrik ringkasan, pakai bivariate sebagai default
    mae, rmse, mape, acc = mae_biv, rmse_biv, mape_biv, acc_biv

    return render_template(
        'index.html',
        today_str     = today_str,
        target_date   = target_date_str,
        history_range = history_range,
        interval      = interval_key,
        harga_aktual  = f"{harga_aktual:,.2f}",
        prediksi_biv  = f"{prediksi_biv:,.2f}",
        prediksi_mult = f"{prediksi_mult:,.2f}",
        next_day      = next_day,
        mae_biv=mae_biv, rmse_biv=rmse_biv, mape_biv=mape_biv, acc_biv=acc_biv,
        mae_mult=mae_mult, rmse_mult=rmse_mult, mape_mult=mape_mult, acc_mult=acc_mult,
        mae=mae_biv, rmse=rmse_biv, mape=mape_biv, acc=acc_biv,
        hist_dates=hist_dates,
        hist_actuals=hist_actuals,
        hist_preds=hist_preds,
        hist_preds_mult=hist_preds_mult,
    )


@app.route('/api/predict', methods=['GET'])
def api_predict():
    """
    Prediksi kustom untuk tanggal+jam di masa DEPAN.
    Query param: datetime (ISO, e.g. 2025-06-01T14:00), mode (bivariate|multivariate)
    """
    dt_str = request.args.get('datetime', '')
    mode   = request.args.get('mode', 'bivariate')

    if not dt_str:
        return jsonify({'error': 'Parameter datetime diperlukan'}), 400

    try:
        target_dt = datetime.fromisoformat(dt_str)
    except ValueError:
        return jsonify({'error': 'Format datetime tidak valid'}), 400

    now = datetime.now()
    if target_dt <= now:
        return jsonify({'error': 'Hanya bisa prediksi untuk waktu di masa depan'}), 400

    # Gunakan 30 hari data terakhir sebagai window
    window_df = fetch_daily(now - timedelta(days=60), now)
    if len(window_df) < 30:
        return jsonify({'error': 'Data tidak cukup'}), 500

    pred = predict_one(window_df[TICKERS], mode=mode)
    if pred is None:
        return jsonify({'error': 'Prediksi gagal'}), 500

    return jsonify({
        'target_datetime': dt_str,
        'mode': mode,
        'predicted_price': round(pred, 2),
        'currency': 'USD',
    })


if __name__ == '__main__':
    app.run(debug=True, port=8000)