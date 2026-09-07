document.addEventListener('DOMContentLoaded', () => {
    // DOM Elements
    const videoFeed = document.getElementById('videoFeed');
    const noStreamOverlay = document.getElementById('noStreamOverlay');
    const statusDot = document.getElementById('statusDot');
    const connStatus = document.getElementById('connStatus');
    const fpsVal = document.getElementById('fpsVal');
    const detectorVal = document.getElementById('detectorVal');

    const directionBox = document.getElementById('directionBox');
    const directionIcon = document.getElementById('directionIcon');
    const directionLabel = document.getElementById('directionLabel');

    const barLeft = document.getElementById('barLeft');
    const barCenter = document.getElementById('barCenter');
    const barRight = document.getElementById('barRight');
    const scoreLeft = document.getElementById('scoreLeft');
    const scoreCenter = document.getElementById('scoreCenter');
    const scoreRight = document.getElementById('scoreRight');

    // Initialize Chart.js Path Plot
    const ctx = document.getElementById('pathChart').getContext('2d');
    const pathChart = new Chart(ctx, {
        type: 'scatter',
        data: {
            datasets: [{
                label: 'Estimated Path (m)',
                data: [{x: 0, y: 0}],
                showLine: true,
                borderColor: '#3b82f6',
                backgroundColor: '#60a5fa',
                borderWidth: 2,
                pointRadius: 4,
                pointHoverRadius: 6,
            }]
        },
        options: {
            responsive: true,
            maintainAspectRatio: false,
            animation: false,
            scales: {
                x: {
                    type: 'linear',
                    position: 'bottom',
                    grid: { color: '#1e293b' },
                    ticks: { color: '#94a3b8' },
                    title: { display: true, text: 'X (meters)', color: '#94a3b8' }
                },
                y: {
                    type: 'linear',
                    grid: { color: '#1e293b' },
                    ticks: { color: '#94a3b8' },
                    title: { display: true, text: 'Y (meters)', color: '#94a3b8' }
                }
            },
            plugins: {
                legend: { display: false }
            }
        }
    });

    let ws = null;
    let reconnectDelay = 1000;

    function connectWebSocket() {
        const protocol = window.location.protocol === 'https:' ? 'wss:' : 'ws:';
        const wsUrl = `${protocol}//${window.location.host}/ws/dashboard`;

        connStatus.textContent = 'CONNECTING...';
        connStatus.className = 'value yellow';
        statusDot.className = 'pulse-dot';

        ws = new WebSocket(wsUrl);

        ws.onopen = () => {
            connStatus.textContent = 'CONNECTED';
            connStatus.className = 'value green';
            statusDot.className = 'pulse-dot active';
            noStreamOverlay.style.display = 'none';
            reconnectDelay = 1000;
        };

        ws.onmessage = (event) => {
            try {
                const data = JSON.parse(event.data);
                updateDashboard(data);
            } catch (err) {
                console.error("Error parsing WS frame payload:", err);
            }
        };

        ws.onclose = () => {
            connStatus.textContent = 'DISCONNECTED';
            connStatus.className = 'value red';
            statusDot.className = 'pulse-dot error';
            noStreamOverlay.style.display = 'flex';
            noStreamOverlay.querySelector('span').textContent = `DISCONNECTED - RECONNECTING IN ${reconnectDelay / 1000}s...`;

            setTimeout(connectWebSocket, reconnectDelay);
            reconnectDelay = Math.min(reconnectDelay * 1.5, 10000);
        };

        ws.onerror = (err) => {
            console.error("WebSocket error:", err);
            ws.close();
        };
    }

    function updateDashboard(data) {
        // 1. Update Video Frame
        if (data.frame_b64) {
            videoFeed.src = 'data:image/jpeg;base64,' + data.frame_b64;
        }

        // 2. Update Telemetry
        if (data.fps !== undefined) {
            fpsVal.textContent = data.fps.toFixed(1);
        }
        if (data.detector) {
            detectorVal.textContent = data.detector.toUpperCase();
        }

        // 3. Update Giant Directional Indicator
        const decision = (data.decision || 'STOP').toUpperCase();
        updateIndicator(decision);

        // 4. Update Clearance Region Bars
        if (data.region_scores) {
            updateBar(barLeft, scoreLeft, data.region_scores.left);
            updateBar(barCenter, scoreCenter, data.region_scores.center);
            updateBar(barRight, scoreRight, data.region_scores.right);
        }

        // 5. Update Path Plot
        if (data.path_point && data.path_point.path) {
            const formattedData = data.path_point.path.map(pt => ({ x: pt[0], y: pt[1] }));
            pathChart.data.datasets[0].data = formattedData;
            pathChart.update('none'); // Update without animation for low latency
        }
    }

    function updateIndicator(decision) {
        directionBox.className = 'direction-box';

        switch(decision) {
            case 'FORWARD':
                directionBox.classList.add('state-forward');
                directionIcon.textContent = '↑';
                directionLabel.textContent = 'FORWARD';
                break;
            case 'LEFT':
                directionBox.classList.add('state-left');
                directionIcon.textContent = '↖';
                directionLabel.textContent = 'TURN LEFT';
                break;
            case 'RIGHT':
                directionBox.classList.add('state-right');
                directionIcon.textContent = '↗';
                directionLabel.textContent = 'TURN RIGHT';
                break;
            case 'STOP':
            default:
                directionBox.classList.add('state-stop');
                directionIcon.textContent = '🛑';
                directionLabel.textContent = 'STOP';
                break;
        }
    }

    function updateBar(barElem, textElem, score) {
        const pct = Math.round((score || 0) * 100);
        textElem.textContent = `${pct}%`;
        barElem.style.width = `${pct}%`;

        if (pct > 65) {
            barElem.style.backgroundColor = 'var(--color-red)';
        } else if (pct > 35) {
            barElem.style.backgroundColor = 'var(--color-amber)';
        } else {
            barElem.style.backgroundColor = 'var(--color-green)';
        }
    }

    // Connect on load
    connectWebSocket();
});
