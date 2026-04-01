/** @odoo-module **/

// ... (el import wel patch elli 3andek l'fou9)

    renderChart(canvas, type, data) {
        // Nams7ou el chart el 9dima ken mawjouda bech ma dakhalech el alwen fi b3adh'ha
        if (canvas.chart) {
            canvas.chart.destroy();
        }

        let config = {};

        // --- HNA TZID EL CONFIG EL JDIDA ---
        if (type === 'burnup') {
            config = {
                type: 'line',
                data: {
                    labels: data.labels,
                    datasets: [
                        {
                            label: 'Total Scope',
                            data: data.scope,
                            borderColor: '#dc3545', // A7mer lel Scope
                            borderDash: [5, 5],
                            fill: false,
                            stepped: true, // Bej tji Linear Step
                        },
                        {
                            label: 'Completed',
                            data: data.completed,
                            borderColor: '#28a745', // Akhdher lel khedma elli tmet
                            backgroundColor: 'rgba(40, 167, 69, 0.1)',
                            fill: true,
                            stepped: true,
                        }
                    ]
                },
                options: {
                    responsive: true,
                    maintainAspectRatio: false,
                    scales: {
                        y: { beginAtZero: true, ticks: { stepSize: 1 } }
                    }
                }
            };
        } else {
            // El charts el 9dom (Status, Type, Priority)
            const chartTypes = { status: 'doughnut', type: 'bar', priority: 'bar' };
            config = {
                type: chartTypes[type],
                data: {
                    labels: data.labels,
                    datasets: [{
                        label: 'Tickets',
                        data: data.data,
                        backgroundColor: data.colors,
                    }]
                },
                options: {
                    responsive: true,
                    indexAxis: type === 'priority' ? 'y' : 'x',
                }
            };
        }

        // Njaddedou el chart fil canvas
        canvas.chart = new Chart(canvas, config);
    }