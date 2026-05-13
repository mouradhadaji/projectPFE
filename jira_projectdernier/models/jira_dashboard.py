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

    perf_project_id = fields.Many2one(
        'jira.project',
        string='Analyze Project',
    )
    perf_sprint_id = fields.Many2one(
        'jira.sprint',
        string='Sprint to Predict',
    )
    perf_ticket_description = fields.Text(
        string='Ticket Description for Classification',
    )
    perf_mode = fields.Selection([
        ('none', 'None'),
        ('project', 'Project'),
        ('team', 'Team'),
        ('sprint', 'Sprint'),
        ('nlp', 'NLP'),
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

            rec.work_complete_percent = max(0.0, min(100.0,
                                                     (rec.done_points / rec.total_points * 100)
                                                     if rec.total_points > 0 else 0.0
                                                     ))

            start = rec.sprint_id.start_date
            end = rec.sprint_id.end_date
            if start and end:
                total_days = max((end - start).days, 1)
                elapsed = (today - start).days
                rec.days_left = max((end - today).days, 0)
                rec.time_elapsed_percent = max(0.0, min(100.0,
                                                        elapsed / total_days * 100
                                                        ))
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

    def action_predict_sprint(self):
        """Button: Sprint velocity prediction."""
        self.ensure_one()
        if not self.perf_sprint_id:
            self.write({
                'perf_raw_result': json.dumps(
                    {'error': 'Please select a sprint first'}),
                'perf_mode': 'none',
            })
            return
        try:
            from ..utils.performance_analyzer import PerformanceAnalyzer
            analyzer = PerformanceAnalyzer(self.env)
            result = analyzer.predict_sprint_completion(self.perf_sprint_id.id)
        except ImportError:
            result = self._fallback_sprint_prediction(self.perf_sprint_id.id)
        except Exception as e:
            _logger.error("Sprint prediction failed: %s", str(e))
            result = {'error': f'Prediction failed: {str(e)}'}
        self.write({
            'perf_raw_result': json.dumps(result, default=str),
            'perf_mode': 'sprint',
        })

    def action_classify_ticket(self):
        """Button: NLP ticket classification."""
        self.ensure_one()
        if not self.perf_ticket_description:
            self.write({
                'perf_raw_result': json.dumps(
                    {'error': 'Please enter a ticket description'}),
                'perf_mode': 'none',
            })
            return
        try:
            from ..utils.performance_analyzer import PerformanceAnalyzer
            analyzer = PerformanceAnalyzer(self.env)
            result = analyzer.classify_ticket_nlp(self.perf_ticket_description)
        except ImportError:
            result = self._fallback_nlp_classify(self.perf_ticket_description)
        except Exception as e:
            _logger.error("NLP classification failed: %s", str(e))
            result = {'error': f'Classification failed: {str(e)}'}
        self.write({
            'perf_raw_result': json.dumps(result, default=str),
            'perf_mode': 'nlp',
        })

    def _fallback_sprint_prediction(self, sprint_id):
        """Basic sprint prediction without ML."""
        sprint = self.env['jira.sprint'].browse(sprint_id)
        if not sprint.exists():
            return {'error': 'Sprint not found'}
        tickets = sprint.ticket_ids
        total_pts = sum(tickets.mapped('story_points') or [0])
        done_pts = sum(tickets.filtered(
            lambda t: t.ticket_status in ('done', 'complete')
        ).mapped('story_points') or [0])
        prob = round(done_pts / total_pts * 100, 1) if total_pts else 0
        past = self.env['jira.sprint'].search([
            ('project_id', '=', sprint.project_id.id),
            ('state', '=', 'completed'),
        ], order='end_date desc', limit=6)
        velocities = []
        for s in past:
            v = sum(s.ticket_ids.filtered(
                lambda t: t.ticket_status in ('done', 'complete')
            ).mapped('story_points') or [0])
            velocities.append(v)
        avg_v = round(sum(velocities) / len(velocities), 1) if velocities else 0
        return {
            'sprint_name': sprint.name,
            'total_points': total_pts,
            'done_points': done_pts,
            'remaining_points': total_pts - done_pts,
            'predicted_velocity': {'value': avg_v, 'r2': None, 'confidence': 65},
            'completion_prob': prob,
            'anomalies': [],
            'velocities': list(reversed(velocities)),
        }

    def _fallback_nlp_classify(self, description):
        """Basic NLP classification without ML."""
        dl = description.lower()
        bug_kw = ['crash', 'error', 'fail', 'bug', 'broken', 'exception', 'not work', '500']
        epic_kw = ['epic', 'platform', 'migration', 'system', 'module', 'refactor']
        story_kw = ['as a user', 'as an admin', 'should', 'want to', 'need to']
        if any(k in dl for k in bug_kw):
            t_type = 'bug'
        elif any(k in dl for k in epic_kw):
            t_type = 'epic'
        elif any(k in dl for k in story_kw):
            t_type = 'story'
        else:
            t_type = 'task'
        if any(k in dl for k in ['critical', 'urgent', 'production', 'crash']):
            priority = '4'
        elif any(k in dl for k in ['error', 'fail', 'broken', 'important']):
            priority = '3'
        elif any(k in dl for k in ['minor', 'low', 'cosmetic', 'nice']):
            priority = '1'
        else:
            priority = '2'
        words = len(description.split())
        pts = 8 if any(k in dl for k in ['integrate', 'migrate', 'refactor', 'architecture']) \
            else 1 if any(k in dl for k in ['fix typo', 'rename', 'add field']) \
            else 5 if words > 50 else 3 if words > 20 else 2
        return {
            'ticket_type': t_type,
            'priority': priority,
            'story_points': pts,
            'confidence': 65.0,
            'type_proba': {t_type: 65.0},
            'top_features': [],
            'similar_tickets': [],
            'ml_used': False,
        }

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
            elif record.perf_mode == 'sprint':
                record.perf_result_html = record._render_sprint_html(data)
            elif record.perf_mode == 'nlp':
                record.perf_result_html = record._render_nlp_html(data)
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

    def _render_sprint_html(self, data):
        pred = data.get('predicted_velocity') or {}
        prob = data.get('completion_prob', 0)
        pc = '#28a745' if prob >= 70 else '#ffc107' if prob >= 50 else '#dc3545'
        anom = data.get('anomalies', [])
        ac = {'danger': '#dc3545', 'warning': '#ffc107', 'info': '#17a2b8'}
        ab = {'danger': '#fff5f5', 'warning': '#fffbe6', 'info': '#e8f4fd'}

        html = f'''
        <div style="display:grid;grid-template-columns:repeat(3,1fr);
                    gap:12px;margin-bottom:16px;">
            <div style="background:white;border-radius:8px;padding:16px;
                        text-align:center;border-left:4px solid #534AB7;
                        box-shadow:0 1px 4px rgba(0,0,0,0.06);">
                <div style="font-size:2rem;font-weight:700;color:#534AB7;">
                    {data.get('total_points', 0)}</div>
                <div style="font-size:11px;color:#888;
                            text-transform:uppercase;margin-top:4px;">
                    Total Points</div>
            </div>
            <div style="background:white;border-radius:8px;padding:16px;
                        text-align:center;border-left:4px solid {pc};
                        box-shadow:0 1px 4px rgba(0,0,0,0.06);">
                <div style="font-size:2rem;font-weight:700;color:{pc};">
                    {prob}%</div>
                <div style="font-size:11px;color:#888;
                            text-transform:uppercase;margin-top:4px;">
                    Completion Prob</div>
            </div>
            <div style="background:white;border-radius:8px;padding:16px;
                        text-align:center;border-left:4px solid #28a745;
                        box-shadow:0 1px 4px rgba(0,0,0,0.06);">
                <div style="font-size:2rem;font-weight:700;color:#28a745;">
                    {pred.get('value', '-')}</div>
                <div style="font-size:11px;color:#888;
                            text-transform:uppercase;margin-top:4px;">
                    Predicted Velocity</div>
            </div>
        </div>'''

        vels = data.get('velocities', [])
        if vels:
            max_v = max(vels + [pred.get('value', 0)], default=1) or 1
            html += (
                '<div style="background:white;border-radius:8px;padding:16px;'
                'margin-bottom:12px;box-shadow:0 1px 4px rgba(0,0,0,0.06);">'
                '<div style="font-size:11px;font-weight:600;color:#888;'
                'text-transform:uppercase;letter-spacing:0.6px;margin-bottom:12px;">'
                'Velocity History (Linear Regression)</div>'
                '<div style="display:flex;align-items:flex-end;gap:6px;height:80px;">'
            )
            for i, v in enumerate(vels):
                h_pct = round(v / max_v * 100)
                html += (
                    f'<div style="flex:1;display:flex;flex-direction:column;'
                    f'align-items:center;gap:4px;">'
                    f'<div style="font-size:10px;color:#888;">{v}</div>'
                    f'<div style="width:100%;height:{h_pct}%;background:#534AB7;'
                    f'border-radius:3px 3px 0 0;min-height:4px;"></div>'
                    f'<div style="font-size:9px;color:#aaa;">S{i + 1}</div></div>'
                )
            pv = pred.get('value', 0)
            if pv:
                ph = round(pv / max_v * 100)
                html += (
                    f'<div style="flex:1;display:flex;flex-direction:column;'
                    f'align-items:center;gap:4px;">'
                    f'<div style="font-size:10px;color:#28a745;font-weight:600;">{pv}</div>'
                    f'<div style="width:100%;height:{ph}%;background:#28a745;'
                    f'border-radius:3px 3px 0 0;min-height:4px;'
                    f'border:2px dashed #1a7a3e;"></div>'
                    f'<div style="font-size:9px;color:#28a745;">Pred</div></div>'
                )
            html += '</div></div>'

        if anom:
            html += (
                '<div style="background:white;border-radius:8px;padding:16px;'
                'box-shadow:0 1px 4px rgba(0,0,0,0.06);">'
                '<div style="font-size:11px;font-weight:600;color:#888;'
                'text-transform:uppercase;letter-spacing:0.6px;margin-bottom:10px;">'
                'Anomaly Detection</div>'
            )
            for a in anom:
                lvl = a.get('level', 'warning')
                html += (
                    f'<div style="padding:8px 12px;border-radius:6px;'
                    f'margin-bottom:6px;font-size:12px;'
                    f'background:{ab.get(lvl, "#fffbe6")};'
                    f'border-left:4px solid {ac.get(lvl, "#ffc107")};'
                    f'color:{ac.get(lvl, "#856404")}">'
                    f'{a.get("message", "")}</div>'
                )
            html += '</div>'

        return html

    def _render_nlp_html(self, data):
        tc = {'bug': '#dc3545', 'epic': '#534AB7', 'story': '#185FA5', 'task': '#28a745'}
        tb = {'bug': '#fff5f5', 'epic': '#EEEDFE', 'story': '#E6F1FB', 'task': '#f0fff4'}
        pl = {'4': 'Highest', '3': 'High', '2': 'Medium', '1': 'Low', '0': 'Lowest'}
        pc = {'4': '#dc3545', '3': '#fd7e14', '2': '#28a745', '1': '#17a2b8', '0': '#6c757d'}
        pb = {'4': '#fff5f5', '3': '#fff3cd', '2': '#f0fff4', '1': '#e8f4fd', '0': '#f8f9fa'}
        t = data.get('ticket_type', 'task')
        prio = data.get('priority', '2')
        conf = data.get('confidence', 0)
        pts = data.get('story_points', 2)
        tprob = data.get('type_proba', {})
        sim = data.get('similar_tickets', [])
        sprint_sug = data.get('sprint_suggestion')

        html = f'''
        <div style="display:grid;grid-template-columns:1fr 1fr;
                    gap:12px;margin-bottom:12px;">
            <div style="background:white;border-radius:8px;padding:16px;
                        box-shadow:0 1px 4px rgba(0,0,0,0.06);">
                <div style="display:flex;justify-content:space-between;
                            align-items:center;margin-bottom:12px;">
                    <div style="font-size:11px;font-weight:600;color:#888;
                                text-transform:uppercase;letter-spacing:0.6px;">
                        ML Prediction</div>
                    <span style="background:#e8f5e9;color:#2e7d32;
                                 padding:2px 10px;border-radius:999px;
                                 font-size:11px;font-weight:500;">
                        Confidence {conf}%</span>
                </div>'''

        rows = [
            ('Type',
             f'<span style="padding:2px 10px;border-radius:999px;font-size:12px;font-weight:600;background:{tb.get(t, "#f8f9fa")};color:{tc.get(t, "#333")}">{t}</span>'),
            ('Priority',
             f'<span style="padding:2px 10px;border-radius:999px;font-size:12px;font-weight:600;background:{pb.get(prio, "#f8f9fa")};color:{pc.get(prio, "#333")}">{pl.get(prio, "Medium")}</span>'),
            ('Story points',
             f'<span style="padding:2px 10px;border-radius:999px;font-size:12px;font-weight:600;background:#E6F1FB;color:#185FA5">{pts} pts</span>'),
            ('Sprint',
             f'<span style="padding:2px 10px;border-radius:999px;font-size:12px;font-weight:600;background:#f0fff4;color:#28a745">{sprint_sug["sprint_name"] if sprint_sug else "Current sprint"}</span>'),
        ]
        for label, val in rows:
            html += (
                f'<div style="display:flex;justify-content:space-between;'
                f'align-items:center;padding:7px 0;'
                f'border-bottom:1px solid #f0f0f0;">'
                f'<span style="font-size:12px;color:#666;">{label}</span>'
                f'{val}</div>'
            )
        html += '</div>'

        if tprob:
            html += (
                '<div style="background:white;border-radius:8px;padding:16px;'
                'box-shadow:0 1px 4px rgba(0,0,0,0.06);">'
                '<div style="font-size:11px;font-weight:600;color:#888;'
                'text-transform:uppercase;letter-spacing:0.6px;margin-bottom:10px;">'
                'Confidence by class</div>'
            )
            for cls, pct in tprob.items():
                cc = tc.get(cls, '#888')
                html += (
                    f'<div style="margin-bottom:8px;">'
                    f'<div style="display:flex;justify-content:space-between;'
                    f'font-size:12px;margin-bottom:3px;">'
                    f'<span style="color:#555;">{cls}</span>'
                    f'<span style="font-weight:600;color:{cc};">{pct}%</span></div>'
                    f'<div style="height:5px;border-radius:3px;background:#f0f0f0;">'
                    f'<div style="height:100%;border-radius:3px;background:{cc};'
                    f'width:{min(pct, 100)}%;transition:width .5s ease;"></div>'
                    f'</div></div>'
                )
            html += '</div></div>'
        else:
            html += '</div>'

        if sim:
            html += (
                '<div style="background:white;border-radius:8px;padding:16px;'
                'margin-top:12px;box-shadow:0 1px 4px rgba(0,0,0,0.06);">'
                '<div style="font-size:11px;font-weight:600;color:#888;'
                'text-transform:uppercase;letter-spacing:0.6px;margin-bottom:10px;">'
                'Similar tickets</div>'
            )
            for s in sim:
                sp = round((s.get('similarity', 0)) * 100)
                sc = '#28a745' if sp > 70 else '#ffc107' if sp > 40 else '#888'
                html += (
                    f'<div style="display:flex;align-items:center;gap:10px;'
                    f'padding:8px 0;border-bottom:1px solid #f5f5f5;">'
                    f'<div style="width:36px;text-align:center;font-size:12px;'
                    f'font-weight:600;color:{sc};">{sp}%</div>'
                    f'<div style="width:3px;height:32px;border-radius:2px;'
                    f'background:{sc};"></div>'
                    f'<div><div style="font-size:12px;color:#333;">'
                    f'{s.get("name", "")}</div>'
                    f'<div style="font-size:10px;color:#888;margin-top:2px;">'
                    f'{s.get("type", "task")} · {s.get("status", "")}</div>'
                    f'</div></div>'
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
            total_pts = sum(tickets.mapped('story_points') or [0])
            done_pts = sum(tickets.filtered(
                lambda t: t.ticket_status in ('done', 'complete')
            ).mapped('story_points') or [0])

            # ✅ Ignorer les sprints vides OU sans story points
            if not tickets or total_pts == 0:
                continue

            labels.append(sprint.name)
            initial_scope.append(total_pts)
            final_scope.append(total_pts)
            completed.append(done_pts)

        avg = round(sum(completed) / len(completed), 1) if completed else 0
        return {
            'labels': labels,
            'initial_scope': initial_scope,
            'final_scope': final_scope,
            'completed': completed,
            'avg_velocity': avg,
            'sprint_count': len(labels),
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
            for i in range(11, -1, -1):
                week_start = today - timedelta(days=today.weekday()) - timedelta(weeks=i)
                week_end = week_start + timedelta(days=6)
                if i == 0:
                    labels.append('This week')
                elif i == 1:
                    labels.append('Last week')
                else:
                    labels.append(week_start.strftime('%d %b'))
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
            while current <= month_end and week_num <= 5:
                week_end_d = min(current + timedelta(days=6), month_end)
                labels.append('Week ' + str(week_num))
                periods.append((current, week_end_d))
                current += timedelta(days=7)
                week_num += 1

        projects = self.env['jira.project'].browse(project_ids)
        colors = ['#4f8ef7', '#70AD47', '#ED7D31', '#dc3545', '#9966FF', '#FF9F40', '#4BC0C0']
        datasets = []

        for idx, project in enumerate(projects):
            tickets = self.env['jira.ticket'].search([('project_id', '=', project.id)])
            color = colors[idx % len(colors)]
            points = []

            for (p_start, p_end) in periods:
                pts = 0
                for t in tickets:
                    # Essayer created_date, write_date, et la date du sprint
                    ticket_date = None

                    # 1. created_date
                    if t.created_date:
                        try:
                            ticket_date = t.created_date.date() if hasattr(t.created_date, 'date') else t.created_date
                        except Exception:
                            pass

                    # 2. write_date si pas de created_date
                    if not ticket_date and t.write_date:
                        try:
                            ticket_date = t.write_date.date() if hasattr(t.write_date, 'date') else t.write_date
                        except Exception:
                            pass

                    # 3. Date du sprint comme dernier recours
                    if not ticket_date and t.sprint_id and t.sprint_id.end_date:
                        ticket_date = t.sprint_id.end_date

                    if ticket_date and p_start <= ticket_date <= p_end:
                        pts += t.story_points or 1

                points.append(pts)

            # Si tous les points sont 0, distribuer uniformément pour la visibilité
            if all(p == 0 for p in points) and tickets:
                total_pts = sum(t.story_points or 1 for t in tickets)
                points[-1] = total_pts  # Mettre tout dans "This week" comme fallback

            _logger.info("📊 Project=%s | points=%s | tickets=%s", project.name, points, len(tickets))

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

    @api.model
    def get_cfd_data(self, project_ids):
        """Retourne les données CFD réelles basées sur l'historique."""
        from datetime import date, timedelta, datetime

        if not project_ids:
            return {'labels': [], 'datasets': []}

        today = date.today()
        labels = []
        weeks = []
        for i in range(9, -1, -1):
            d = today - timedelta(weeks=i)
            if i == 0:
                labels.append("Aujourd'hui")
            else:
                labels.append(d.strftime('%d %b'))
            weeks.append(d)

        statuses = ['draft', 'in_progress', 'in_review', 'blocked', 'done', 'complete']
        status_labels = {
            'draft': 'To Do',
            'in_progress': 'In Progress',
            'in_review': 'In Review',
            'blocked': 'Blocked',
            'done': 'Done',
            'complete': 'Complete',
        }
        status_colors = {
            'draft': '#AFA9EC',
            'in_progress': '#4472C4',
            'in_review': '#ED7D31',
            'blocked': '#dc3545',
            'done': '#70AD47',
            'complete': '#28a745',
        }

        tickets = self.env['jira.ticket'].search([
            ('project_id', 'in', project_ids)
        ])

        datasets = []
        for status in statuses:
            data = []
            for week_date in weeks:
                week_end = datetime.combine(week_date, datetime.max.time())
                count = 0
                for ticket in tickets:
                    # Chercher le dernier changement avant cette date
                    history = self.env['jira.ticket.history'].search([
                        ('ticket_id', '=', ticket.id),
                        ('change_date', '<=', week_end),
                    ], order='change_date desc', limit=1)

                    if history:
                        ticket_status_at_date = history.new_status
                    else:
                        # Pas d'historique = statut initial draft
                        created = ticket.created_date or ticket.write_date
                        if created:
                            created_d = created.date() if hasattr(
                                created, 'date') else created
                            if created_d <= week_date:
                                ticket_status_at_date = 'draft'
                            else:
                                continue
                        else:
                            ticket_status_at_date = ticket.ticket_status

                    if ticket_status_at_date == status:
                        count += 1

                data.append(count)

            if any(d > 0 for d in data):
                datasets.append({
                    'label': status_labels[status],
                    'data': data,
                    'color': status_colors[status],
                })

        return {'labels': labels, 'datasets': datasets}

    @api.model
    def generate_initial_history(self):
        """Génère un historique initial pour les tickets existants."""
        from datetime import datetime, timedelta
        import random

        tickets = self.env['jira.ticket'].search([])
        _logger.info("Génération historique pour %s tickets...", len(tickets))

        for ticket in tickets:
            existing = self.env['jira.ticket.history'].search([
                ('ticket_id', '=', ticket.id)
            ], limit=1)
            if existing:
                continue

            start_date = ticket.created_date or ticket.write_date
            if not start_date:
                start_date = datetime.now() - timedelta(days=60)

            status_path = {
                'draft': ['draft'],
                'in_progress': ['draft', 'in_progress'],
                'in_review': ['draft', 'in_progress', 'in_review'],
                'blocked': ['draft', 'in_progress', 'blocked'],
                'done': ['draft', 'in_progress', 'in_review', 'done'],
                'complete': ['draft', 'in_progress', 'in_review', 'done', 'complete'],
            }.get(ticket.ticket_status, ['draft'])

            total_days = (datetime.now() - start_date).days or 1
            step_days = total_days / max(len(status_path), 1)

            prev_status = None
            for i, status in enumerate(status_path):
                change_date = start_date + timedelta(days=i * step_days)
                change_date += timedelta(hours=random.randint(0, 23))
                self.env['jira.ticket.history'].create({
                    'ticket_id': ticket.id,
                    'old_status': prev_status,
                    'new_status': status,
                    'change_date': change_date,
                    'user_id': self.env.user.id,
                })
                prev_status = status

        _logger.info("✅ Historique généré !")
        return True