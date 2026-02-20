/** @odoo-module **/

console.log('🚀 SPRINT BURNDOWN PRO LOADED!');

(function() {
    'use strict';

    let burndownChart = null;

    function waitForChartJS() {
        return new Promise((resolve) => {
            if (typeof Chart !== 'undefined') {
                resolve();
                return;
            }
            const checkInterval = setInterval(() => {
                if (typeof Chart !== 'undefined') {
                    clearInterval(checkInterval);
                    resolve();
                }
            }, 100);
        });
    }

    async function loadSprintOptions() {
        const selector = document.getElementById('sprintSelector');
        if (!selector) return;

        try {
            const response = await fetch('/web/dataset/call_kw', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({
                    jsonrpc: '2.0',
                    method: 'call',
                    params: {
                        model: 'jira.sprint',
                        method: 'search_read',
                        args: [[]],
                        kwargs: {
                            fields: ['id', 'name', 'project_id', 'start_date', 'end_date'],
                            order: 'start_date desc',
                            limit: 50
                        }
                    },
                    id: new Date().getTime()
                })
            });

            const result = await response.json();
            const sprints = result.result || [];

            selector.innerHTML = '<option value="">Choisissez un sprint...</option>';

            sprints.forEach(sprint => {
                const option = document.createElement('option');
                option.value = sprint.id;
                const projectName = sprint.project_id ? ` - ${sprint.project_id[1]}` : '';
                const dates = sprint.start_date && sprint.end_date
                    ? ` (${sprint.start_date} → ${sprint.end_date})`
                    : '';
                option.textContent = sprint.name + projectName + dates;
                selector.appendChild(option);
            });

            // Style hover effect
            selector.addEventListener('mouseover', () => {
                selector.style.borderColor = '#4682b4';
            });
            selector.addEventListener('mouseout', () => {
                selector.style.borderColor = '#e0e0e0';
            });

        } catch (error) {
            console.error('❌ Error loading sprints:', error);
        }
    }

    async function renderBurndownChart(sprintId) {
        const canvas = document.getElementById('sprintBurndownChart');
        if (!canvas || !sprintId) return;

        await waitForChartJS();

        try {
            const response = await fetch(`/jira/sprint/burndown_data/${sprintId}`);
            const data = await response.json();

            if (data.error) {
                const ctx = canvas.getContext('2d');
                if (burndownChart) burndownChart.destroy();
                ctx.clearRect(0, 0, canvas.width, canvas.height);
                ctx.font = '16px Arial';
                ctx.textAlign = 'center';
                ctx.fillStyle = '#dc3545';
                ctx.fillText(data.error, canvas.width / 2, canvas.height / 2);
                return;
            }

            // Update stats
            const statsDiv = document.getElementById('sprintStats');
            if (statsDiv) {
                statsDiv.style.display = 'block';
                document.getElementById('totalPoints').textContent = data.total_story_points;
                const remaining = data.remaining_values[data.remaining_values.length - 1] || 0;
                const completed = data.total_story_points - remaining;
                document.getElementById('completedPoints').textContent = Math.round(completed);
                document.getElementById('remainingPoints').textContent = Math.round(remaining);
            }

            if (burndownChart) {
                burndownChart.destroy();
            }

            const ctx = canvas.getContext('2d');

            // Créer gradient pour la ligne rouge
            const gradient = ctx.createLinearGradient(0, 0, 0, 400);
            gradient.addColorStop(0, 'rgba(220, 53, 69, 0.1)');
            gradient.addColorStop(1, 'rgba(220, 53, 69, 0)');

            burndownChart = new Chart(ctx, {
                type: 'line',
                data: {
                    labels: data.labels,
                    datasets: [
                        {
                            label: 'Ligne idéale',
                            data: data.guideline,
                            borderColor: '#999',
                            backgroundColor: 'transparent',
                            borderWidth: 2,
                            borderDash: [5, 5],
                            pointRadius: 0,
                            tension: 0
                        },
                        {
                            label: 'Progression réelle',
                            data: data.remaining_values,
                            borderColor: '#dc3545',
                            backgroundColor: gradient,
                            borderWidth: 3,
                            pointRadius: 5,
                            pointBackgroundColor: '#dc3545',
                            pointBorderColor: '#fff',
                            pointBorderWidth: 2,
                            pointHoverRadius: 7,
                            stepped: 'before',
                            tension: 0,
                            fill: true
                        }
                    ]
                },
                options: {
                    responsive: true,
                    maintainAspectRatio: false,
                    interaction: {
                        mode: 'index',
                        intersect: false
                    },
                    scales: {
                        y: {
                            beginAtZero: true,
                            title: {
                                display: true,
                                text: 'Story Points',
                                font: { size: 14, weight: '600' },
                                color: '#666'
                            },
                            grid: {
                                color: 'rgba(0, 0, 0, 0.05)',
                                borderDash: [3, 3]
                            },
                            ticks: {
                                font: { size: 12 },
                                color: '#666'
                            }
                        },
                        x: {
                            title: {
                                display: true,
                                text: 'Période',
                                font: { size: 14, weight: '600' },
                                color: '#666'
                            },
                            grid: {
                                color: function(context) {
                                    const index = context.index;
                                    if (data.non_working_days && data.non_working_days[index] === 1) {
                                        return 'rgba(200, 200, 200, 0.3)';
                                    }
                                    return 'rgba(0, 0, 0, 0.05)';
                                },
                                borderDash: [3, 3],
                                lineWidth: function(context) {
                                    const index = context.index;
                                    if (data.non_working_days && data.non_working_days[index] === 1) {
                                        return 0;
                                    }
                                    return 1;
                                }
                            },
                            ticks: {
                                font: { size: 11 },
                                color: '#666',
                                maxRotation: 45,
                                minRotation: 45
                            }
                        }
                    },
                    plugins: {
                        legend: {
                            display: false
                        },
                        tooltip: {
                            backgroundColor: 'rgba(0, 0, 0, 0.8)',
                            padding: 12,
                            titleFont: { size: 14, weight: '600' },
                            bodyFont: { size: 13 },
                            borderColor: '#ddd',
                            borderWidth: 1,
                            callbacks: {
                                label: function(context) {
                                    return context.dataset.label + ': ' +
                                           context.parsed.y.toFixed(1) + ' points';
                                },
                                afterLabel: function(context) {
                                    const index = context.dataIndex;
                                    if (data.non_working_days && data.non_working_days[index] === 1) {
                                        return '🏖️ Jour non-ouvré';
                                    }
                                    return '';
                                }
                            }
                        }
                    }
                }
            });

            console.log('✅ Professional burndown chart rendered!');

        } catch (error) {
            console.error('❌ Error:', error);
        }
    }

    // Initialize
    let attempts = 0;
    const tryInit = setInterval(() => {
        attempts++;
        const selector = document.getElementById('sprintSelector');
        const canvas = document.getElementById('sprintBurndownChart');

        if (selector && canvas) {
            console.log('✅ Burndown Pro elements found!');
            loadSprintOptions();

            selector.addEventListener('change', (e) => {
                const sprintId = e.target.value;
                if (sprintId) {
                    renderBurndownChart(sprintId);
                } else {
                    // Hide stats when no sprint selected
                    const statsDiv = document.getElementById('sprintStats');
                    if (statsDiv) statsDiv.style.display = 'none';
                }
            });

            clearInterval(tryInit);
        } else if (attempts >= 30) {
            clearInterval(tryInit);
        }
    }, 1000);

})();