/** @odoo-module **/

(function() {
    'use strict';

    let chartInstance = null;
    let chartJsLoaded = false;
    let burndownChart = null;

    async function loadChartJS() { chartJsLoaded = true; return; }

    async function rpcCall(model, method, args) {
    const response = await fetch('/web/dataset/call_kw', {
        method: 'POST',  // ✅ toujours POST, jamais GET
        headers: {
            'Content-Type': 'application/json',
            'X-Requested-With': 'XMLHttpRequest'
        },
        body: JSON.stringify({
            jsonrpc: '2.0',
            method: 'call',
            id: Date.now(),
            params: {
                model: model,
                method: method,
                args: args,
                kwargs: {}
            }
        })
    });
    if (!response.ok) {
        const text = await response.text();
        throw new Error('HTTP ' + response.status + ': ' + text);
    }
    const data = await response.json();
    if (data.error) throw new Error(data.error.data?.message || data.error.message);
    return data.result;
}

    function getRecordIdFromURL() {
        const segments = window.location.pathname.split('/');
        const num = parseInt(segments[segments.length - 1]);
        if (!isNaN(num) && num > 0) return num;
        const hashMatch = window.location.hash.match(/id=(\d+)/);
        if (hashMatch) return parseInt(hashMatch[1]);
        return null;
    }

    // ─── BURNDOWN ─────────────────────────────────────────────────────────────

    async function loadSprintOptions() {
        const selector = document.getElementById('sprintSelector');
        if (!selector) return;
        try {
            const response = await fetch('/web/dataset/call_kw', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ jsonrpc: '2.0', method: 'call', params: { model: 'jira.sprint', method: 'search_read', args: [[]], kwargs: { fields: ['id', 'name', 'project_id'], order: 'name asc' } }, id: Date.now() })
            });
            const result = await response.json();
            if (result.error) return;
            const sprints = result.result || [];
            selector.innerHTML = '<option value="">Sélectionnez un sprint...</option>';
            sprints.forEach(function(sprint) {
                const option = document.createElement('option');
                option.value = sprint.id;
                option.textContent = sprint.name + (sprint.project_id ? ` (${sprint.project_id[1]})` : '');
                selector.appendChild(option);
            });
        } catch(e) { console.error('❌ Error loading sprints:', e); }
    }

    async function renderBurndownChart(sprintId) {
        const canvas = document.getElementById('sprintBurndownChart');
        if (!canvas || !sprintId) return;
        await loadChartJS();
        try {
            const response = await fetch(`/jira/sprint/burndown_data/${sprintId}`);
            const data = await response.json();
            if (data.error) {
                const ctx = canvas.getContext('2d');
                if (burndownChart) burndownChart.destroy();
                ctx.clearRect(0, 0, canvas.width, canvas.height);
                ctx.font = '16px Arial'; ctx.textAlign = 'center'; ctx.fillStyle = '#d9534f';
                ctx.fillText(data.error, canvas.width / 2, canvas.height / 2);
                return;
            }
            if (burndownChart) burndownChart.destroy();
            burndownChart = new Chart(canvas.getContext('2d'), {
                type: 'line',
                data: { labels: data.labels, datasets: [
                    { label: 'Guideline', data: data.guideline, borderColor: '#999', backgroundColor: 'transparent', borderWidth: 2, pointRadius: 0, tension: 0 },
                    { label: 'Remaining Values', data: data.remaining_values, borderColor: '#d9534f', backgroundColor: 'transparent', borderWidth: 3, pointRadius: 4, pointBackgroundColor: '#d9534f', stepped: 'before', tension: 0 }
                ]},
                options: { responsive: true, maintainAspectRatio: false, scales: { y: { beginAtZero: true, title: { display: true, text: 'Story Points' } }, x: { title: { display: true, text: 'Time' } } }, plugins: { legend: { position: 'top', align: 'end' } } }
            });
        } catch(e) { console.error('❌ Burndown error:', e); }
    }

    function initBurndown() {
        const selector = document.getElementById('sprintSelector');
        const canvas = document.getElementById('sprintBurndownChart');
        if (!selector || !canvas || selector.dataset.burndownInit) return;
        selector.dataset.burndownInit = 'true';
        loadSprintOptions();
        selector.addEventListener('change', function(e) { if (e.target.value) renderBurndownChart(e.target.value); });
    }

    // ─── DASHBOARD CHART ──────────────────────────────────────────────────────

    async function renderDashboardChart() {
        const canvas = document.getElementById('projectsPieChart');
        if (!canvas) return;
        await loadChartJS();
        const recordId = getRecordIdFromURL();
        let data;
        if (recordId) {
            try { const response = await fetch('/jira/dashboard/chart_data/' + recordId); data = await response.json(); }
            catch(e) { data = { labels: [], data: [], colors: [] }; }
        } else {
            const tags = document.querySelectorAll('.o_field_many2many_tags .badge');
            const projects = Array.from(tags).map(function(t) { return { name: t.textContent.trim().replace('×','').trim(), completion: Math.random()*100 }; }).filter(function(p) { return p.name; });
            if (!projects.length) return;
            data = { labels: projects.map(function(p) { return p.name; }), data: projects.map(function(p) { return p.completion; }), colors: ['#FF6384','#36A2EB','#FFCE56','#4BC0C0','#9966FF','#FF9F40'] };
        }
        if (!data || !data.labels || !data.labels.length) return;
        if (chartInstance) chartInstance.destroy();
        chartInstance = new Chart(canvas.getContext('2d'), {
            type: 'pie',
            data: { labels: data.labels, datasets: [{ data: data.data, backgroundColor: data.colors, borderWidth: 2, borderColor: '#fff' }] },
            options: { responsive: true, maintainAspectRatio: false, plugins: { legend: { position: 'bottom' }, tooltip: { callbacks: { label: function(c) { return c.label + ': ' + c.parsed.toFixed(2) + '%'; } } } } }
        });
    }

    // ─── VELOCITY ─────────────────────────────────────────────────────────────

    async function loadVelocityProjects() {
        const field = document.querySelector('[name="velocity_project_ids"]');
        if (!field || field.dataset.observed === 'true') return;
        field.dataset.observed = 'true';
        async function updateChart() {
            const names = Array.from(field.querySelectorAll('.badge')).map(function(b) { return b.textContent.trim().replace(/[×x]/g, '').trim(); }).filter(function(n) { return n; });
            if (!names.length) { if (window.teamVelocityChartInstance) { window.teamVelocityChartInstance.destroy(); window.teamVelocityChartInstance = null; } return; }
            const projects = await rpcCall('jira.project', 'search_read', [[['name', 'in', names]], ['id', 'name']]);
            const ids = projects.map(function(p) { return p.id; });
            if (ids.length) await renderVelocityChartByProject(ids);
        }
        new MutationObserver(function() { updateChart(); }).observe(field, { childList: true, subtree: true });
        await updateChart();
        setTimeout(updateChart, 500);
        setTimeout(updateChart, 1000);
    }

    async function renderVelocityChartByProject(projectIds) {
        const canvas = document.getElementById('teamVelocityChart');
        if (!canvas) return;
        await loadChartJS();
        try {
            const data = await rpcCall('jira.dashboard', 'get_velocity_by_project', [projectIds]);
            if (!data.labels || !data.labels.length) {
                const ctx = canvas.getContext('2d');
                ctx.clearRect(0, 0, canvas.width, canvas.height);
                ctx.font = '16px Arial'; ctx.textAlign = 'center'; ctx.fillStyle = '#666';
                ctx.fillText('No sprint data.', canvas.width / 2, canvas.height / 2);
                return;
            }
            const avgEl = document.getElementById('avgVelocity');
            const subEl = document.getElementById('velocitySubtitle');
            if (avgEl) avgEl.textContent = data.avg_velocity || 0;
            if (subEl) subEl.textContent = 'Calculated based on the last ' + (data.sprint_count || 0) + ' sprints.';
            if (window.teamVelocityChartInstance) { window.teamVelocityChartInstance.destroy(); window.teamVelocityChartInstance = null; }
            window._velocityRawData = JSON.parse(JSON.stringify(data));
            window.teamVelocityChartInstance = new Chart(canvas.getContext('2d'), {
                type: 'bar',
                data: {
                    labels: data.labels,
                    datasets: [
                        { label: 'Initial Scope', data: data.initial_scope, backgroundColor: '#4472C4', borderRadius: 4, barThickness: 40 },
                        { label: 'Final Scope', data: data.final_scope, backgroundColor: '#ED7D31', borderRadius: 4, barThickness: 40 },
                        { label: 'Completed', data: data.completed, backgroundColor: '#70AD47', borderRadius: 4, barThickness: 40 },
                        { label: 'Velocity Trend', data: data.completed, type: 'line', borderColor: '#dc3545', borderWidth: 3, pointRadius: 4, pointBackgroundColor: '#dc3545', fill: false, tension: 0.4, spanGaps: true, order: 0 }
                    ]
                },
                options: {
                    responsive: true, maintainAspectRatio: false, clip: false,
                    plugins: { legend: { display: false }, tooltip: { callbacks: { title: function(items) { return data.labels[items[0].dataIndex]; }, label: function(c) { return c.dataset.label + ': ' + c.parsed.y + ' pts'; } } } },
                    scales: {
                        x: { title: { display: true, text: 'Sprints', color: '#666', font: { size: 12, weight: 'bold' } }, grid: { display: false }, ticks: { callback: function(value, index) { return 'Sprint ' + (index + 1); } } },
                        y: { title: { display: true, text: 'Story Points', color: '#666', font: { size: 12, weight: 'bold' } }, beginAtZero: true, grid: { color: '#e0e0e0' } }
                    }
                }
            });
            _setActiveBtn('btnBar');
        } catch(e) { console.error('❌ Velocity error:', e); }
    }

    function _setActiveBtn(id) {
        ['btnBar','btnLine','btnPie','btnStack'].forEach(function(b) {
            const el = document.getElementById(b);
            if (!el) return;
            el.style.borderColor = (b === id) ? '#4f8ef7' : '#ddd';
            el.style.background  = (b === id) ? '#eef3ff' : 'white';
        });
    }

    function doSetChartType(type) {
        const chart = window.teamVelocityChartInstance;
        if (!chart) return;
        const d = window._velocityRawData;
        const btnMap = { bar: 'btnBar', line: 'btnLine', pie: 'btnPie', stack: 'btnStack' };
        _setActiveBtn(btnMap[type]);
        if (type === 'pie') {
            chart.config.type = 'pie';
            const totalComplete = d.completed.reduce(function(a,b){ return a+b; }, 0);
            const totalFinal = d.final_scope.reduce(function(a,b){ return a+b; }, 0);
            const totalInitial = d.initial_scope.reduce(function(a,b){ return a+b; }, 0);
            const totalInProgress = Math.max(0, totalFinal - totalComplete);
            const totalTodo = Math.max(0, totalInitial - totalComplete - totalInProgress);
            chart.data.labels = ['Completed', 'In Progress', 'To Do'];
            chart.data.datasets = [{ data: [totalComplete, totalInProgress, totalTodo], backgroundColor: ['#70AD47', '#ED7D31', '#4472C4'], borderWidth: 2, borderColor: '#fff' }];
            chart.options.scales = {};
            chart.options.plugins.legend = { display: true, position: 'right', labels: { usePointStyle: true, pointStyle: 'circle', padding: 20, font: { size: 13 } } };
        } else {
            if (chart.config.type === 'pie') {
                chart.data.labels = [...d.labels];
                chart.data.datasets = [
                    { label: 'Initial Scope', data: [...d.initial_scope], backgroundColor: '#4472C4', borderRadius: 4, barThickness: 40 },
                    { label: 'Final Scope', data: [...d.final_scope], backgroundColor: '#ED7D31', borderRadius: 4, barThickness: 40 },
                    { label: 'Completed', data: [...d.completed], backgroundColor: '#70AD47', borderRadius: 4, barThickness: 40 },
                    { label: 'Velocity Trend', data: [...d.completed], type: 'line', borderColor: '#dc3545', borderWidth: 3, pointRadius: 4, pointBackgroundColor: '#dc3545', fill: false, tension: 0.4, order: 0 }
                ];
                chart.options.scales = {
                    x: { title: { display: true, text: 'Sprints', color: '#666', font: { size: 12, weight: 'bold' } }, grid: { display: false }, ticks: { callback: function(value, index) { return 'Sprint ' + (index + 1); } } },
                    y: { title: { display: true, text: 'Story Points', color: '#666', font: { size: 12, weight: 'bold' } }, beginAtZero: true }
                };
                chart.options.plugins.legend = { display: false };
            }
            if (type === 'stack') { chart.config.type = 'bar'; chart.data.datasets.forEach(function(ds) { if (ds.type !== 'line') ds.stack = 'v'; }); }
            else if (type === 'bar') { chart.config.type = 'bar'; chart.data.datasets.forEach(function(ds) { delete ds.stack; }); }
            else if (type === 'line') {
                chart.config.type = 'line';
                chart.data.datasets.forEach(function(ds) {
                    delete ds.stack;
                    if (ds.label === 'Initial Scope') { ds.fill = true; ds.tension = 0.4; ds.pointRadius = 4; ds.borderWidth = 2; ds.borderColor = '#4472C4'; ds.backgroundColor = 'rgba(68,114,196,0.3)'; ds.pointBackgroundColor = '#4472C4'; }
                    else if (ds.label === 'Final Scope') { ds.fill = true; ds.tension = 0.4; ds.pointRadius = 4; ds.borderWidth = 2; ds.borderColor = '#ED7D31'; ds.backgroundColor = 'rgba(237,125,49,0.3)'; ds.pointBackgroundColor = '#ED7D31'; }
                    else if (ds.label === 'Completed') { ds.fill = true; ds.tension = 0.4; ds.pointRadius = 4; ds.borderWidth = 2; ds.borderColor = '#70AD47'; ds.backgroundColor = 'rgba(112,173,71,0.3)'; ds.pointBackgroundColor = '#70AD47'; }
                    else if (ds.label === 'Velocity Trend') { ds.fill = false; ds.tension = 0.4; ds.borderColor = '#dc3545'; ds.backgroundColor = 'transparent'; ds.borderWidth = 3; ds.pointRadius = 4; ds.pointBackgroundColor = '#dc3545'; }
                });
            }
        }
        chart.update();
    }

    function doSortVelocity(dir) {
        const chart = window.teamVelocityChartInstance;
        if (!chart || chart.config.type === 'pie') return;
        const labels = [...chart.data.labels];
        const dd = chart.data.datasets.map(function(ds) { return [...ds.data]; });
        const idx = labels.map(function(_,i) { return i; }).sort(function(a,b) { return dir === 'asc' ? dd[2][a] - dd[2][b] : dd[2][b] - dd[2][a]; });
        chart.data.labels = idx.map(function(i) { return labels[i]; });
        chart.data.datasets.forEach(function(ds, di) { if (di < 3) ds.data = idx.map(function(i) { return dd[di][i]; }); });
        chart.update();
    }

    function doToggleMeasures() {
        const m = document.getElementById('measuresMenu');
        if (m) m.style.display = (m.style.display === 'none') ? 'block' : 'none';
    }

    function doUpdateMeasures() {
        const chart = window.teamVelocityChartInstance;
        if (!chart) return;
        ['measureInitial','measureFinal','measureCompleted','measureAvg'].forEach(function(id, i) {
            const cb = document.getElementById(id);
            if (cb) chart.setDatasetVisibility(i, cb.checked);
        });
        chart.update();
    }

    // ─── MEETING TYPE ─────────────────────────────────────────────────────────

    function setMeetingType(type) {
        const presBtn = document.getElementById('meetingTypePresential');
        const onlineBtn = document.getElementById('meetingTypeOnline');
        const typeInput = document.getElementById('meetingTypeValue');
        if (!presBtn || !onlineBtn || !typeInput) return;
        if (type === 'presentiel') {
            presBtn.style.background = '#eef3ff'; presBtn.style.borderColor = '#4f8ef7'; presBtn.style.color = '#4f8ef7';
            onlineBtn.style.background = 'white'; onlineBtn.style.borderColor = '#ddd'; onlineBtn.style.color = '#888';
        } else {
            onlineBtn.style.background = '#eef3ff'; onlineBtn.style.borderColor = '#4f8ef7'; onlineBtn.style.color = '#4f8ef7';
            presBtn.style.background = 'white'; presBtn.style.borderColor = '#ddd'; presBtn.style.color = '#888';
        }
        typeInput.value = type;
    }

    // ─── HANDLE SAVE MEETING ──────────────────────────────────────────────────

    async function handleSaveMeeting() {
    const saveBtn = document.getElementById('saveMeetingBtn');
    const meetingForm = document.getElementById('meetingForm');
    if (!meetingForm) return;

    // ✅ Empêche les double-clics
    if (saveBtn && saveBtn.dataset.saving === 'true') return;
    if (saveBtn) saveBtn.dataset.saving = 'true';

    const title = document.getElementById('meetingTitle').value.trim();
    const dateVal = document.getElementById('meetingDate').value;
    if (!title || !dateVal) {
        alert('Please fill Title and Date.');
        if (saveBtn) saveBtn.dataset.saving = 'false';
        return;
    }

    const meetingTypeEl = document.getElementById('meetingTypeValue');
    const meetingType = meetingTypeEl ? meetingTypeEl.value : 'presentiel';

    const vals = {
        name: title,
        meeting_date: dateVal.replace('T', ' ') + ':00',
        duration: parseFloat(document.getElementById('meetingDuration').value) || 1.0,
        notes: document.getElementById('meetingNotes').value || '',
        meeting_type: meetingType,
    };

    const projVal = document.getElementById('meetingProject').value;
    if (projVal) vals.project_id = parseInt(projVal);

    const participantSelect = document.getElementById('meetingParticipants');
    if (participantSelect) {
        const selected = Array.from(participantSelect.selectedOptions)
            .map(function(o) { return parseInt(o.value); });
        if (selected.length) vals.participant_ids = [[6, 0, selected]];
    }

    try {
        if (saveBtn) saveBtn.textContent = 'Saving...';
        const editId = meetingForm.getAttribute('data-edit-id');

        if (editId) {
            // ✅ Update existant
            await rpcCall('jira.meeting', 'update_meeting', [parseInt(editId), vals]);
            console.log('✅ Meeting updated:', editId);
        } else {
            // ✅ Nouvelle création
            await rpcCall('jira.meeting', 'create_meeting', [vals]);
            console.log('✅ Meeting created');
        }

        // ✅ Reset propre du formulaire
        meetingForm.removeAttribute('data-edit-id');
        meetingForm.style.display = 'none';
        document.getElementById('meetingTitle').value = '';
        document.getElementById('meetingDate').value = '';
        document.getElementById('meetingDuration').value = '1';
        document.getElementById('meetingNotes').value = '';
        if (document.getElementById('meetingProject'))
            document.getElementById('meetingProject').value = '';
        if (saveBtn) {
            saveBtn.textContent = 'Save Meeting';
            saveBtn.dataset.saving = 'false';
        }
        setMeetingType('presentiel');

        // ✅ Recharge la liste
        await loadMeetings([]);

    } catch(e) {
        console.error('❌ Save meeting error:', e);
        if (saveBtn) {
            saveBtn.textContent = 'Update Meeting';
            saveBtn.dataset.saving = 'false';
        }
    }
}
    window.handleSaveMeeting = handleSaveMeeting;

    // ─── GLOBAL EVENT DELEGATION ──────────────────────────────────────────────

    function setupGlobalDelegation() {
        if (document._jiraDelegation) return;
        document._jiraDelegation = true;
        document.addEventListener('click', function(e) {
            const chartBtn = e.target.closest('[data-chart-type]');
            if (chartBtn) { e.preventDefault(); e.stopImmediatePropagation(); doSetChartType(chartBtn.dataset.chartType); return; }
            const editBtn = e.target.closest('[data-edit-id]');
            if (editBtn) { e.preventDefault(); e.stopImmediatePropagation(); window._editMeeting(parseInt(editBtn.getAttribute('data-edit-id'))); return; }
            if (e.target.closest('#saveMeetingBtn')) { e.preventDefault(); e.stopPropagation(); window.handleSaveMeeting(); return; }
            if (e.target.closest('#cancelMeetingBtn')) {
                e.preventDefault(); e.stopImmediatePropagation();
                const f = document.getElementById('meetingForm');
                if (f) { f.removeAttribute('data-edit-id'); f.style.display = 'none'; }
                const sb = document.getElementById('saveMeetingBtn');
                if (sb) sb.textContent = 'Save Meeting';
                setMeetingType('presentiel');
                return;
            }
            // ✅ Meeting type buttons
            if (e.target.closest('#meetingTypePresential')) { e.preventDefault(); e.stopImmediatePropagation(); setMeetingType('presentiel'); return; }
            if (e.target.closest('#meetingTypeOnline')) { e.preventDefault(); e.stopImmediatePropagation(); setMeetingType('en_ligne'); return; }

            const activityBtn = e.target.closest('[data-activity-period]');
            if (activityBtn) { e.preventDefault(); e.stopImmediatePropagation(); loadTeamActivity(activityBtn.dataset.activityPeriod, null); return; }
            const sortBtn = e.target.closest('[data-sort]');
            if (sortBtn && !sortBtn.closest('#measuresMenu')) { e.preventDefault(); e.stopImmediatePropagation(); doSortVelocity(sortBtn.dataset.sort); return; }
            if (e.target.closest('#measuresBtn')) { e.preventDefault(); e.stopImmediatePropagation(); doToggleMeasures(); return; }
            const menuRow = e.target.closest('#measuresMenu > div');
            if (menuRow) { const cb = menuRow.querySelector('input[type="checkbox"]'); if (cb && e.target !== cb) cb.checked = !cb.checked; doUpdateMeasures(); return; }
            if (!e.target.closest('#measuresBtn') && !e.target.closest('#measuresMenu')) { const m = document.getElementById('measuresMenu'); if (m) m.style.display = 'none'; }
        }, true);
        document.addEventListener('change', function(e) {
            if (e.target.closest('#measuresMenu') && e.target.type === 'checkbox') { doUpdateMeasures(); }
        }, true);
        console.log('✅ Global delegation ready');
    }

    // ─── SPRINT REPORT ────────────────────────────────────────────────────────

    async function loadSprintReport() {
        const sprintField = document.querySelector('[name="sprint_id"]');
        if (!sprintField || sprintField.dataset.reportObserved === 'true') return;
        sprintField.dataset.reportObserved = 'true';
        async function updateReport() {
            let sprintId = null;
            const link = sprintField.querySelector('a.o_form_uri');
            if (link) {
                const href = link.getAttribute('href') || '';
                const match = href.match(/\/(\d+)$/);
                if (match) sprintId = parseInt(match[1]);
                if (!sprintId) { const name = link.textContent.trim(); if (name) { const res = await rpcCall('jira.sprint', 'search_read', [[['name', '=', name]], ['id']]); if (res.length) sprintId = res[0].id; } }
            }
            if (!sprintId) return;
            try { const data = await rpcCall('jira.dashboard', 'get_sprint_report', [sprintId]); if (data && data.sprint_name) renderSprintReport(data); }
            catch(e) { console.error('❌ Sprint report error:', e); }
        }
        new MutationObserver(function() { setTimeout(updateReport, 0); }).observe(sprintField, { childList: true, subtree: true });
        setTimeout(updateReport, 300);
    }

    function renderSprintReport(data) {
        const meta = document.getElementById('sprintReportMeta');
        if (meta) meta.textContent = data.sprint_name + ' · ' + data.start_date + ' → ' + data.end_date;
        const canvas = document.getElementById('sprintReportBurndown');
        if (canvas && data.burndown && data.burndown.length) {
            if (window.sprintReportChartInstance) { window.sprintReportChartInstance.destroy(); window.sprintReportChartInstance = null; }
            window.sprintReportChartInstance = new Chart(canvas.getContext('2d'), {
                type: 'line',
                data: { labels: data.burndown.map(function(d) { return d.date; }), datasets: [
                    { label: 'Guideline', data: data.burndown.map(function(d) { return d.ideal; }), borderColor: '#aaa', borderWidth: 1.5, pointRadius: 0, fill: false, tension: 0 },
                    { label: 'Remaining Values', data: data.burndown.map(function(d) { return d.remaining; }), borderColor: '#e05c5c', borderWidth: 2, pointRadius: 4, pointBackgroundColor: '#e05c5c', fill: false, tension: 0, stepped: 'before' }
                ]},
                options: { responsive: true, maintainAspectRatio: false, plugins: { legend: { display: false } }, scales: { x: { grid: { color: '#f0f0f0' }, ticks: { color: '#888', font: { size: 11 } } }, y: { beginAtZero: true, grid: { color: '#f0f0f0' }, ticks: { color: '#888' }, title: { display: true, text: 'Story Points', color: '#888' } } } }
            });
        }
        const tbody = document.getElementById('sprintReportIssues');
        if (tbody) {
            if (!data.issues || !data.issues.length) { tbody.innerHTML = '<tr><td colspan="4" style="padding:20px;text-align:center;color:#bbb;">🎉 All issues completed!</td></tr>'; return; }
            const statusColors = { 'to_do': '#6c757d', 'todo': '#6c757d', 'in_progress': '#0d6efd', 'in_review': '#fd7e14', 'blocked': '#dc3545', 'done': '#198754', 'complete': '#198754' };
            tbody.innerHTML = data.issues.map(function(issue) {
                const color = statusColors[(issue.ticket_status || '').toLowerCase()] || '#6c757d';
                return '<tr style="border-bottom:1px solid #f5f5f5;"><td style="padding:10px;color:#333;">' + (issue.name || '-') + '</td><td style="padding:10px;"><span style="padding:3px 10px;border-radius:12px;font-size:11px;font-weight:500;background:' + color + '22;color:' + color + ';">' + (issue.ticket_status || 'To Do') + '</span></td><td style="padding:10px;color:#666;">' + (issue.priority || 'Low') + '</td><td style="padding:10px;text-align:right;font-weight:600;color:#333;">' + (issue.story_points || 0) + '</td></tr>';
            }).join('');
        }
    }

    // ─── TEAM ACTIVITY ────────────────────────────────────────────────────────

    async function loadTeamActivity(period, selectedMonth) {
        period = period || 'week';
        selectedMonth = selectedMonth || null;
        const canvas = document.getElementById('teamActivityChart');
        if (!canvas) return;
        await loadChartJS();
        const activityField = document.querySelector('[name="activity_project_ids"]');
        let projectIds = [];
        if (activityField) {
            if (!activityField.dataset.activityObserved) {
                activityField.dataset.activityObserved = 'true';
                new MutationObserver(function() {
                    const activeBtn = document.querySelector('[data-activity-period][style*="eef3ff"]');
                    const currentPeriod = activeBtn ? activeBtn.dataset.activityPeriod : 'week';
                    loadTeamActivity(currentPeriod, null);
                }).observe(activityField, { childList: true, subtree: true });
            }
            const names = Array.from(activityField.querySelectorAll('.badge')).map(function(b) { return b.textContent.trim().replace(/[×x]/g, '').trim(); }).filter(function(n) { return n; });
            if (names.length) { const projects = await rpcCall('jira.project', 'search_read', [[['name', 'in', names]], ['id']]); projectIds = projects.map(function(p) { return p.id; }); }
        }
        if (!projectIds.length) {
            const vField = document.querySelector('[name="velocity_project_ids"]');
            if (vField) {
                const names = Array.from(vField.querySelectorAll('.badge')).map(function(b) { return b.textContent.trim().replace(/[×x]/g, '').trim(); }).filter(function(n) { return n; });
                if (names.length) { const projects = await rpcCall('jira.project', 'search_read', [[['name', 'in', names]], ['id']]); projectIds = projects.map(function(p) { return p.id; }); }
            }
        }
        try {
            const data = await rpcCall('jira.dashboard', 'get_team_activity_by_member', [projectIds, period, selectedMonth]);
            renderActivityChart(data, period);
        } catch(e) { console.error('❌ Activity error:', e); }
    }

    function renderActivityChart(data, period) {
        const canvas = document.getElementById('teamActivityChart');
        if (!canvas) return;
        if (window.teamActivityChartInstance) { window.teamActivityChartInstance.destroy(); window.teamActivityChartInstance = null; }
        var datasets = [];
        if (data.datasets && data.datasets.length) {
            datasets = data.datasets.map(function(ds) { return { label: ds.label, data: ds.data, borderColor: ds.color, borderWidth: 2.5, backgroundColor: ds.color + '23', pointBackgroundColor: ds.color, pointRadius: 5, pointHoverRadius: 7, fill: true, tension: 0.4 }; });
        } else {
            datasets = [{ label: 'Story Points', data: data.points || [], borderColor: '#4f8ef7', borderWidth: 2.5, backgroundColor: 'rgba(79,142,247,0.1)', pointBackgroundColor: '#4f8ef7', pointRadius: 5, pointHoverRadius: 7, fill: true, tension: 0.4 }];
        }
        window.teamActivityChartInstance = new Chart(canvas.getContext('2d'), {
            type: 'line', data: { labels: data.labels, datasets: datasets },
            options: { responsive: true, maintainAspectRatio: false, plugins: { legend: { display: datasets.length > 1, position: 'bottom', labels: { usePointStyle: true, pointStyle: 'circle', padding: 15, font: { size: 12 } } }, tooltip: { callbacks: { label: function(c) { return c.dataset.label + ': ' + c.parsed.y + ' pts'; } } } }, scales: { x: { grid: { display: false }, ticks: { color: '#888', font: { size: 11 } } }, y: { beginAtZero: true, grid: { color: '#f0f0f0' }, ticks: { color: '#888', font: { size: 11 } }, title: { display: true, text: 'Story Points', color: '#888' } } } }
        });
        ['activityBtnWeek', 'activityBtnMonth'].forEach(function(id) {
            const btn = document.getElementById(id);
            if (!btn) return;
            const isActive = btn.dataset.activityPeriod === period;
            btn.style.borderColor = isActive ? '#4f8ef7' : '#ddd';
            btn.style.background  = isActive ? '#eef3ff' : 'white';
            btn.style.color       = isActive ? '#4f8ef7' : '#888';
        });
    }

    // ─── TIMELINE ─────────────────────────────────────────────────────────────

    async function loadProjectTimeline(projectIds) {
        const container = document.getElementById('timelineList');
        if (!container) return;
        try {
            const items = await rpcCall('jira.dashboard', 'get_project_timeline', [projectIds]);
            if (!items || !items.length) { container.innerHTML = '<div style="color:#bbb;font-size:12px;">No activity yet.</div>'; return; }
            container.innerHTML = items.map(function(item) {
                return '<div style="display:flex;align-items:flex-start;gap:12px;margin-bottom:12px;"><div style="min-width:10px;height:10px;border-radius:50%;background:' + item.color + ';margin-top:3px;"></div><div style="flex:1;"><div style="font-size:12px;font-weight:600;color:#333;">' + item.name + '</div><div style="font-size:11px;color:#888;margin-top:2px;"><span style="background:' + item.color + '22;color:' + item.color + ';padding:1px 8px;border-radius:10px;">' + item.status + '</span> · ' + item.project + '</div></div><div style="text-align:right;min-width:70px;"><div style="font-size:11px;font-weight:600;color:#555;">' + item.date + '</div><div style="font-size:11px;color:#aaa;">' + item.time + '</div></div></div>';
            }).join('');
        } catch(e) { console.error('❌ Timeline error:', e); }
    }

    // ─── MEETINGS ─────────────────────────────────────────────────────────────

    async function loadMeetings(projectIds) {
        const container = document.getElementById('meetingsList');
        if (!container) return;
        try {
            const meetings = await rpcCall('jira.meeting', 'get_upcoming_meetings', [projectIds || []]);
            if (!meetings || !meetings.length) { container.innerHTML = '<div style="color:#bbb;font-size:12px;text-align:center;padding:20px;">No upcoming meetings. Schedule one!</div>'; return; }
            container.innerHTML = meetings.map(function(m) {
                const participants = m.participants.slice(0, 4).map(function(p) { return '<div title="' + p.name + '" style="width:28px;height:28px;border-radius:50%;background:#4f8ef7;color:white;font-size:10px;font-weight:700;display:inline-flex;align-items:center;justify-content:center;margin-left:-6px;border:2px solid white;">' + p.initials + '</div>'; }).join('');
                const extra = m.participants.length > 4 ? '<div style="width:28px;height:28px;border-radius:50%;background:#eee;color:#888;font-size:10px;font-weight:700;display:inline-flex;align-items:center;justify-content:center;margin-left:-6px;border:2px solid white;">+' + (m.participants.length - 4) + '</div>' : '';
                // ✅ Badge type réunion coloré
                const typeLabel = m.meeting_type === 'en_ligne' ? '💻 En Ligne' : '🏢 Présentiel';
                const typeBadgeColor = m.meeting_type === 'en_ligne' ? '#17a2b8' : '#28a745';
                return '<div style="display:flex;align-items:flex-start;gap:14px;padding:12px 0;border-bottom:1px solid #f5f5f5;">' +
                    '<div style="min-width:48px;text-align:center;background:#f0f4ff;border-radius:8px;padding:6px 4px;"><div style="font-size:16px;font-weight:700;color:#4f8ef7;line-height:1;">' + m.date.split(' ')[0] + '</div><div style="font-size:10px;color:#888;">' + m.date.split(' ')[1] + '</div></div>' +
                    '<div style="flex:1;"><div style="font-size:13px;font-weight:600;color:#333;">' + m.name + '</div>' +
                    '<div style="font-size:11px;color:#888;margin-top:3px;">🕐 ' + m.time + ' · ' + m.duration + 'h' + (m.project ? ' · 📁 ' + m.project : '') + '</div>' +
                    '<div style="margin-top:4px;"><span style="padding:2px 8px;border-radius:10px;font-size:10px;font-weight:600;background:' + typeBadgeColor + '22;color:' + typeBadgeColor + ';">' + typeLabel + '</span></div>' +
                    (m.notes ? '<div style="font-size:11px;color:#aaa;margin-top:4px;font-style:italic;">' + m.notes.substring(0, 80) + (m.notes.length > 80 ? '...' : '') + '</div>' : '') + '</div>' +
                    '<div style="display:flex;align-items:center;padding-left:6px;">' + participants + extra + '</div>' +
                    '<div data-edit-id="' + m.id + '" style="cursor:pointer;padding:4px 10px;border:1.5px solid #4f8ef7;border-radius:6px;font-size:11px;color:#4f8ef7;margin-left:8px;white-space:nowrap;">✏️ Edit</div>' +
                '</div>';
            }).join('');
        } catch(e) { console.error('❌ Meetings error:', e); }
    }

    async function initMeetingForm() {
        const addBtn = document.getElementById('addMeetingBtn');
        const projectSelect = document.getElementById('meetingProject');
        if (!addBtn || addBtn.dataset.initialized) return;
        addBtn.dataset.initialized = 'true';
        addBtn.addEventListener('click', function() {
            const meetingForm = document.getElementById('meetingForm');
            meetingForm.removeAttribute('data-edit-id');
            document.getElementById('meetingTitle').value = '';
            document.getElementById('meetingDate').value = '';
            document.getElementById('meetingDuration').value = '1';
            document.getElementById('meetingNotes').value = '';
            if (projectSelect) projectSelect.value = '';
            const saveBtn = document.getElementById('saveMeetingBtn');
            if (saveBtn) saveBtn.textContent = 'Save Meeting';
            setMeetingType('presentiel');
            meetingForm.style.display = meetingForm.style.display === 'none' ? 'block' : 'none';
        }, true);

        const cancelBtn = document.getElementById('cancelMeetingBtn');
        if (cancelBtn) { cancelBtn.addEventListener('click', function(e) { e.preventDefault(); e.stopImmediatePropagation(); const f = document.getElementById('meetingForm'); f.removeAttribute('data-edit-id'); f.style.display = 'none'; const sb = document.getElementById('saveMeetingBtn'); if (sb) sb.textContent = 'Save Meeting'; setMeetingType('presentiel'); }, true); }
        if (projectSelect) { rpcCall('jira.project', 'search_read', [[], ['id', 'name']]).then(function(projects) { projects.forEach(function(p) { const opt = document.createElement('option'); opt.value = p.id; opt.textContent = p.name; projectSelect.appendChild(opt); }); }).catch(function() {}); }
        rpcCall('res.users', 'search_read', [[['share', '=', false]], ['id', 'name']]).then(function(users) { const ps = document.getElementById('meetingParticipants'); if (!ps) return; users.forEach(function(u) { const opt = document.createElement('option'); opt.value = u.id; opt.textContent = u.name; ps.appendChild(opt); }); }).catch(function() {});
    }

    window._editMeeting = async function(meetingId) {
        try {
            const res = await rpcCall('jira.meeting', 'search_read', [[['id', '=', meetingId]], ['id', 'name', 'meeting_date', 'duration', 'project_id', 'notes', 'participant_ids', 'meeting_type']]);
            if (!res.length) return;
            const m = res[0];
            document.getElementById('meetingTitle').value = m.name || '';
            document.getElementById('meetingDuration').value = m.duration || 1;
            document.getElementById('meetingNotes').value = m.notes || '';
            if (m.meeting_date) { const d = new Date(m.meeting_date); const local = new Date(d.getTime() - d.getTimezoneOffset() * 60000).toISOString().slice(0, 16); document.getElementById('meetingDate').value = local; }
            if (m.project_id) document.getElementById('meetingProject').value = m.project_id[0];
            const ps = document.getElementById('meetingParticipants');
            if (ps && m.participant_ids) { Array.from(ps.options).forEach(function(opt) { opt.selected = m.participant_ids.includes(parseInt(opt.value)); }); }
            // ✅ Restaure le type lors de l'édition
            setMeetingType(m.meeting_type || 'presentiel');
            const meetingForm = document.getElementById('meetingForm');
            meetingForm.setAttribute('data-edit-id', meetingId);
            meetingForm.style.display = 'block';
            const saveBtn = document.getElementById('saveMeetingBtn');
            if (saveBtn) saveBtn.textContent = 'Update Meeting';
            meetingForm.scrollIntoView({ behavior: 'smooth', block: 'center' });
        } catch(e) { console.error('❌ Edit error:', e); }
    };

    // ─── DONUT CHART ──────────────────────────────────────────────────────────────

    async function initDonutChart() {
    await new Promise(resolve => setTimeout(resolve, 300));

    const canvas = document.getElementById('ticketStatusDonut');
    if (!canvas) return;

    const recordId = getRecordIdFromURL();
    if (!recordId) return;

    try {
        const response = await fetch('/jira/dashboard/ticket_status_donut/' + recordId);
        const data = await response.json();

        if (!data || !data.counts || !data.counts.length) {
            console.log('No donut data');
            return;
        }

        // Mettre à jour la table
        const tbody = document.getElementById('legendTableBody');
        if (tbody) {
            tbody.innerHTML = data.data.map(function(item) {
                return '<tr>' +
                    '<td style="padding:8px;display:flex;align-items:center;gap:8px;">' +
                        '<div style="width:12px;height:12px;border-radius:50%;background:' + item.color + ';"></div>' +
                        item.label +
                    '</td>' +
                    '<td style="padding:8px;text-align:center;">' + item.count + '</td>' +
                    '<td style="padding:8px;text-align:center;">' + item.percentage + '%</td>' +
                '</tr>';
            }).join('');
        }

        // Total
        const totalEl = document.getElementById('totalIssues');
        if (totalEl) totalEl.textContent = data.total;

        // Détruire ancien chart
        if (window.donutChartInstance) {
            window.donutChartInstance.destroy();
            window.donutChartInstance = null;
        }

        // Créer le donut
        window.donutChartInstance = new Chart(canvas.getContext('2d'), {
            type: 'doughnut',
            data: {
                labels: data.labels,
                datasets: [{
                    data: data.counts,
                    backgroundColor: data.colors,
                    borderWidth: 2,
                    borderColor: '#fff',
                    hoverOffset: 8
                }]
            },
            options: {
                responsive: true,
                maintainAspectRatio: false,
                cutout: '65%',
                plugins: {
                    legend: { display: false },
                    tooltip: {
                        callbacks: {
                            label: function(c) {
                                return c.label + ': ' + c.parsed + ' tickets';
                            }
                        }
                    }
                }
            }
        });

    } catch(e) {
        console.error('❌ Donut chart error:', e);
    }
}

    // ─── TRIGGER RENDERS ──────────────────────────────────────────────────────

    function triggerRenders() {
        setupGlobalDelegation();

        Promise.all([
            renderDashboardChart(),
            loadVelocityProjects(),
            loadSprintReport(),
            loadMeetings([]),
            loadTeamActivity('week', null),
            loadProjectTimeline([]),
            initMeetingForm(),
        ]);

        initBurndown();

        const picker = document.getElementById('activityMonthPicker');
        if (picker && !picker.dataset.initialized) {
            picker.dataset.initialized = 'true';
            const now = new Date();
            picker.value = now.getFullYear() + '-' + String(now.getMonth() + 1).padStart(2, '0');
            picker.addEventListener('change', function() { loadTeamActivity('month', picker.value); });
        }

        setTimeout(function() {
            const picker = document.getElementById('activityMonthPicker');
            const now = new Date();
            const currentMonth = now.getFullYear() + '-' + String(now.getMonth() + 1).padStart(2, '0');
            if (picker) picker.value = currentMonth;
            loadTeamActivity('month', currentMonth);
            const btnWeek = document.getElementById('activityBtnWeek');
            const btnMonth = document.getElementById('activityBtnMonth');
            if (btnWeek) { btnWeek.style.borderColor = '#ddd'; btnWeek.style.background = 'white'; btnWeek.style.color = '#888'; }
            if (btnMonth) { btnMonth.style.borderColor = '#4f8ef7'; btnMonth.style.background = '#eef3ff'; btnMonth.style.color = '#4f8ef7'; }
            const activityField = document.querySelector('[name="activity_project_ids"]');
            if (activityField && !activityField.dataset.triggerObserved) {
                activityField.dataset.triggerObserved = 'true';
                new MutationObserver(function() {
                    const activePicker = document.getElementById('activityMonthPicker');
                    const activeMonth = activePicker ? activePicker.value : currentMonth;
                    const isMonth = document.getElementById('activityBtnMonth').style.borderColor === 'rgb(79, 142, 247)';
                    loadTeamActivity(isMonth ? 'month' : 'week', isMonth ? activeMonth : null);
                }).observe(activityField, { childList: true, subtree: true });
            }

            const cancelBtn = document.getElementById('cancelMeetingBtn');
            if (cancelBtn && !cancelBtn.dataset.bound) { cancelBtn.dataset.bound = 'true'; cancelBtn.addEventListener('click', function(e) { e.preventDefault(); e.stopImmediatePropagation(); const f = document.getElementById('meetingForm'); if (f) { f.removeAttribute('data-edit-id'); f.style.display = 'none'; } const sb = document.getElementById('saveMeetingBtn'); if (sb) sb.textContent = 'Save Meeting'; setMeetingType('presentiel'); }, true); }
            initBurndown();
            initDonutChart();
        }, 1200);

        console.log('✅ Renders triggered');
    }

    // ─── INIT ─────────────────────────────────────────────────────────────────

    // ✅ NOUVEAU CODE
setupGlobalDelegation();
let rendered = false;
let lastUrl = location.href;

function tryInit() {
    const hasCanvas = document.getElementById('teamVelocityChart')
                   || document.getElementById('projectsPieChart')
                   || document.getElementById('teamActivityChart')
                   || document.getElementById('meetingsList');
    if (hasCanvas && !rendered) {
        rendered = true;
        console.log('✅ Ready!');
        triggerRenders();
    }
}

// ✅ Reset rendered à chaque changement d'URL
new MutationObserver(function() {
    if (location.href !== lastUrl) {
        lastUrl = location.href;
        rendered = false;  // ← reset ici
        console.log('🔄 URL changed, reset rendered');
        setTimeout(tryInit, 500);  // ← délai pour laisser le DOM se charger
    }
    tryInit();
}).observe(document, { subtree: true, childList: true });

let attempts = 0;
const tryRender = setInterval(function() {
    attempts++;
    tryInit();
    if (rendered || attempts >= 20) clearInterval(tryRender);
}, 100);
})();