// api_gateway/static/app.js

document.addEventListener('DOMContentLoaded', () => {
    // --- Chart Initialization ---
    const chartContainer = document.getElementById('main-chart');
    const chart = LightweightCharts.createChart(chartContainer, {
        layout: {
            backgroundColor: 'transparent',
            textColor: '#d1d5db',
        },
        grid: {
            vertLines: { color: 'rgba(42, 46, 57, 0.5)' },
            horzLines: { color: 'rgba(42, 46, 57, 0.5)' },
        },
        crosshair: {
            mode: LightweightCharts.CrosshairMode.Normal,
        },
        rightPriceScale: {
            borderColor: 'rgba(197, 203, 206, 0.8)',
        },
        timeScale: {
            borderColor: 'rgba(197, 203, 206, 0.8)',
            timeVisible: true,
            secondsVisible: true,
        },
    });

    const candleSeries = chart.addCandlestickSeries({
        upColor: '#26a69a',
        downColor: '#ef5350',
        borderVisible: false,
        wickUpColor: '#26a69a',
        wickDownColor: '#ef5350',
    });

    // Mock initial data
    let chartData = [
        { time: Math.floor(Date.now() / 1000) - 300, open: 2500, high: 2510, low: 2490, close: 2505 },
        { time: Math.floor(Date.now() / 1000) - 200, open: 2505, high: 2515, low: 2500, close: 2510 },
        { time: Math.floor(Date.now() / 1000) - 100, open: 2510, high: 2520, low: 2505, close: 2515 },
    ];
    candleSeries.setData(chartData);

    window.addEventListener('resize', () => {
        chart.resize(chartContainer.clientWidth, chartContainer.clientHeight);
    });

    // --- WebSocket Integration ---
    const protocol = window.location.protocol === 'https:' ? 'wss:' : 'ws:';
    const ws = new WebSocket(`${protocol}//${window.location.host}/ws`);

    ws.onopen = () => {
        addLog('WebSocket connection established.');
        document.getElementById('status-indicator').innerHTML = `
            <div class="w-3 h-3 bg-green-500 rounded-full"></div>
            Connected
        `;
    };

    ws.onmessage = (event) => {
        try {
            const data = JSON.parse(event.data);

            // Handle Executions
            if (data.order_id) {
                addLog(`[EXEC] ${data.side} ${data.quantity.toFixed(4)} @ ${data.price.toFixed(2)}`, 'text-blue-400 font-bold');
                updatePositions();
            }

            // Handle Features (Price Updates)
            if (data.features) {
                const newPrice = data.features.vwap || data.features.last_price;
                const lastCandle = chartData[chartData.length - 1];
                const now = Math.floor(Date.now() / 1000);

                if (now - lastCandle.time < 10) {
                    // Update current candle
                    lastCandle.close = newPrice;
                    lastCandle.high = Math.max(lastCandle.high, newPrice);
                    lastCandle.low = Math.min(lastCandle.low, newPrice);
                } else {
                    // New candle
                    const newCandle = {
                        time: now,
                        open: lastCandle.close,
                        high: Math.max(lastCandle.close, newPrice),
                        low: Math.min(lastCandle.close, newPrice),
                        close: newPrice
                    };
                    chartData.push(newCandle);
                }
                candleSeries.setData(chartData);

                // Update Order Book placeholders
                updateOrderBook(newPrice);
            }
        } catch (e) {
            // addLog(`[WS] ${event.data}`);
        }
    };

    ws.onclose = () => {
        addLog('WebSocket connection closed.', 'text-red-400');
        document.getElementById('status-indicator').innerHTML = `
            <div class="w-3 h-3 bg-red-500 rounded-full"></div>
            Disconnected
        `;
    };

    // --- UI Logic ---
    const addLog = (message, colorClass = 'text-slate-300') => {
        const logsContainer = document.getElementById('logs');
        const div = document.createElement('div');
        div.className = colorClass;
        div.textContent = `[${new Date().toLocaleTimeString()}] ${message}`;
        logsContainer.appendChild(div);
        logsContainer.scrollTop = logsContainer.scrollHeight;
    };

    const updateOrderBook = (midPrice) => {
        const bids = document.getElementById('bids-list');
        const asks = document.getElementById('asks-list');
        bids.innerHTML = '';
        asks.innerHTML = '';

        for (let i = 1; i <= 5; i++) {
            const bidPrice = midPrice - (i * 0.5);
            const askPrice = midPrice + (i * 0.5);
            const bidLi = `<li class="flex justify-between"><span>${bidPrice.toFixed(2)}</span> <span class="text-slate-500">${(Math.random() * 10).toFixed(2)}</span></li>`;
            const askLi = `<li class="flex justify-between"><span>${askPrice.toFixed(2)}</span> <span class="text-slate-500">${(Math.random() * 10).toFixed(2)}</span></li>`;
            bids.innerHTML += bidLi;
            asks.innerHTML += askLi;
        }
    };

    // Order Submission
    document.getElementById('submit-order').addEventListener('click', async () => {
        const order = {
            instrument: document.getElementById('instrument').value,
            side: document.getElementById('buy-btn').classList.contains('bg-green-700') ? 'BUY' : 'SELL',
            quantity: parseFloat(document.getElementById('quantity').value),
            price: parseFloat(document.getElementById('price').value) || null,
            order_type: document.getElementById('order-type').value,
            duration_seconds: 30 // Default for TWAP/VWAP
        };

        addLog(`Submitting ${order.order_type} ${order.side} ${order.quantity} ${order.instrument}...`);

        try {
            const response = await fetch('/v1/order', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify(order)
            });
            const result = await response.json();
            if (response.ok) {
                addLog(`Order Accepted: ${order.order_type}`, 'text-green-400');
            } else {
                addLog(`Order Rejected: ${result.detail}`, 'text-red-400');
            }
        } catch (error) {
            addLog(`Error: ${error.message}`, 'text-red-400');
        }
    });

    // Side selection toggle
    document.getElementById('buy-btn').addEventListener('click', () => {
        document.getElementById('buy-btn').classList.add('bg-green-700', 'ring-2', 'ring-white');
        document.getElementById('sell-btn').classList.remove('bg-red-700', 'ring-2', 'ring-white');
        document.getElementById('buy-btn').classList.remove('bg-green-600');
        document.getElementById('sell-btn').classList.add('bg-red-600');
    });

    document.getElementById('sell-btn').addEventListener('click', () => {
        document.getElementById('sell-btn').classList.add('bg-red-700', 'ring-2', 'ring-white');
        document.getElementById('buy-btn').classList.remove('bg-green-700', 'ring-2', 'ring-white');
        document.getElementById('sell-btn').classList.remove('bg-red-600');
        document.getElementById('buy-btn').classList.add('bg-green-600');
    });

    // Kill Switch
    document.getElementById('kill-switch-btn').addEventListener('click', async () => {
        if (!confirm('ACTIVATE EMERGENCY KILL-SWITCH?')) return;
        try {
            await fetch('/v1/kill-switch?action=ACTIVATE', { method: 'POST' });
            addLog('!!! KILL-SWITCH ACTIVATED !!!', 'text-red-500 font-bold');
        } catch (error) {
            addLog(`Kill-switch failed: ${error.message}`, 'text-red-400');
        }
    });

    const updatePositions = async () => {
        try {
            const response = await fetch('/v1/positions');
            const data = await response.json();
            document.getElementById('balance-info').textContent = `USD: $${data.USD.toFixed(2)} | ETH: ${data.ETH.toFixed(4)}`;

            const positionsList = document.getElementById('positions-list');
            positionsList.innerHTML = '';
            if (data.ETH !== 0) {
                const row = `
                    <tr class="border-b border-slate-800">
                        <td class="py-2">ETH/USDT</td>
                        <td class="${data.ETH > 0 ? 'text-green-400' : 'text-red-400'}">${data.ETH > 0 ? 'LONG' : 'SHORT'}</td>
                        <td>${Math.abs(data.ETH).toFixed(4)}</td>
                        <td>$${(data.USD_PRICE || 2500).toFixed(2)}</td>
                    </tr>
                `;
                positionsList.innerHTML = row;
            }
        } catch (error) {}
    };

    updatePositions();
    setInterval(updatePositions, 5000);
});
