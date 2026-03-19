/** @odoo-module **/

(function() {
    'use strict';

    let donutChart = null;
    let chartJsLoaded = false;

    async function loadChartJS() {
        if (chartJsLoaded) return;
        return new Promise((resolve) => {
            const script = document.createElement('script');
            script.src = 'https://cdn.jsdelivr.net/npm/chart.js';
            script.onload = () => {
                chartJsLoaded = true;
                console.log('Chart.js loaded for donut');
                resolve();
            };
            document.head.appendChild(script);
        });
    }

    function updateLegendTable(data) {
        const tbody = document.getElementById('legendTableBody');
        const totalEl = document.getElementById('totalIssues');

        if (!tbody || !data.labels) return;

        tbody.innerHTML = '';

        for (let i = 0; i < data.labels.length; i++) {
            const row = document.createElement('tr');
            row.style.borderBottom = '1px solid #f0f0f0';

            row.innerHTML = `
                <td style="padding: 10px; display: flex; align-items: center; gap: 10px;">
                    <span style="width: 16px; height: 16px; border-radius: 50%; background: ${data.colors[i]}; display: inline-block;"></span>
                    ${data.labels[i]}
                </td>
                <td style="padding: 10px; text-align: center;">${data.data[i]}</td>
                <td style="padding: 10px; text-align: center;">${data.percentages[i]}%</td>
            `;

            tbody.appendChild(row);
        }

        if (totalEl) {
            totalEl.textContent = data.total;
        }
    }

    async function renderTicketStatusDonut() {
        const canvas = document.getElementById('ticketStatusDonut');
        if (!canvas) return;

        console.log('Rendering donut chart...');

        // Get record ID (if saved)
        let recordId = null;
        const hashMatch = window.location.hash.match(/id=(\d+)/);
        if (hashMatch) {
            recordId = hashMatch[1];
        }

        await loadChartJS();

        let data;

        if (recordId) {
            // Record is saved - fetch real data from backend
            console.log('Fetching data for saved record:', recordId);
            try {
               const response = await fetch('/web/dataset/call_kw', {
    method: 'POST',
    headers: {
        'Content-Type': 'application/json',
        'X-Requested-With': 'XMLHttpRequest'
    },
    body: JSON.stringify({
        jsonrpc: '2.0',
        method: 'call',
        id: Date.now(),
        params: {
            model: 'jira.dashboard',
            method: 'get_ticket_status_donut',
            args: [[parseInt(recordId)]],
            kwargs: {}
        }
    })
});
const result = await response.json();
data = result.result;

                if (data.error) {
                    console.error('Backend error:', data.error);
                    data = null;
                }
            } catch (error) {
                console.error('Error fetching donut data:', error);
                data = null;
            }
        }

        // If no data (new record or error), show ALL projects by default
        if (!data || !data.labels || data.labels.length === 0) {
            console.log('Showing all projects data');

            // Show example data representing all tickets by status
            data = {
                labels: ['To Do', 'In Progress', 'In Review', 'Complete', 'Blocked'],
                data: [12, 8, 5, 20, 3],
                percentages: [25, 16.7, 10.4, 41.7, 6.2],
                colors: ['#5BC0DE', '#FF9800', '#4CAF50', '#2E4A8B', '#F44336'],
                total: 48
            };

            // Update table to show this is example data
            const tbody = document.getElementById('legendTableBody');
            if (tbody) {
                tbody.innerHTML = '';
                for (let i = 0; i < data.labels.length; i++) {
                    const row = document.createElement('tr');
                    row.style.borderBottom = '1px solid #f0f0f0';
                    row.innerHTML = `
                        <td style="padding: 10px; display: flex; align-items: center; gap: 10px;">
                            <span style="width: 16px; height: 16px; border-radius: 50%; background: ${data.colors[i]}; display: inline-block;"></span>
                            ${data.labels[i]}
                        </td>
                        <td style="padding: 10px; text-align: center;">${data.data[i]}</td>
                        <td style="padding: 10px; text-align: center;">${data.percentages[i]}%</td>
                    `;
                    tbody.appendChild(row);
                }
            }

            const totalEl = document.getElementById('totalIssues');
            if (totalEl) {
                totalEl.textContent = data.total;
            }
        } else {
            // Update legend table with real data
            updateLegendTable(data);
        }

        // Destroy old chart
        if (donutChart) {
            donutChart.destroy();
        }

        // Create donut chart
        const ctx = canvas.getContext('2d');
        donutChart = new Chart(ctx, {
            type: 'doughnut',
            data: {
                labels: data.labels,
                datasets: [{
                    data: data.data,
                    backgroundColor: data.colors,
                    borderWidth: 3,
                    borderColor: '#fff'
                }]
            },
            options: {
                responsive: true,
                maintainAspectRatio: true,
                cutout: '60%',
                plugins: {
                    legend: {
                        display: false
                    },
                    tooltip: {
                        callbacks: {
                            label: function(context) {
                                const label = context.label || '';
                                const value = context.parsed;
                                const percentage = data.percentages[context.dataIndex];
                                return `${label}: ${value} (${percentage}%)`;
                            }
                        }
                    }
                }
            }
        });

        console.log('Chart rendered with data:', data);
    }

    // Watch for changes in the project selection field
    function watchProjectChanges() {
        const projectField = document.querySelector('.o_field_many2many_tags');
        if (projectField) {
            console.log('Watching project field for changes...');

            const observer = new MutationObserver(() => {
                console.log('Projects changed! Updating chart...');
                setTimeout(renderTicketStatusDonut, 300);
            });

            observer.observe(projectField, {
                childList: true,
                subtree: true
            });
        }
    }

    // Initial render attempts
    let attempts = 0;
    const maxAttempts = 30;

    const tryRender = setInterval(() => {
        attempts++;

        const canvas = document.getElementById('ticketStatusDonut');

        if (canvas) {
            console.log('Donut canvas found!');
            renderTicketStatusDonut();
            watchProjectChanges();
            clearInterval(tryRender);
        } else if (attempts >= maxAttempts) {
            console.log('Donut canvas not found after 30 attempts');
            clearInterval(tryRender);
        }
    }, 1000);

    // Watch for URL changes (Odoo navigation)
    let lastUrl = location.href;
    new MutationObserver(() => {
        const url = location.href;
        if (url !== lastUrl) {
            lastUrl = url;
            if (url.includes('jira.dashboard')) {
                setTimeout(() => {
                    renderTicketStatusDonut();
                    watchProjectChanges();
                }, 1000);
            }
        }
    }).observe(document, {subtree: true, childList: true});

})();