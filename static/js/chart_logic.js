function renderDashboardChart(labels, actualData) {
    const ctx = document.getElementById('chartDashboard');
    if (!ctx) return;
    
    new Chart(ctx, {
        type: 'line',
        data: {
            labels: labels,
            datasets: [{
                label: 'Harga BTC ($)',
                data: actualData,
                borderColor: '#0d6efd',
                backgroundColor: 'rgba(13, 110, 253, 0.1)',
                fill: true,
                tension: 0.1 // Kurangi tension agar lebih stabil
            }]
        },
        options: {
            responsive: true,
            maintainAspectRatio: false, // WAJIB: Agar mengikuti tinggi div induk
            animation: {
                duration: 500 // Mempercepat animasi agar tidak nge-lag saat resize
            }
        }
    });
}

function renderAnalisisChart(labels, actualData, predData) {
    const ctx = document.getElementById('chartAnalisis').getContext('2d');
    if (!ctx) return;

    new Chart(ctx, {
        type: 'line',
        data: {
            labels: labels,
            datasets: [
                {
                    label: 'Harga Aktual',
                    data: actualData,
                    borderColor: '#212529',
                    borderWidth: 2,
                    fill: false,
                    pointRadius: 2
                },
                {
                    label: 'Prediksi LSTM',
                    data: predData, // Data ini harus terisi!
                    borderColor: '#198754',
                    borderDash: [5, 5], // Ini yang bikin garis putus-putus
                    borderWidth: 2,
                    fill: false,
                    pointRadius: 2
                }
            ]
        },
        options: {
            responsive: true,
            maintainAspectRatio: false
        }
    });
}