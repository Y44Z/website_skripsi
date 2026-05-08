import os
os.environ['TF_CPP_MIN_LOG_LEVEL'] = '2'

from flask import Flask, render_template, request, jsonify
import yfinance as yf
import pandas as pd
import numpy as np
import joblib
from tensorflow.keras.models import load_model
from datetime import datetime, timedelta

app = Flask(__name__)

model  = load_model('model_skripsi_terbaik.h5')
scaler = joblib.load('scaler_skripsi_6_aset.pkl')

TICKERS = ["BTC-USD", "GC=F", "SI=F", "PL=F", "PA=F", "XRH0.L"]

# ── Batas resmi Yahoo Finance via yfinance ─────────────────────────────────
#   1m              → maks 7 hari ke belakang
#   5m/15m/30m/1h   → maks 60 hari ke belakang  (batas keras Yahoo)
#   1d ke atas      → tidak terbatas
#
#   days_back di sini diset 59 (bukan 60) untuk memberi satu hari buffer
#   agar tidak kena batas tepat di tepi yang kadang ditolak Yahoo.
# ───────────────────────────────────────────────────────────────────────────
INTERVAL_MAP = {
    '5m':  {'yf': '5m',  'days_back': 59, 'label': '5 Menit'},
    '10m': {'yf': '5m',  'days_back': 59, 'label': '10 Menit'},   # resample dari 5m
    '15m': {'yf': '15m', 'days_back': 59, 'label': '15 Menit'},
    '30m': {'yf': '30m', 'days_back': 59, 'label': '30 Menit'},
    '1h':  {'yf': '1h',  'days_back': 59, 'label': '1 Jam'},
    '30d': {'yf': '1d',  'days_back': 30, 'label': '30 Hari'},
    '60d': {'yf': '1d',  'days_back': 60, 'label': '60 Hari'},
    '90d': {'yf': '1d',  'days_back': 90, 'label': '90 Hari'},
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


def _normalize_close(df):
    """
    Terima output yfinance (kolom bisa MultiIndex atau flat),
    kembalikan DataFrame Close dengan kolom = nama ticker bersih.
    """
    if isinstance(df.columns, pd.MultiIndex):
        df = df['Close']
    elif 'Close' in df.columns:
        df = df[['Close']]
    # Bersihkan nama kolom
    df.columns = [str(c).replace('^', '') for c in df.columns]
    return df.ffill().bfill()


def fetch_daily(start, end):
    """
    Download data penutupan harian semua ticker.
    start/end boleh berupa string 'YYYY-MM-DD' atau datetime/Timestamp.
    """
    start_str = pd.Timestamp(start).strftime('%Y-%m-%d')
    # +2 hari buffer agar hari 'end' pasti masuk (Yahoo kadang eksklusif)
    end_str   = (pd.Timestamp(end) + timedelta(days=2)).strftime('%Y-%m-%d')

    raw = yf.download(
        TICKERS,
        start=start_str,
        end=end_str,
        interval='1d',
        progress=False,
        auto_adjust=True
    )
    return _normalize_close(raw)


def fetch_intraday(interval_key, end_dt=None):
    """
    Download data intraday semua ticker sesuai batas Yahoo Finance.
    Seluruh rentang yang tersedia (s/d days_back) selalu diambil;
    kemudian dipotong sampai end_dt jika diberikan.

    end_dt : datetime | None
        Jika None → ambil sampai detik sekarang.
    """
    cfg         = INTERVAL_MAP[interval_key]
    yf_interval = cfg['yf']
    days_back   = cfg['days_back']

    now   = datetime.utcnow()
    start = now - timedelta(days=days_back)

    raw = yf.download(
        TICKERS,
        start=start.strftime('%Y-%m-%d'),
        end=(now + timedelta(days=1)).strftime('%Y-%m-%d'),
        interval=yf_interval,
        progress=False,
        auto_adjust=True
    )
    df = _normalize_close(raw)

    # Resample 10m dari 5m
    if interval_key == '10m':
        df = df.resample('10min').last().ffill()

    # Normalisasi index → timezone-naive UTC
    if df.index.tz is not None:
        df.index = df.index.tz_convert('UTC').tz_localize(None)

    # Potong s/d end_dt
    if end_dt is not None:
        df = df[df.index <= pd.Timestamp(end_dt)]
    # Tidak ada potongan → data penuh dipakai (end_dt=None berarti "sampai sekarang")

    return df


def predict_one(window_df, mode='bivariate'):
    """
    Prediksi satu langkah ke depan dari window tepat 30 baris terakhir.
    Kembalikan harga BTC (USD) atau None jika data tidak cukup.
    """
    if len(window_df) < 30:
        return None

    tail = window_df.tail(30)

    try:
        full_data = tail[TICKERS].values   # (30, 6)
    except KeyError:
        return None

    scaled = scaler.transform(full_data)

    if mode == 'bivariate':
        input_arr = scaled[:, :2]
        input_arr = np.hstack([input_arr, np.zeros((30, 1))])
    else:
        input_arr = scaled[:, :3]

    X           = np.array([input_arr])        # (1, 30, 3)
    pred_scaled = model.predict(X, verbose=0)

    dummy       = np.zeros((1, 6))
    dummy[0, 0] = pred_scaled[0, 0]
    return float(scaler.inverse_transform(dummy)[0, 0])


# ─── ROUTES ─────────────────────────────────────────────────────────────────

@app.route('/')
def index():
    today_str = datetime.now().strftime('%Y-%m-%d')
    today_dt  = datetime.now()

    # ── Baca parameter ──────────────────────────────────────────────────────
    target_date_str = request.args.get('target_date', today_str)
    target_time_str = request.args.get('target_time', '')
    history_range   = int(request.args.get('history_range', 30))
    interval_key    = request.args.get('interval', '30d')

    is_intraday = interval_key not in ('30d', '60d', '90d')

    # ── Bangun target_end_dt untuk mode intraday ────────────────────────────
    target_end_dt = None
    if is_intraday:
        if target_time_str:
            try:
                target_end_dt = datetime.strptime(
                    f"{target_date_str} {target_time_str}", '%Y-%m-%d %H:%M'
                )
            except ValueError:
                target_end_dt = today_dt
        else:
            target_end_dt = today_dt   # tanpa filter waktu → ambil sampai sekarang

    # Jangan boleh maju ke masa depan
    target_date = pd.to_datetime(target_date_str)
    if target_date > pd.to_datetime(today_str):
        target_date     = pd.to_datetime(today_str)
        target_date_str = today_str

    if target_end_dt and target_end_dt > today_dt:
        target_end_dt = today_dt

    # ── Harga live BTC ──────────────────────────────────────────────────────
    harga_aktual = 0.0
    try:
        btc_raw = yf.download(
            "BTC-USD", period="1d", interval="1m",
            progress=False, auto_adjust=True
        )
        btc_close = _normalize_close(btc_raw)
        if not btc_close.empty:
            harga_aktual = float(btc_close['BTC-USD'].iloc[-1])
    except Exception:
        pass

    # ── Prediksi 24 jam ke depan (pakai data harian) ────────────────────────
    prediksi_biv  = 0.0
    prediksi_mult = 0.0
    try:
        daily_window  = fetch_daily(
            target_date - timedelta(days=62),
            target_date
        )
        prediksi_biv  = predict_one(daily_window[TICKERS], mode='bivariate')   or 0.0
        prediksi_mult = predict_one(daily_window[TICKERS], mode='multivariate') or 0.0
    except Exception as e:
        app.logger.warning(f"Prediksi 24j error: {e}")

    next_day = (datetime.now() + timedelta(days=1)).strftime('%Y-%m-%d %H:%M')

    # ── Backtesting ─────────────────────────────────────────────────────────
    hist_dates     = []
    hist_actuals   = []
    hist_preds_biv = []
    hist_preds_mult = []

    try:
        if not is_intraday:
            # ────────────────────────────────────────────────────────────────
            # Mode HARIAN (30d / 60d / 90d)
            # Perlu data sebanyak (history_range + 30 + buffer) hari ke belakang
            # dari target_date agar setiap titik punya window 30 bar.
            # ────────────────────────────────────────────────────────────────
            data_start = target_date - timedelta(days=history_range + 35)
            data_daily = fetch_daily(data_start, target_date)

            # Pastikan semua kolom ada
            missing = [t for t in TICKERS if t not in data_daily.columns]
            if missing:
                raise ValueError(f"Kolom hilang dari data harian: {missing}")

            n_rows = len(data_daily)
            for i in range(history_range, 0, -1):
                if n_rows < i + 30:
                    continue
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
            # ────────────────────────────────────────────────────────────────
            # Mode INTRADAY (5m / 10m / 15m / 30m / 1h)
            # Ambil seluruh data yang tersedia (maks 59 hari).
            # Bar backtesting: sebanyak yang muat dari data tersedia.
            # ────────────────────────────────────────────────────────────────
            intra_df = fetch_intraday(interval_key, end_dt=target_end_dt)

            n_rows = len(intra_df)
            if n_rows < 32:
                raise ValueError(f"Data intraday terlalu sedikit: {n_rows} bar")

            # Batasi jumlah titik prediksi agar tidak terlalu lambat
            n_bars_limit = {'5m': 288, '10m': 200, '15m': 150, '30m': 100, '1h': 80}
            max_points   = n_bars_limit.get(interval_key, 80)
            max_iter     = min(max_points, n_rows - 31)

            for i in range(max_iter, 0, -1):
                if n_rows < i + 30:
                    continue
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
                    hist_dates.append(pd.Timestamp(ts).strftime('%H:%M'))
                else:
                    hist_dates.append(pd.Timestamp(ts).strftime('%d/%m %H:%M'))

    except Exception as e:
        app.logger.warning(f"Backtesting error: {e}")
        # hist_* tetap list kosong → template aman menampilkan "tidak ada data"

    hist_preds = hist_preds_biv

    mae_biv,  rmse_biv,  mape_biv,  acc_biv  = calculate_metrics(hist_actuals, hist_preds_biv)
    mae_mult, rmse_mult, mape_mult, acc_mult  = calculate_metrics(hist_actuals, hist_preds_mult)

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
        mae_biv=mae_biv,   rmse_biv=rmse_biv,   mape_biv=mape_biv,   acc_biv=acc_biv,
        mae_mult=mae_mult, rmse_mult=rmse_mult, mape_mult=mape_mult, acc_mult=acc_mult,
        mae=mae_biv, rmse=rmse_biv, mape=mape_biv, acc=acc_biv,
        hist_dates=hist_dates,
        hist_actuals=hist_actuals,
        hist_preds=hist_preds,
        hist_preds_mult=hist_preds_mult,
    )


@app.route('/api/predict', methods=['GET'])
def api_predict():
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

    try:
        window_df = fetch_daily(now - timedelta(days=62), now)
        if len(window_df) < 30:
            return jsonify({'error': 'Data tidak cukup'}), 500
        pred = predict_one(window_df[TICKERS], mode=mode)
        if pred is None:
            return jsonify({'error': 'Prediksi gagal'}), 500
    except Exception as e:
        return jsonify({'error': str(e)}), 500

    return jsonify({
        'target_datetime': dt_str,
        'mode':            mode,
        'predicted_price': round(pred, 2),
        'currency':        'USD',
    })


if __name__ == '__main__':
    app.run(debug=True, port=8000)