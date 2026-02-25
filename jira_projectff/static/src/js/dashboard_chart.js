/** @odoo-module **/

(function() {
    'use strict';

    let chartInstance = null;
    let chartJsLoaded = false;

    // ─── HELPER: Load Chart.js ──────────────────────────────
    async function loadChartJS() {
        if (chartJsLoaded || window.Chart) {
            chartJsLoaded = true;
            return;
        }
        return new Promise((resolve) => {
            const script = document.createElement('script');
            script.src = 'https://cdn.jsdelivr.net/npm/chart.js';
            script.onload = () => {
                chartJsLoaded = true;
                console.log('✅ Chart.js loaded');
                resolve();
            };
            document.head.appendChild(script);
        });
    }

    // ─── HELPER: RPC Call ───────────────────────────────────
    async function rpcCall(model, method, args) {
        const response = await fetch('/web/dataset/call_kw', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({
                jsonrpc: '2.0', method: 'call',
                params: { model, method, args, kwargs: {} }
            })
        });
        const data = await response.json();
        if (data.error) throw new Error(data.error.message);
        return data.result;
    }

    // ─── HELPER: Get Record ID ──────────────────────────────
    function getRecordIdFromURL() {
        // Checks both Odoo 16+ (pathname) and Odoo 15- (hash) formats
        const pathMatch = window.location.pathname.match(/\/(\d+)(?:\/|$)/);
        if (pathMatch) return parseInt(pathMatch[1]);

        const hashMatch = window.location.hash.match(/id=(\d+)/);
        if (hashMatch) return parseInt(hashMatch[1]);

        return null;
    }

    // ─── DATA EXTRACATION ───────────────────────────────────
    async function getProjectDataFromDOM() {
        const projectTags = document.querySelectorAll('.o_field_many2many_tags .badge');
        const projects = [];
        for (const tag of projectTags) {
            const projectName = tag.textContent.trim().replace('×', '').trim();
            if (projectName) {
                projects.push({ name: projectName, completion: Math.random() * 100 });
            }
        }
        return projects;
    }

    // ─── RENDER: Dashboard Pie Chart ────────────────────────
    async function renderDashboardChart() {
        const canvas = document.getElementById('projectsPieChart');
        if (!canvas) return;

        await loadChartJS();
        const recordId = getRecordIdFromURL();
        let data;

        if (recordId) {
            try {
                const response = await fetch(`/jira/dashboard/chart_data/${recordId}`);
                data = await response.json();
            } catch (error) {
                console.error('❌ Error fetching data:', error);
                data = { labels: [], data: [], colors: [] };
            }
        } else {
            const projects = await getProjectDataFromDOM();
            if (projects.length === 0) {
                const ctx = canvas.getContext('2d');
                ctx.clearRect(0, 0, canvas.width, canvas.height);
                ctx.font = '16px Arial';
                ctx.textAlign = 'center';
                ctx.fillStyle = '#666';
                ctx.fillText('Select projects to see the chart', canvas.width / 2, canvas.height / 2);
                return;
            }
            data = {
                labels: projects.map(p => p.name),
                data: projects.map(p => p.completion),
                colors: ['#FF6384', '#36A2EB', '#FFCE56', '#4BC0C0', '#9966FF', '#FF9F40']
            };
        }

        if (!data.labels || data.labels.length === 0) {
            const ctx = canvas.getContext('2d');
            ctx.clearRect(0, 0, canvas.width, canvas.height);
            ctx.font = '16px Arial';
            ctx.textAlign = 'center';
            ctx.fillStyle = '#666';
            ctx.fillText('No projects to display', canvas.width / 2, canvas.height / 2);
            return;
        }

        if (chartInstance) { chartInstance.destroy(); }

        const ctx = canvas.getContext('2d');
        chartInstance = new Chart(ctx, {
            type: 'pie',
            data: {
                labels: data.labels,
                datasets: [{ data: data.data, backgroundColor: data.colors, borderWidth: 2, borderColor: '#fff' }]
            },
            options: {
                responsive: true,
                maintainAspectRatio: false,
                plugins: {
                    legend: { position: 'bottom', labels: { padding: 15, font: { size: 12 } } },
                    tooltip: { callbacks: { label: (context) => context.label + ': ' + context.parsed.toFixed(2) + '%' } }
                }
            }
        });
    }

    // ─── RENDER: Velocity Chart ─────────────────────────────
    async function renderVelocityChart(recordId) {
        const canvas = document.getElementById('teamVelocityChart');
        if (!canvas) return;

        await loadChartJS();

        try {
            const data = await rpcCall('jira.dashboard', 'get_team_velocity_data', [[parseInt(recordId)]]);

            if (!data.labels || data.labels.length === 0) {
                const ctx = canvas.getContext('2d');
                ctx.clearRect(0, 0, canvas.width, canvas.height);
                ctx.font = '16px Arial';
                ctx.textAlign = 'center';
                ctx.fillStyle = '#666';
                ctx.fillText('No sprint data available. Please select a project with completed sprints.', canvas.width / 2, canvas.height / 2);
                return;
            }

            const avgEl = document.getElementById('avgVelocity');
            const subtitleEl = document.getElementById('velocitySubtitle');
            if (avgEl) avgEl.textContent = data.avg_velocity || 0;
            if (subtitleEl) subtitleEl.textContent = `Calculated based on the last ${data.sprint_count || 0} sprints.`;

            const avgLine = data.labels.map(() => data.avg_velocity);

            if (window.velocityChart) { window.velocityChart.destroy(); }

            const ctx = canvas.getContext('2d');
            window.velocityChart = new Chart(ctx, {
                type: 'bar',
                data: {
                    labels: data.labels,
                    datasets: [
                        { label: 'Initial Scope', data: data.initial_scope, backgroundColor: '#4472C4', borderRadius: 4, barThickness: 40 },
                        { label: 'Final Scope', data: data.final_scope, backgroundColor: '#ED7D31', borderRadius: 4, barThickness: 40 },
                        { label: 'Completed', data: data.completed, backgroundColor: '#70AD47', borderRadius: 4, barThickness: 40 },
                        { label: 'Average Velocity', data: avgLine, type: 'line', borderColor: '#dc3545', borderWidth: 3, pointRadius: 0, fill: false, tension: 0.4 }
                    ]
                },
                options: {
                    responsive: true, maintainAspectRatio: false,
                    plugins: { legend: { display: false }, tooltip: { callbacks: { label: (context) => context.dataset.label + ': ' + context.parsed.y + ' pts' } } },
                    scales: {
                        x: { title: { display: true, text: 'Sprints', color: '#666', font: { size: 12, weight: 'bold' } }, grid: { display: false } },
                        y: { title: { display: true, text: 'Story Points', color: '#666', font: { size: 12, weight: 'bold' } }, beginAtZero: true, grid: { color: '#e0e0e0' } }
                    }
                }
            });
        } catch (error) {
            console.error('❌ Error rendering velocity chart:', error);
        }
    }

    // ─── EVENT LISTENERS ────────────────────────────────────
    function watchProjectFieldChange() {
        const projectField = document.querySelector('select[name="project_id"]');
        if (projectField && !projectField.dataset.listenerAttached) {
            projectField.addEventListener('change', function() {
                setTimeout(() => {
                    const recordId = getRecordIdFromURL();
                    if (recordId) renderVelocityChart(recordId);
                }, 1000);
            });
            projectField.dataset.listenerAttached = "true"; // Prevent duplicate listeners
        }
    }

    function triggerRenders() {
        renderDashboardChart();
        watchProjectFieldChange(); // Fixed function name
        const recordId = getRecordIdFromURL();
        if (recordId) renderVelocityChart(recordId);
    }

    // Initialize via Interval (since Odoo SPA routing doesn't always trigger DOMContentLoaded)
    let attempts = 0;
    const maxAttempts = 30;
    const tryRender = setInterval(() => {
        attempts++;
        if (document.getElementById('projectsPieChart') || document.getElementById('teamVelocityChart')) {
            triggerRenders();
            clearInterval(tryRender);
        } else if (attempts >= maxAttempts) {
            clearInterval(tryRender);
        }
    }, 1000);

    // Watch URL changes for Odoo SPA routing
    let lastUrl = location.href;
    new MutationObserver(() => {
        const url = location.href;
        if (url !== lastUrl) {
            lastUrl = url;
            // Adjust this condition to match your actual Odoo route/action string
            if (url.includes('jira.dashboard') || url.includes('id=')) {
                setTimeout(triggerRenders, 1000);
            }
        }
    }).observe(document, { subtree: true, childList: true });

})();