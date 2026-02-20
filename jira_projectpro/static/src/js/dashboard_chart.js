/** @odoo-module **/

(function() {
    'use strict';

    let chartInstance = null;
    let chartJsLoaded = false;

    async function loadChartJS() {
        if (chartJsLoaded) return;

        return new Promise((resolve) => {
            const script = document.createElement('script');
            script.src = 'https://cdn.jsdelivr.net/npm/chart.js';
            script.onload = () => {
                chartJsLoaded = true;
                console.log('Chart.js loaded');
                resolve();
            };
            document.head.appendChild(script);
        });
    }

    async function getProjectDataFromDOM() {
        /**
         * Get selected projects directly from the form
         * This works even before saving!
         */
        const projectTags = document.querySelectorAll('.o_field_many2many_tags .badge');
        const projects = [];

        for (const tag of projectTags) {
            const projectName = tag.textContent.trim().replace('×', '').trim();
            if (projectName) {
                projects.push({
                    name: projectName,
                    completion: Math.random() * 100  // Mock data for now
                });
            }
        }

        return projects;
    }

    async function renderDashboardChart() {
        const canvas = document.getElementById('projectsPieChart');
        if (!canvas) return;

        console.log('Rendering chart...');

        // Load Chart.js
        await loadChartJS();

        // Get record ID (if saved)
        let recordId = null;
        const hashMatch = window.location.hash.match(/id=(\d+)/);
        if (hashMatch) {
            recordId = hashMatch[1];
        }

        let data;

        if (recordId) {
            // Record is saved - fetch from backend
            console.log('Fetching data for saved record:', recordId);
            try {
                const response = await fetch(`/jira/dashboard/chart_data/${recordId}`);
                data = await response.json();
            } catch (error) {
                console.error('Error fetching data:', error);
                data = { labels: [], data: [], colors: [] };
            }
        } else {
            // New record - get data from DOM
            console.log('New record - getting data from form');
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

        console.log('Chart data:', data);

        if (!data.labels || data.labels.length === 0) {
            const ctx = canvas.getContext('2d');
            ctx.clearRect(0, 0, canvas.width, canvas.height);
            ctx.font = '16px Arial';
            ctx.textAlign = 'center';
            ctx.fillStyle = '#666';
            ctx.fillText('No projects to display', canvas.width / 2, canvas.height / 2);
            return;
        }

        // Destroy old chart
        if (chartInstance) {
            chartInstance.destroy();
            chartInstance = null;
        }

        // Create chart
        const ctx = canvas.getContext('2d');
        chartInstance = new Chart(ctx, {
            type: 'pie',
            data: {
                labels: data.labels,
                datasets: [{
                    data: data.data,
                    backgroundColor: data.colors,
                    borderWidth: 2,
                    borderColor: '#fff'
                }]
            },
            options: {
                responsive: true,
                maintainAspectRatio: false,
                plugins: {
                    legend: {
                        position: 'bottom',
                        labels: {
                            padding: 15,
                            font: { size: 12 }
                        }
                    },
                    tooltip: {
                        callbacks: {
                            label: function(context) {
                                return context.label + ': ' + context.parsed.toFixed(2) + '%';
                            }
                        }
                    }
                }
            }
        });

        console.log('Chart rendered successfully!');
    }

    // Watch for changes in the many2many field
    function watchProjectChanges() {
        const projectField = document.querySelector('.o_field_many2many_tags');
        if (projectField) {
            const observer = new MutationObserver(() => {
                console.log('Projects changed, updating chart...');
                setTimeout(renderDashboardChart, 500);
            });

            observer.observe(projectField, {
                childList: true,
                subtree: true
            });

            console.log('Watching for project changes');
        }
    }

    // Initial render attempts
    let attempts = 0;
    const maxAttempts = 30;

    const tryRender = setInterval(() => {
        attempts++;

        const canvas = document.getElementById('projectsPieChart');

        if (canvas) {
            console.log('Canvas found! Rendering...');
            renderDashboardChart();
            watchProjectChanges();
            clearInterval(tryRender);
        } else if (attempts >= maxAttempts) {
            console.log('Max attempts reached, canvas not found');
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
                    renderDashboardChart();
                    watchProjectChanges();
                }, 1000);
            }
        }
    }).observe(document, {subtree: true, childList: true});

})();