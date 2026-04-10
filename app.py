import os
import json
os.environ['TF_CPP_MIN_LOG_LEVEL'] = '2'

from flask import Flask, render_template, request
import yfinance as yf
import pandas as pd
import numpy as np
import joblib
from tensorflow.keras.models import load_model
from datetime import datetime, timedelta

app = Flask(__name__)

model = load_model('model_skripsi_terbaik.h5')
scaler = joblib.load('scaler_skripsi_6_aset.pkl')

def calculate_metrics(actual, predicted):
    actual, predicted = np.array(actual), np.array(predicted)
    mae = np.mean(np.abs(actual - predicted))
    rmse = np.sqrt(np.mean((actual - predicted)**2))
    mape = np.mean(np.abs((actual - predicted) / actual)) * 100
    return round(mae, 2), round(rmse, 2), round(mape, 2), round(100 - mape, 2)

@app.route('/')
def index():
    # --- PROSES INPUT USER ---
    # Jika tidak ada input, gunakan default hari ini dan 30 hari histori
    target_date_str = request.args.get('target_date', datetime.now().strftime('%Y-%m-%d'))
    history_range = int(request.args.get('history_range', 30))
    
    target_date = pd.to_datetime(target_date_str)
    
    # Ambil data (window 30 hari + range histori)
    tickers = ["BTC-USD", "GC=F", "SI=F", "PL=F", "PA=F", "XRH0.L"]
    start_fetch = target_date - timedelta(days=history_range + 60)
    data_raw = yf.download(tickers, start=start_fetch, end=target_date + timedelta(days=1), progress=False)['Close']
    data_raw = data_raw.ffill().bfill()

    # --- 1. PREDIKSI TANGGAL INPUT ---
    # Mengambil 30 data tepat sebelum target_date
    input_data = data_raw[data_raw.index < target_date].tail(30)
    
    if len(input_data) == 30:
        scaled_input = scaler.transform(input_data.values)
        X_live = np.array([scaled_input[:, :3]])
        pred_scaled = model.predict(X_live, verbose=0)
        
        dummy = np.zeros((1, 6))
        dummy[0, 0] = pred_scaled[0, 0]
        prediction_val = scaler.inverse_transform(dummy)[0, 0]
    else:
        prediction_val = 0

    # --- 2. ANALISIS HISTORI DINAMIS ---
    hist_actuals, hist_preds, dates = [], [], []
    
    # Loop sebanyak range yang dipilih (30/60/90/120)
    for i in range(history_range, 0, -1):
        if len(data_raw) > (i + 30):
            window = data_raw.iloc[-(i+30):-i]
            actual_price = data_raw['BTC-USD'].iloc[-i]
            
            s_window = scaler.transform(window.values)
            X_hist = np.array([s_window[:, :3]])
            p_final_scaled = model.predict(X_hist, verbose=0)
            
            d_dummy = np.zeros((1, 6))
            d_dummy[0, 0] = p_final_scaled[0, 0]
            p_final = scaler.inverse_transform(d_dummy)[0, 0]
            
            hist_actuals.append(float(actual_price))
            hist_preds.append(float(p_final))
            dates.append(data_raw.index[-i].strftime('%d/%m'))

    mae, rmse, mape, acc = calculate_metrics(hist_actuals, hist_preds) if hist_preds else (0,0,0,0)

    return render_template('index.html', 
                           target_date=target_date_str,
                           history_range=history_range,
                           harga_aktual=f"{data_raw['BTC-USD'].iloc[-1]:,.2f}",
                           prediksi_val=f"{prediction_val:,.2f}",
                           mae=mae, rmse=rmse, mape=mape, acc=acc,
                           hist_dates=dates, hist_actuals=hist_actuals, hist_preds=hist_preds)

if __name__ == '__main__':
    app.run(debug=True, port=8000)