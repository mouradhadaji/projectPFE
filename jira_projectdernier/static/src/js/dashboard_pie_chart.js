/** @odoo-module **/

import { registry } from "@web/core/registry";
import { Component, onMounted, onWillUnmount, useRef } from "@odoo/owl";
import { useService } from "@web/core/utils/hooks";
import { loadJS } from "@web/core/assets";

export class DashboardPieChart extends Component {
    setup() {
        this.chartRef = useRef("pieChart");
        this.orm = useService("orm");
        this.chartInstance = null;

        onMounted(async () => {
            await this.renderChart();
        });

        onWillUnmount(() => {
            if (this.chartInstance) {
                this.chartInstance.destroy();
            }
        });
    }

    async renderChart() {
        // Load Chart.js
        await loadJS("https://cdn.jsdelivr.net/npm/chart.js");

        const resId = this.props.record.resId;
        if (!resId) return;

        // Get data from backend
        const chartData = await this.orm.call(
            "jira.dashboard",
            "get_projects_pie_chart_data",
            [[resId]]
        );

        // Destroy old chart
        if (this.chartInstance) {
            this.chartInstance.destroy();
        }

        // Create new chart
        const ctx = this.chartRef.el;
        if (ctx && chartData) {
            this.chartInstance = new Chart(ctx, {
                type: 'pie',
                data: {
                    labels: chartData.labels,
                    datasets: [{
                        data: chartData.data,
                        backgroundColor: chartData.colors
                    }]
                },
                options: {
                    responsive: true,
                    maintainAspectRatio: true,
                    plugins: {
                        legend: {
                            position: 'bottom'
                        },
                        tooltip: {
                            callbacks: {
                                label: (context) => {
                                    return context.label + ': ' + context.parsed + '%';
                                }
                            }
                        }
                    }
                }
            });
        }
    }
}

DashboardPieChart.template = "jira_project.DashboardPieChart";

registry.category("fields").add("dashboard_pie_chart", DashboardPieChart);