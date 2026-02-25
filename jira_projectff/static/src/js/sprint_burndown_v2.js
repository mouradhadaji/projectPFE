/** @odoo-module **/

console.log('🚀 SPRINT BURNDOWN JS LOADED!');

(function() {
    'use strict';

    let burndownChart = null;
    let chartJsLoaded = false;

    async function loadChartJS() {
        if (chartJsLoaded) return;
        return new Promise((resolve) => {
            const script = document.createElement('script');
            script.src = 'https://cdn.jsdelivr.net/npm/chart.js';
            script.onload = () => {
                chartJsLoaded = true;
                console.log('✅ Chart.js loaded for burndown');
                resolve();
            };
            document.head.appendChild(script);
        });
    }

    async function loadSprintOptions() {
        const selector = document.getElementById('sprintSelector');
        if (!selector) {
            console.log('❌ Sprint selector not found');
            return;
        }

        console.log('🔄 Loading ALL sprints...');

        try {
            // Fetch ALL sprints (no project filter)
            const response = await fetch('/web/dataset/call_kw', {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json',
                },
                body: JSON.stringify({
                    jsonrpc: '2.0',
                    method: 'call',
                    params: {
                        model: 'jira.sprint',
                        method: 'search_read',
                        args: [[]],  // Empty domain = ALL sprints
                        kwargs: {
                            fields: ['id', 'name', 'project_id'],
                            order: 'name asc'
                        }
                    },
                    id: new Date().getTime()
                })
            });

            const result = await response.json();
            console.log('📊 Full API Response:', result);

            if (result.error) {
                console.error('❌ API Error:', result.error);
                return;
            }

            const sprints = result.result || [];
            console.log(`✅ Found ${sprints.length} sprints:`, sprints);

            // Clear and populate selector
            selector.innerHTML = '<option value="">Sélectionnez un sprint...</option>';

            sprints.forEach(sprint => {
                const option = document.createElement('option');
                option.value = sprint.id;
                // Show project name if available
                const projectName = sprint.project_id ? ` (${sprint.project_id[1]})` : '';
                option.textContent = sprint.name + projectName;
                selector.appendChild(option);
            });

            console.log('✅ Sprints loaded into dropdown');

        } catch (error) {
            console.error('❌ Error loading sprints:', error);
        }
    }

    async function renderBurndownChart(sprintId) {
        const canvas = document.getElementById('sprintBurndownChart');
        if (!canvas) {
            console.log('❌ Canvas not found');
            return;
        }

        if (!sprintId) {
            console.log('⚠️ No sprint ID');
            return;
        }

        console.log('📈 Loading burndown for sprint:', sprintId);

        await loadChartJS();

        try {
            const response = await fetch(`/jira/sprint/burndown_data/${sprintId}`);
            const data = await response.json();

            console.log('📊 Burndown data received:', data);

            if (data.error) {
                console.error('❌ Backend error:', data.error);
                const ctx = canvas.getContext('2d');
                if (burndownChart) burndownChart.destroy();
                ctx.clearRect(0, 0, canvas.width, canvas.height);
                ctx.font = '16px Arial';
                ctx.textAlign = 'center';
                ctx.fillStyle = '#d9534f';
                ctx.fillText(data.error, canvas.width / 2, canvas.height / 2);
                return;
            }

            // Destroy old chart
            if (burndownChart) {
                burndownChart.destroy();
            }

            // Create burndown chart
            const ctx = canvas.getContext('2d');
            burndownChart = new Chart(ctx, {
                type: 'line',
                data: {
                    labels: data.labels,
                    datasets: [
                        {
                            label: 'Guideline',
                            data: data.guideline,
                            borderColor: '#999',
                            backgroundColor: 'transparent',
                            borderWidth: 2,
                            pointRadius: 0,
                            tension: 0
                        },
                        {
                            label: 'Remaining Values',
                            data: data.remaining_values,
                            borderColor: '#d9534f',
                            backgroundColor: 'transparent',
                            borderWidth: 3,
                            pointRadius: 4,
                            pointBackgroundColor: '#d9534f',
                            stepped: 'before',
                            tension: 0
                        }
                    ]
                },
                options: {
                    responsive: true,
                    maintainAspectRatio: false,
                    scales: {
                        y: {
                            beginAtZero: true,
                            title: {
                                display: true,
                                text: 'Story Points',
                                font: { size: 14 }
                            },
                            grid: {
                                color: 'rgba(0, 0, 0, 0.05)'
                            }
                        },
                        x: {
                            title: {
                                display: true,
                                text: 'Time',
                                font: { size: 14 }
                            },
                            grid: {
                                color: function(context) {
                                    const index = context.index;
                                    if (data.non_working_days && data.non_working_days[index] === 1) {
                                        return 'rgba(200, 200, 200, 0.3)';
                                    }
                                    return 'rgba(0, 0, 0, 0.05)';
                                }
                            }
                        }
                    },
                    plugins: {
                        legend: {
                            position: 'top',
                            align: 'end',
                            labels: {
                                usePointStyle: true,
                                padding: 15,
                                font: { size: 12 }
                            }
                        },
                        tooltip: {
                            callbacks: {
                                label: function(context) {
                                    return context.dataset.label + ': ' +
                                           context.parsed.y.toFixed(1) + ' points';
                                }
                            }
                        }
                    }
                }
            });

            console.log('✅ Burndown chart rendered successfully!');

        } catch (error) {
            console.error('❌ Error rendering burndown:', error);
        }
    }

    // Initialize
    let attempts = 0;
    const maxAttempts = 30;

    const tryInit = setInterval(() => {
        attempts++;
        console.log(`🔍 Attempt ${attempts}: Looking for burndown elements...`);

        const selector = document.getElementById('sprintSelector');
        const canvas = document.getElementById('sprintBurndownChart');

        if (selector && canvas) {
            console.log('✅ Burndown elements found!');

            // Load sprint options immediately
            loadSprintOptions();

            // Listen for sprint selection
            selector.addEventListener('change', (e) => {
                const sprintId = e.target.value;
                console.log('🎯 Sprint selected:', sprintId);
                if (sprintId) {
                    renderBurndownChart(sprintId);
                }
            });

            clearInterval(tryInit);
        } else {
            if (!selector) console.log('   ❌ Selector not found');
            if (!canvas) console.log('   ❌ Canvas not found');

            if (attempts >= maxAttempts) {
                console.log('❌ Max attempts reached - burndown elements not found');
                clearInterval(tryInit);
            }
        }
    }, 1000);

})();