# models/jira_dashboard.py
# -*- coding: utf-8 -*-
import json
import logging
from datetime import date, timedelta

from odoo import models, fields, api

_logger = logging.getLogger(__name__)


class JiraDashboard(models.Model):
    _name = 'jira.dashboard'
    _description = 'Jira Dashboard'

    name = fields.Char(string='Dashboard Name', required=True, default='My Dashboard')

    # ─── Relations ────────────────────────────────────────────
    project_id = fields.Many2one('jira.project', string='Project')
    project_ids = fields.Many2many(
        'jira.project',
        'jira_dashboard_project_rel',
        'dashboard_id',
        'project_id',
        string='Projects for Chart'
    )
    velocity_project_ids = fields.Many2many(
        'jira.project',
        'jira_dashboard_velocity_project_rel',
        'dashboard_id',
        'project_id',
        string='Velocity Projects'
    )
    activity_project_ids = fields.Many2many(
        'jira.project',
        'jira_dashboard_activity_project_rel',
        'dashboard_id',
        'project_id',
        string='Activity Projects'
    )

    # ─── Sprint Health Fields ─────────────────────────────────
    sprint_id = fields.Many2one('jira.sprint', string='Active Sprint')
    done_points = fields.Integer(compute='_compute_sprint_health', store=True)
    in_progress_points = fields.Integer(compute='_compute_sprint_health', store=True)
    todo_points = fields.Integer(compute='_compute_sprint_health', store=True)
    total_points = fields.Integer(compute='_compute_sprint_health', store=True)
    work_complete_percent = fields.Float(compute='_compute_sprint_health', store=True)
    time_elapsed_percent = fields.Float(compute='_compute_sprint_health', store=True)
    days_left = fields.Integer(compute='_compute_sprint_health', store=True)
    blocker_count = fields.Integer(compute='_compute_sprint_health', store=True)
    flagged_count = fields.Integer(compute='_compute_sprint_health', store=True)

    # ─── KPIs ─────────────────────────────────────────────────
    total_tickets = fields.Integer(
        string='Total Tickets', compute='_compute_ticket_stats', store=False
    )
    completed_tickets = fields.Integer(
        string='Completed Tickets', compute='_compute_ticket_stats', store=False
    )
    in_progress_tickets = fields.Integer(
        string='In Progress Tickets', compute='_compute_ticket_stats', store=False
    )
    completion_rate = fields.Float(
        string='Completion Rate (%)', compute='_compute_ticket_stats', store=False
    )

    # ═══════════════════════════════════════════════════════════
    # ─── PERFORMANCE ANALYZER FIELDS ──────────────────────────
    # ═══════════════════════════════════════════════════════════
    perf_project_id = fields.Many2one(
        'jira.project',
        string='Analyze Project',
    )
    perf_mode = fields.Selection([
        ('none', 'None'),
        ('project', 'Project'),
        ('team', 'Team'),
    ], default='none', string='Analysis Mode')
    perf_raw_result = fields.Text(
        string='Raw Result', default='{}'
    )
    perf_result_html = fields.Html(
        string='Performance Result',
        sanitize=False,
        compute='_compute_perf_result_html',
    )

    # ═══════════════════════════════════════════════════════════
    # ─── EXISTING COMPUTES ────────────────────────────────────
    # ═══════════════════════════════════════════════════════════

    @api.depends('project_id', 'project_id.ticket_ids', 'project_id.ticket_ids.ticket_status')
    def _compute_ticket_stats(self):
        for dashboard in self:
            if dashboard.project_id:
                tickets = dashboard.project_id.ticket_ids
                dashboard.total_tickets = len(tickets)
                dashboard.completed_tickets = len(
                    tickets.filtered(lambda t: t.ticket_status in ('done', 'complete'))
                )
                dashboard.in_progress_tickets = len(
                    tickets.filtered(lambda t: t.ticket_status == 'in_progress')
                )
                dashboard.completion_rate = (
                    (dashboard.completed_tickets / dashboard.total_tickets)
                    if dashboard.total_tickets > 0 else 0.0
                )
            else:
                dashboard.total_tickets = 0
                dashboard.completed_tickets = 0
                dashboard.in_progress_tickets = 0
                dashboard.completion_rate = 0.0

    @api.depends('sprint_id', 'sprint_id.ticket_ids.ticket_status',
                 'sprint_id.ticket_ids.story_points')
    def _compute_sprint_health(self):
        today = date.today()
        for rec in self:
            if not rec.sprint_id:
                rec.done_points = rec.in_progress_points = rec.todo_points = 0
                rec.total_points = rec.blocker_count = rec.flagged_count = 0
                rec.work_complete_percent = rec.time_elapsed_percent = 0.0
                rec.days_left = 0
                continue

            tickets = rec.sprint_id.ticket_ids
            done = tickets.filtered(lambda t: t.ticket_status in ('done', 'complete'))
            progress = tickets.filtered(lambda t: t.ticket_status == 'in_progress')
            todo = tickets.filtered(lambda t: t.ticket_status == 'draft')

            rec.done_points = sum(done.mapped('story_points'))
            rec.in_progress_points = sum(progress.mapped('story_points'))
            rec.todo_points = sum(todo.mapped('story_points'))
            rec.total_points = rec.done_points + rec.in_progress_points + rec.todo_points
            rec.work_complete_percent = (
                (rec.done_points / rec.total_points * 100)
                if rec.total_points > 0 else 0.0
            )

            start = rec.sprint_id.start_date
            end = rec.sprint_id.end_date
            if start and end:
                total_days = (end - start).days or 1
                elapsed = (today - start).days
                rec.days_left = max((end - today).days, 0)
                rec.time_elapsed_percent = min(elapsed / total_days * 100, 100)
            else:
                rec.days_left = 0
                rec.time_elapsed_percent = 0.0

            rec.blocker_count = len(tickets.filtered(
                lambda t: t.priority == '4' and t.ticket_status not in ('done', 'complete')
            ))
            rec.flagged_count = len(tickets.filtered(lambda t: t.is_flagged))

    # ═══════════════════════════════════════════════════════════
    # ─── PERFORMANCE ANALYZER ACTIONS ─────────────────────────
    # ═══════════════════════════════════════════════════════════

    def action_analyze_project(self):
        """Button: Analyze Project with ML."""
        self.ensure_one()
        if not self.perf_project_id:
            self.write({
                'perf_raw_result': json.dumps({
                    'error': 'Please select a project first'
                }),
                'perf_mode': 'none',
            })
            return

        try:
            from ..utils.performance_analyzer import PerformanceAnalyzer
            analyzer = PerformanceAnalyzer(self.env)
            result = analyzer.predict_project_health(self.perf_project_id.id)
        except ImportError:
            # Fallback if ML utils not available
            result = self._fallback_project_analysis(self.perf_project_id.id)
        except Exception as e:
            _logger.error("Project analysis failed: %s", str(e))
            result = {'error': f'Analysis failed: {str(e)}'}

        self.write({
            'perf_raw_result': json.dumps(result, default=str),
            'perf_mode': 'project',
        })

    def action_analyze_team(self):
        """Button: Full Team Report with ML."""
        self.ensure_one()
        if not self.perf_project_id:
            self.write({
                'perf_raw_result': json.dumps({
                    'error': 'Please select a project first'
                }),
                'perf_mode': 'none',
            })
            return

        try:
            from ..utils.performance_analyzer import PerformanceAnalyzer
            analyzer = PerformanceAnalyzer(self.env)
            result = analyzer.analyze_full_team(self.perf_project_id.id, days=30)
        except ImportError:
            result = self._fallback_team_analysis(self.perf_project_id.id)
        except Exception as e:
            _logger.error("Team analysis failed: %s", str(e))
            result = {'error': f'Analysis failed: {str(e)}'}

        self.write({
            'perf_raw_result': json.dumps(result, default=str),
            'perf_mode': 'team',
        })

    def action_clear_analysis(self):
        """Button: Clear analysis results."""
        self.ensure_one()
        self.write({
            'perf_raw_result': '{}',
            'perf_mode': 'none',
        })

    # ═══════════════════════════════════════════════════════════
    # ─── FALLBACK ANALYSIS (without ML) ───────────────────────
    # ═══════════════════════════════════════════════════════════

    def _fallback_project_analysis(self, project_id):
        """Basic analysis when ML utils are not available."""
        project = self.env['jira.project'].browse(project_id)
        if not project.exists():
            return {'error': 'Project not found'}

        tickets = project.ticket_ids
        total = len(tickets)
        if total == 0:
            return {'error': 'No tickets in this project'}

        done = tickets.filtered(lambda t: t.ticket_status in ('done', 'complete'))
        completion_rate = round(len(done) / total * 100, 1)
        total_pts = sum(tickets.mapped('story_points') or [0])
        done_pts = sum(done.mapped('story_points') or [0])

        if completion_rate >= 70:
            health = {'status': '🟢 Healthy', 'color': '#28a745'}
        elif completion_rate >= 40:
            health = {'status': '🟡 At Risk', 'color': '#ffc107'}
        else:
            health = {'status': '🔴 Critical', 'color': '#dc3545'}

        return {
            'project_name': project.name,
            'total_tickets': total,
            'done': len(done),
            'completion_rate': completion_rate,
            'total_points': total_pts,
            'done_points': done_pts,
            'health': health,
            'risks': [{'type': 'Basic Analysis', 'level': 'Info',
                       'detail': 'ML model not loaded — showing basic stats',
                       'color': '#17a2b8'}],
            'ml_health_prediction': None,
        }

    def _fallback_team_analysis(self, project_id):
        """Basic team analysis when ML utils are not available."""
        project = self.env['jira.project'].browse(project_id)
        if not project.exists():
            return {'error': 'Project not found'}

        tickets = self.env['jira.ticket'].search([
            ('project_id', '=', project_id),
        ])
        member_ids = list(set(
            m for m in tickets.mapped('assignee_id.id') if m
        ))

        members = []
        for mid in member_ids:
            member = self.env['res.users'].browse(mid)
            member_tickets = tickets.filtered(lambda t: t.assignee_id.id == mid)
            total = len(member_tickets)
            done = len(member_tickets.filtered(
                lambda t: t.ticket_status in ('done', 'complete')
            ))
            rate = round(done / total * 100, 1) if total else 0
            pts = sum(member_tickets.filtered(
                lambda t: t.ticket_status in ('done', 'complete')
            ).mapped('story_points') or [0])

            members.append({
                'member_name': member.name or 'Unknown',
                'member_id': mid,
                'performance_score': rate,
                'level': '✅ Good' if rate >= 70 else ('⚠️ Average' if rate >= 40 else '🔴 Low'),
                'ml_level': None,
                'ml_prediction': None,
                'metrics': {
                    'total_tickets': total,
                    'completion_rate': rate,
                    'completed_points': pts,
                    'in_progress_count': len(member_tickets.filtered(
                        lambda t: t.ticket_status == 'in_progress'
                    )),
                    'blocked_count': len(member_tickets.filtered(
                        lambda t: t.ticket_status == 'blocked'
                    )),
                },
                'issues': [],
                'recommendations': ['ML model not loaded — showing basic stats'],
            })

        members.sort(key=lambda x: x['performance_score'], reverse=True)

        return {
            'project_name': project.name,
            'team_size': len(members),
            'period_days': 30,
            'members': members,
            'ml_available': False,
        }

    # ═══════════════════════════════════════════════════════════
    # ─── COMPUTE HTML RESULT ──────────────────────────────────
    # ═══════════════════════════════════════════════════════════

    @api.depends('perf_raw_result', 'perf_mode')
    def _compute_perf_result_html(self):
        for record in self:
            try:
                data = json.loads(record.perf_raw_result or '{}')
            except (json.JSONDecodeError, TypeError):
                data = {}

            if not data or data.get('error'):
                error_msg = data.get('error', 'Select a project and click Analyze')
                record.perf_result_html = (
                    '<div style="text-align:center;padding:40px;color:#bbb;">'
                    '<div style="font-size:48px;margin-bottom:12px;">🤖</div>'
                    f'<div style="font-size:14px;">{error_msg}</div>'
                    '</div>'
                )
                continue

            if record.perf_mode == 'project':
                record.perf_result_html = record._render_project_html(data)
            elif record.perf_mode == 'team':
                record.perf_result_html = record._render_team_html(data)
            else:
                record.perf_result_html = (
                    '<div style="text-align:center;padding:40px;color:#bbb;">'
                    '<div style="font-size:48px;margin-bottom:12px;">🤖</div>'
                    '<div style="font-size:14px;">'
                    'Select a project and click Analyze to see AI insights'
                    '</div></div>'
                )

    # ─── Render Project HTML ──────────────────────────────────

    def _render_project_html(self, data):
        health = data.get('health', {})
        health_status = health.get('status', '-')
        health_color = health.get('color', '#333')

        ml_badge = ''
        ml_pred = data.get('ml_health_prediction')
        if ml_pred is not None:
            ml_badge = (
                '<div style="margin-top:8px;padding:4px 10px;background:#e8f5e9;'
                'border-radius:12px;font-size:11px;display:inline-block;">'
                f'🤖 ML: <strong>{ml_pred}</strong></div>'
            )

        html = f'''
        <div style="display:grid;grid-template-columns:repeat(4,1fr);gap:12px;margin-bottom:16px;">
            <div style="background:white;border-radius:8px;padding:16px;text-align:center;
                 border-left:4px solid #4f8ef7;box-shadow:0 1px 4px rgba(0,0,0,0.06);">
                <div style="font-size:2rem;font-weight:700;color:#4f8ef7;">
                    {data.get('total_tickets', 0)}</div>
                <div style="font-size:11px;color:#888;text-transform:uppercase;margin-top:4px;">
                    Total Tickets</div>
            </div>
            <div style="background:white;border-radius:8px;padding:16px;text-align:center;
                 border-left:4px solid #28a745;box-shadow:0 1px 4px rgba(0,0,0,0.06);">
                <div style="font-size:2rem;font-weight:700;color:#28a745;">
                    {data.get('completion_rate', 0)}%</div>
                <div style="font-size:11px;color:#888;text-transform:uppercase;margin-top:4px;">
                    Completion Rate</div>
            </div>
            <div style="background:white;border-radius:8px;padding:16px;text-align:center;
                 border-left:4px solid #f5c842;box-shadow:0 1px 4px rgba(0,0,0,0.06);">
                <div style="font-size:2rem;font-weight:700;color:#f5c842;">
                    {data.get('done_points', 0)}</div>
                <div style="font-size:11px;color:#888;text-transform:uppercase;margin-top:4px;">
                    Done Points</div>
            </div>
            <div style="background:white;border-radius:8px;padding:16px;text-align:center;
                 border-left:4px solid {health_color};box-shadow:0 1px 4px rgba(0,0,0,0.06);">
                <div style="font-size:1.2rem;font-weight:700;color:{health_color};">
                    {health_status}</div>
                <div style="font-size:11px;color:#888;text-transform:uppercase;margin-top:4px;">
                    Project Health</div>
                {ml_badge}
            </div>
        </div>
        '''

        # Risks
        risks = data.get('risks', [])
        if risks:
            html += (
                '<div style="background:white;border-radius:8px;padding:16px;'
                'box-shadow:0 1px 4px rgba(0,0,0,0.06);">'
                '<h4 style="margin:0 0 12px;color:#333;font-size:14px;">'
                '⚠️ Identified Risks</h4>'
            )
            for risk in risks:
                rc = risk.get('color', '#ccc')
                html += (
                    f'<div style="display:flex;align-items:center;gap:10px;padding:8px 12px;'
                    f'margin-bottom:6px;background:#fafafa;border-radius:6px;'
                    f'border-left:4px solid {rc};">'
                    f'<span style="font-weight:600;color:{rc};min-width:80px;">'
                    f'{risk.get("level", "")}</span>'
                    f'<span style="font-weight:600;">{risk.get("type", "")}</span>'
                    f'<span style="color:#666;font-size:12px;">'
                    f'— {risk.get("detail", "")}</span></div>'
                )
            html += '</div>'

        return html

    # ─── Render Team HTML ─────────────────────────────────────

    def _render_team_html(self, data):
        members = data.get('members', [])

        if not members:
            return (
                '<div style="text-align:center;padding:30px;color:#999;">'
                'No team members found</div>'
            )

        ml_available = data.get('ml_available', False)
        ml_badge = (
            '<span style="background:#e8f5e9;color:#2e7d32;padding:2px 8px;'
            'border-radius:10px;font-size:11px;">🤖 ML Active</span>'
            if ml_available else
            '<span style="background:#fff3e0;color:#e65100;padding:2px 8px;'
            'border-radius:10px;font-size:11px;">📊 Rule-based</span>'
        )

        html = (
            f'<div style="margin-bottom:12px;display:flex;justify-content:space-between;'
            f'align-items:center;">'
            f'<span style="color:#666;font-size:12px;">'
            f'{data.get("team_size", 0)} members · '
            f'Last {data.get("period_days", 30)} days</span>'
            f'{ml_badge}</div>'
        )

        medals = ['🥇', '🥈', '🥉']

        for index, member in enumerate(members):
            metrics = member.get('metrics', {})
            score = member.get('performance_score', 0)
            level = member.get('ml_level') or member.get('level', 'N/A')
            name = member.get('member_name', 'Unknown')

            if score >= 85:
                bc = '#28a745'
            elif score >= 70:
                bc = '#4f8ef7'
            elif score >= 50:
                bc = '#ffc107'
            elif score >= 30:
                bc = '#fd7e14'
            else:
                bc = '#dc3545'

            medal = medals[index] if index < 3 else f'#{index + 1}'
            bar_w = min(score, 100)

            html += f'''
            <div style="background:white;border-radius:8px;padding:16px;margin-bottom:10px;
                 box-shadow:0 1px 4px rgba(0,0,0,0.06);border-left:4px solid {bc};">
                <div style="display:flex;justify-content:space-between;align-items:center;
                     margin-bottom:10px;">
                    <div style="display:flex;align-items:center;gap:8px;">
                        <span style="font-size:18px;">{medal}</span>
                        <span style="font-weight:700;font-size:14px;color:#333;">{name}</span>
                    </div>
                    <div style="display:flex;align-items:center;gap:8px;">
                        <span style="font-size:13px;">{level}</span>
                        <span style="background:{bc};color:white;padding:2px 10px;
                             border-radius:12px;font-weight:700;font-size:13px;">{score}</span>
                    </div>
                </div>
                <div style="background:#f0f0f0;border-radius:4px;height:6px;margin-bottom:12px;">
                    <div style="background:{bc};height:100%;border-radius:4px;
                         width:{bar_w}%;"></div>
                </div>
                <div style="display:grid;grid-template-columns:repeat(5,1fr);gap:8px;
                     margin-bottom:10px;">
                    <div style="text-align:center;">
                        <div style="font-size:16px;font-weight:700;color:#4f8ef7;">
                            {metrics.get('total_tickets', 0)}</div>
                        <div style="font-size:10px;color:#999;">Tickets</div>
                    </div>
                    <div style="text-align:center;">
                        <div style="font-size:16px;font-weight:700;color:#28a745;">
                            {metrics.get('completion_rate', 0)}%</div>
                        <div style="font-size:10px;color:#999;">Done</div>
                    </div>
                    <div style="text-align:center;">
                        <div style="font-size:16px;font-weight:700;color:#f5c842;">
                            {metrics.get('completed_points', 0)}</div>
                        <div style="font-size:10px;color:#999;">Points</div>
                    </div>
                    <div style="text-align:center;">
                        <div style="font-size:16px;font-weight:700;color:#fd7e14;">
                            {metrics.get('in_progress_count', 0)}</div>
                        <div style="font-size:10px;color:#999;">In Progress</div>
                    </div>
                    <div style="text-align:center;">
                        <div style="font-size:16px;font-weight:700;color:#dc3545;">
                            {metrics.get('blocked_count', 0)}</div>
                        <div style="font-size:10px;color:#999;">Blocked</div>
                    </div>
                </div>
            '''

            # Issues
            issues = member.get('issues', [])
            if issues:
                html += '<div style="margin-top:6px;">'
                for issue in issues:
                    html += (
                        '<span style="display:inline-block;background:#fff3cd;color:#856404;'
                        f'padding:2px 8px;border-radius:10px;font-size:10px;margin:2px;">'
                        f'⚠️ {issue}</span>'
                    )
                html += '</div>'

            # Recommendations
            recs = member.get('recommendations', [])
            if recs:
                html += '<div style="margin-top:6px;">'
                for rec in recs:
                    html += (
                        '<span style="display:inline-block;background:#d4edda;color:#155724;'
                        f'padding:2px 8px;border-radius:10px;font-size:10px;margin:2px;">'
                        f'💡 {rec}</span>'
                    )
                html += '</div>'

            # ML prediction
            ml_pred = member.get('ml_prediction')
            if ml_pred is not None:
                ml_lvl = member.get('ml_level', '')
                html += (
                    '<div style="margin-top:8px;padding:6px 12px;background:#f3e5f5;'
                    'border-radius:6px;font-size:11px;color:#7b1fa2;">'
                    f'🤖 ML Prediction: <strong>{ml_pred}</strong>'
                    f'{f" → {ml_lvl}" if ml_lvl else ""}'
                    '</div>'
                )

            html += '</div>'

        return html

    # ═══════════════════════════════════════════════════════════
    # ─── EXISTING METHODS (unchanged) ─────────────────────────
    # ═══════════════════════════════════════════════════════════

    def get_open_support_tickets_data(self):
        self.ensure_one()
        if self.project_ids:
            all_tickets = self.env['jira.ticket'].search([
                ('project_id', 'in', self.project_ids.ids)
            ])
        elif self.project_id:
            all_tickets = self.project_id.ticket_ids
        else:
            all_tickets = self.env['jira.ticket'].search([])

        status_config = [
            {'key': 'draft',       'label': 'Draft',       'color': '#ffc107'},
            {'key': 'in_progress', 'label': 'In Progress', 'color': '#FF9800'},
            {'key': 'done',        'label': 'Done',        'color': '#4CAF50'},
            {'key': 'complete',    'label': 'Complete',     'color': '#2E4A8B'},
        ]

        total = len(all_tickets)
        result = []
        for status in status_config:
            count = len(all_tickets.filtered(
                lambda t, s=status['key']: t.ticket_status == s
            ))
            if count > 0:
                result.append({
                    'label': status['label'],
                    'color': status['color'],
                    'count': count,
                    'percentage': round(count / total * 100, 1) if total > 0 else 0.0,
                })

        return {
            'title': 'Open Support Tickets',
            'total': total,
            'data': result,
            'labels': [r['label'] for r in result],
            'counts': [r['count'] for r in result],
            'colors': [r['color'] for r in result],
        }

    def get_sprint_health_data(self):
        self.ensure_one()
        assignees = (
            self.sprint_id.ticket_ids.mapped('assignee_id')
            if self.sprint_id else []
        )
        return {
            'sprint_name': self.sprint_id.name if self.sprint_id else '',
            'days_left': self.days_left,
            'done_points': self.done_points,
            'in_progress_points': self.in_progress_points,
            'todo_points': self.todo_points,
            'total_points': self.total_points,
            'work_complete': round(self.work_complete_percent, 1),
            'time_elapsed': round(self.time_elapsed_percent, 1),
            'blockers': self.blocker_count,
            'flagged': self.flagged_count,
            'assignees': [
                {
                    'id': m.id,
                    'name': m.name,
                    'initials': ''.join(
                        [n[0].upper() for n in m.name.split()[:2]]
                    ),
                }
                for m in assignees
            ],
        }

    def get_team_velocity_data(self):
        self.ensure_one()
        if not self.project_id:
            return {
                'labels': [], 'initial_scope': [], 'final_scope': [],
                'completed': [], 'avg_velocity': 0, 'sprint_count': 0,
            }

        sprints = self.env['jira.sprint'].search([
            ('project_id', '=', self.project_id.id),
        ], order='start_date asc', limit=10)

        labels, initial_scope, final_scope, completed = [], [], [], []
        for sprint in sprints:
            tickets = sprint.ticket_ids
            total_pts = sum(tickets.mapped('story_points'))
            done_pts = sum(tickets.filtered(
                lambda t: t.ticket_status in ('done', 'complete')
            ).mapped('story_points'))
            labels.append(sprint.name)
            initial_scope.append(total_pts)
            final_scope.append(total_pts)
            completed.append(done_pts)

        avg = round(sum(completed) / len(completed), 1) if completed else 0
        return {
            'labels': labels, 'initial_scope': initial_scope,
            'final_scope': final_scope, 'completed': completed,
            'avg_velocity': avg, 'sprint_count': len(sprints),
        }

    @api.model
    def get_velocity_by_project(self, project_ids):
        if isinstance(project_ids, int):
            project_ids = [project_ids]
        elif isinstance(project_ids, list):
            project_ids = [int(p) for p in project_ids if p]

        sprints = self.env['jira.sprint'].search([
            ('project_id', 'in', project_ids),
        ], order='start_date asc', limit=20)

        labels, initial_scope, final_scope, completed = [], [], [], []
        for sprint in sprints:
            tickets = sprint.ticket_ids
            total_pts = sum(tickets.mapped('story_points'))
            done_pts = sum(tickets.filtered(
                lambda t: t.ticket_status in ('done', 'complete')
            ).mapped('story_points'))
            labels.append(sprint.name)
            initial_scope.append(total_pts)
            final_scope.append(total_pts)
            completed.append(done_pts)

        avg = round(sum(completed) / len(completed), 1) if completed else 0
        return {
            'labels': labels, 'initial_scope': initial_scope,
            'final_scope': final_scope, 'completed': completed,
            'avg_velocity': avg, 'sprint_count': len(sprints),
        }

    @api.model
    def get_sprint_report(self, sprint_id):
        sprint = self.env['jira.sprint'].browse(sprint_id)
        if not sprint:
            return {}

        tickets = self.env['jira.ticket'].search([('sprint_id', '=', sprint_id)])
        total_pts = sum(tickets.mapped('story_points') or [0])

        not_completed = tickets.filtered(
            lambda t: t.ticket_status not in ['done', 'complete']
        )
        issues = []
        for t in not_completed:
            issues.append({
                'name': t.name,
                'ticket_status': t.ticket_status or 'draft',
                'story_points': t.story_points or 0,
                'priority': t.priority or '2',
            })

        start = sprint.start_date
        end = sprint.end_date
        burndown = []
        if start and end:
            delta = (end - start).days + 1
            ideal_step = total_pts / max(delta - 1, 1)
            remaining = total_pts
            for i in range(delta):
                day = start + timedelta(days=i)
                burndown.append({
                    'date': day.strftime('%d %b'),
                    'ideal': round(total_pts - (ideal_step * i), 1),
                    'remaining': max(0, remaining - (total_pts / delta)),
                })

        return {
            'sprint_name': sprint.name,
            'start_date': start.strftime('%d/%m/%Y') if start else '',
            'end_date': end.strftime('%d/%m/%Y') if end else '',
            'total_points': total_pts,
            'completed_points': sum(
                tickets.filtered(
                    lambda t: t.ticket_status in ['done', 'complete']
                ).mapped('story_points') or [0]
            ),
            'burndown': burndown,
            'issues': issues,
        }

    @api.model
    def get_team_activity_by_member(self, project_ids, period='week', selected_month=None):
        import calendar

        if not project_ids:
            return {'labels': [], 'datasets': []}

        today = date.today()
        labels = []
        periods = []

        if period == 'week':
            for i in range(3, -1, -1):
                week_start = today - timedelta(days=today.weekday()) - timedelta(weeks=i)
                week_end = week_start + timedelta(days=6)
                labels.append('Week ' + str(4 - i))
                periods.append((week_start, week_end))
        else:
            if selected_month:
                year, month = map(int, selected_month.split('-'))
            else:
                year, month = today.year, today.month
            month_start = date(year, month, 1)
            month_end = date(year, month, calendar.monthrange(year, month)[1])
            current = month_start
            week_num = 1
            while current <= month_end and week_num <= 4:
                week_end_d = min(current + timedelta(days=6), month_end)
                labels.append('Week ' + str(week_num))
                periods.append((current, week_end_d))
                current += timedelta(days=7)
                week_num += 1

        projects = self.env['jira.project'].browse(project_ids)
        colors = [
            '#4f8ef7', '#70AD47', '#ED7D31', '#dc3545',
            '#9966FF', '#FF9F40', '#4BC0C0',
        ]
        datasets = []

        for idx, project in enumerate(projects):
            tickets = self.env['jira.ticket'].search([
                ('project_id', '=', project.id),
            ])
            _logger.info(
                'PROJECT: %s — tickets: %d', project.name, len(tickets)
            )
            for t in tickets:
                _logger.info(
                    '  ticket: %s | created: %s | points: %s',
                    t.name, t.created_date, t.story_points,
                )
            color = colors[idx % len(colors)]
            points = []
            for (p_start, p_end) in periods:
                pts = sum(
                    t.story_points or 0 for t in tickets
                    if t.created_date
                    and p_start <= t.created_date.date() <= p_end
                )
                points.append(pts)
            datasets.append({
                'label': project.name,
                'data': points,
                'color': color,
            })

        return {'labels': labels, 'datasets': datasets}

    @api.model
    def get_project_timeline(self, project_ids):
        if not project_ids:
            return []

        tickets = self.env['jira.ticket'].search([
            ('project_id', 'in', project_ids),
        ], order='updated_date desc', limit=20)

        colors = {
            'done': '#198754', 'complete': '#198754',
            'in_progress': '#0d6efd', 'in_review': '#fd7e14',
            'blocked': '#dc3545', 'draft': '#6c757d',
        }

        result = []
        for t in tickets:
            if not t.updated_date:
                continue
            status = (t.ticket_status or '').lower()
            result.append({
                'name': t.name,
                'project': t.project_id.name if t.project_id else '',
                'status': t.ticket_status or 'Draft',
                'color': colors.get(status, '#6c757d'),
                'date': t.updated_date.strftime('%d %b %Y'),
                'time': t.updated_date.strftime('%H:%M'),
            })
        return result