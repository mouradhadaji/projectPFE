# -*- coding: utf-8 -*-
from odoo import models, fields, api


class JiraDashboard(models.Model):
    _name = 'jira.dashboard'
    _description = 'Jira Dashboard'

    name = fields.Char(string='Dashboard Name', required=True, default='My Dashboard')

    # Relations
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

    # Sprint Health Fields
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

    # KPIs
    total_tickets = fields.Integer(string='Total Tickets', compute='_compute_ticket_stats', store=False)
    completed_tickets = fields.Integer(string='Completed Tickets', compute='_compute_ticket_stats', store=False)
    in_progress_tickets = fields.Integer(string='In Progress Tickets', compute='_compute_ticket_stats', store=False)
    completion_rate = fields.Float(string='Completion Rate (%)', compute='_compute_ticket_stats', store=False)

    @api.depends('project_id', 'project_id.ticket_ids', 'project_id.ticket_ids.ticket_status')
    def _compute_ticket_stats(self):
        for dashboard in self:
            if dashboard.project_id:
                tickets = dashboard.project_id.ticket_ids
                dashboard.total_tickets = len(tickets)
                dashboard.completed_tickets = len(tickets.filtered(lambda t: t.ticket_status in ('done', 'complete')))
                dashboard.in_progress_tickets = len(tickets.filtered(lambda t: t.ticket_status == 'in_progress'))
                dashboard.completion_rate = (dashboard.completed_tickets / dashboard.total_tickets) if dashboard.total_tickets > 0 else 0.0
            else:
                dashboard.total_tickets = 0
                dashboard.completed_tickets = 0
                dashboard.in_progress_tickets = 0
                dashboard.completion_rate = 0.0

    @api.depends('sprint_id', 'sprint_id.ticket_ids.ticket_status', 'sprint_id.ticket_ids.story_points')
    def _compute_sprint_health(self):
        from datetime import date
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

            rec.done_points        = sum(done.mapped('story_points'))
            rec.in_progress_points = sum(progress.mapped('story_points'))
            rec.todo_points        = sum(todo.mapped('story_points'))
            rec.total_points       = rec.done_points + rec.in_progress_points + rec.todo_points
            rec.work_complete_percent = (rec.done_points / rec.total_points * 100) if rec.total_points > 0 else 0.0

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

            rec.blocker_count = len(tickets.filtered(lambda t: t.priority == '4' and t.ticket_status not in ('done', 'complete')))
            rec.flagged_count = len(tickets.filtered(lambda t: t.is_flagged))

    def get_open_support_tickets_data(self):
        self.ensure_one()
        if self.project_ids:
            all_tickets = self.env['jira.ticket'].search([('project_id', 'in', self.project_ids.ids)])
        elif self.project_id:
            all_tickets = self.project_id.ticket_ids
        else:
            all_tickets = self.env['jira.ticket'].search([])

        status_config = [
            {'key': 'draft',       'label': 'Draft',       'color': '#ffc107'},
            {'key': 'in_progress', 'label': 'In Progress', 'color': '#FF9800'},
            {'key': 'done',        'label': 'Done',        'color': '#4CAF50'},
            {'key': 'complete',    'label': 'Complete',    'color': '#2E4A8B'},
        ]

        total = len(all_tickets)
        result = []
        for status in status_config:
            count = len(all_tickets.filtered(lambda t, s=status['key']: t.ticket_status == s))
            if count > 0:
                result.append({
                    'label': status['label'], 'color': status['color'],
                    'count': count, 'percentage': round(count / total * 100, 1) if total > 0 else 0.0,
                })

        return {
            'title': 'Open Support Tickets', 'total': total, 'data': result,
            'labels': [r['label'] for r in result],
            'counts': [r['count'] for r in result],
            'colors': [r['color'] for r in result],
        }

    def get_sprint_health_data(self):
        self.ensure_one()
        assignees = self.sprint_id.ticket_ids.mapped('assignee_id') if self.sprint_id else []
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
            'assignees': [{'id': m.id, 'name': m.name, 'initials': ''.join([n[0].upper() for n in m.name.split()[:2]])} for m in assignees]
        }

    def get_team_velocity_data(self):
        self.ensure_one()
        if not self.project_id:
            return {'labels': [], 'initial_scope': [], 'final_scope': [], 'completed': [], 'avg_velocity': 0, 'sprint_count': 0}

        sprints = self.env['jira.sprint'].search([('project_id', '=', self.project_id.id)], order='start_date asc', limit=10)
        labels, initial_scope, final_scope, completed = [], [], [], []

        for sprint in sprints:
            tickets = sprint.ticket_ids
            total_points = sum(tickets.mapped('story_points'))
            done_points = sum(tickets.filtered(lambda t: t.ticket_status in ('done', 'complete')).mapped('story_points'))
            labels.append(sprint.name)
            initial_scope.append(total_points)
            final_scope.append(total_points)
            completed.append(done_points)

        avg = round(sum(completed) / len(completed), 1) if completed else 0
        return {'labels': labels, 'initial_scope': initial_scope, 'final_scope': final_scope, 'completed': completed, 'avg_velocity': avg, 'sprint_count': len(sprints)}

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
            total_points = sum(tickets.mapped('story_points'))
            done_points = sum(tickets.filtered(
                lambda t: t.ticket_status in ('done', 'complete')
            ).mapped('story_points'))
            labels.append(sprint.name)
            initial_scope.append(total_points)
            final_scope.append(total_points)
            completed.append(done_points)

        avg = round(sum(completed) / len(completed), 1) if completed else 0
        return {
            'labels': labels,
            'initial_scope': initial_scope,
            'final_scope': final_scope,
            'completed': completed,
            'avg_velocity': avg,
            'sprint_count': len(sprints),
        }

    @api.model
    def get_sprint_report(self, sprint_id):
        sprint = self.env['jira.sprint'].browse(sprint_id)
        if not sprint:
            return {}

        tickets = self.env['jira.ticket'].search([('sprint_id', '=', sprint_id)])
        total_points = sum(tickets.mapped('story_points') or [0])

        not_completed = tickets.filtered(lambda t: t.ticket_status not in ['done', 'complete'])
        issues = []
        for t in not_completed:
            issues.append({
                'name': t.name,
                'ticket_status': t.ticket_status or 'draft',
                'story_points': t.story_points or 0,
                'priority': t.priority or '2',
            })

        from datetime import date, timedelta
        start = sprint.start_date
        end = sprint.end_date
        burndown = []
        if start and end:
            delta = (end - start).days + 1
            ideal_step = total_points / max(delta - 1, 1)
            remaining = total_points
            for i in range(delta):
                day = start + timedelta(days=i)
                burndown.append({
                    'date': day.strftime('%d %b'),
                    'ideal': round(total_points - (ideal_step * i), 1),
                    'remaining': max(0, remaining - (total_points / delta))
                })

        return {
            'sprint_name': sprint.name,
            'start_date': start.strftime('%d/%m/%Y') if start else '',
            'end_date': end.strftime('%d/%m/%Y') if end else '',
            'total_points': total_points,
            'completed_points': sum(
                tickets.filtered(lambda t: t.ticket_status in ['done', 'complete']).mapped('story_points') or [0]),
            'burndown': burndown,
            'issues': issues,
        }

    @api.model
    def get_team_activity_by_member(self, project_ids, period='week', selected_month=None):
        from datetime import date, timedelta
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
        colors = ['#4f8ef7', '#70AD47', '#ED7D31', '#dc3545', '#9966FF', '#FF9F40', '#4BC0C0']
        datasets = []

        for idx, project in enumerate(projects):
            tickets = self.env['jira.ticket'].search([
                ('project_id', '=', project.id),
            ])
            import logging
            _logger = logging.getLogger(__name__)
            _logger.info('PROJECT: %s — tickets: %d', project.name, len(tickets))
            for t in tickets:
                _logger.info('  ticket: %s | created: %s | points: %s', t.name, t.created_date, t.story_points)
            color = colors[idx % len(colors)]
            points = []
            for (p_start, p_end) in periods:
                pts = sum(
                    t.story_points or 0 for t in tickets
                    if t.created_date  and p_start <= t.created_date .date() <= p_end
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
            'blocked': '#dc3545', 'draft': '#6c757d'
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



