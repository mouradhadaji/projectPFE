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

    # KPIs - Computed Fields
    total_tickets = fields.Integer(
        string='Total Tickets',
        compute='_compute_ticket_stats',
        store=False
    )
    completed_tickets = fields.Integer(
        string='Completed Tickets',
        compute='_compute_ticket_stats',
        store=False
    )
    in_progress_tickets = fields.Integer(
        string='In Progress Tickets',
        compute='_compute_ticket_stats',
        store=False
    )
    completion_rate = fields.Float(
        string='Completion Rate (%)',
        compute='_compute_ticket_stats',
        store=False
    )

    # ─── Compute Ticket Stats ─────────────────────────────
    @api.depends('project_id', 'project_id.ticket_ids',
                 'project_id.ticket_ids.ticket_status')
    def _compute_ticket_stats(self):
        """Calculate ticket statistics"""
        for dashboard in self:
            if dashboard.project_id:
                tickets = dashboard.project_id.ticket_ids
                dashboard.total_tickets = len(tickets)
                dashboard.completed_tickets = len(
                    tickets.filtered(
                        lambda t: t.ticket_status in ('done', 'complete')))
                dashboard.in_progress_tickets = len(
                    tickets.filtered(
                        lambda t: t.ticket_status == 'in_progress'))
                if dashboard.total_tickets > 0:
                    dashboard.completion_rate = (
                        dashboard.completed_tickets / dashboard.total_tickets)
                else:
                    dashboard.completion_rate = 0.0
            else:
                dashboard.total_tickets = 0
                dashboard.completed_tickets = 0
                dashboard.in_progress_tickets = 0
                dashboard.completion_rate = 0.0

    # ─── Compute Sprint Health ────────────────────────────
    @api.depends('sprint_id', 'sprint_id.ticket_ids.ticket_status',
                 'sprint_id.ticket_ids.story_points')
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

            # ✅ Statuts corrects selon votre ticket.py
            done = tickets.filtered(
                lambda t: t.ticket_status in ('done', 'complete'))
            progress = tickets.filtered(
                lambda t: t.ticket_status == 'in_progress')
            todo = tickets.filtered(
                lambda t: t.ticket_status == 'draft')

            rec.done_points        = sum(done.mapped('story_points'))
            rec.in_progress_points = sum(progress.mapped('story_points'))
            rec.todo_points        = sum(todo.mapped('story_points'))
            rec.total_points       = (
                rec.done_points + rec.in_progress_points + rec.todo_points)

            rec.work_complete_percent = (
                rec.done_points / rec.total_points * 100
                if rec.total_points > 0 else 0.0)

            # ✅ start_date / end_date (noms corrects dans jira.sprint)
            start = rec.sprint_id.start_date
            end   = rec.sprint_id.end_date
            if start and end:
                total_days = (end - start).days or 1
                elapsed    = (today - start).days
                rec.days_left            = max((end - today).days, 0)
                rec.time_elapsed_percent = min(elapsed / total_days * 100, 100)
            else:
                rec.days_left            = 0
                rec.time_elapsed_percent = 0.0

            # ✅ priority '4' = Highest dans votre modèle
            rec.blocker_count = len(tickets.filtered(
                lambda t: t.priority == '4'
                and t.ticket_status not in ('done', 'complete')))
            rec.flagged_count = len(tickets.filtered(lambda t: t.is_flagged))

    # ─── Chart Data Methods ───────────────────────────────

    def get_tickets_by_status_chart_data(self):
        """Returns data for Tickets by Status chart (Pie/Doughnut)"""
        self.ensure_one()
        if not self.project_id:
            return {'labels': [], 'data': [], 'colors': []}

        tickets = self.project_id.ticket_ids
        status_counts = {
            'draft':       len(tickets.filtered(lambda t: t.ticket_status == 'draft')),
            'in_progress': len(tickets.filtered(lambda t: t.ticket_status == 'in_progress')),
            'done':        len(tickets.filtered(lambda t: t.ticket_status == 'done')),
            'complete':    len(tickets.filtered(lambda t: t.ticket_status == 'complete')),
        }
        color_map = {
            'draft':       '#ffc107',
            'in_progress': '#17a2b8',
            'done':        '#28a745',
            'complete':    '#2E4A8B',
        }
        label_map = {
            'draft':       'Draft',
            'in_progress': 'In Progress',
            'done':        'Done',
            'complete':    'Complete',
        }

        labels, data, colors = [], [], []
        for status, count in status_counts.items():
            if count > 0:
                labels.append(label_map[status])
                data.append(count)
                colors.append(color_map[status])
        return {'labels': labels, 'data': data, 'colors': colors}

    def get_tickets_by_type_chart_data(self):
        """Returns data for Tickets by Type chart (Bar chart)"""
        self.ensure_one()
        if not self.project_id:
            return {'labels': [], 'data': [], 'colors': []}

        tickets = self.project_id.ticket_ids
        type_counts = {
            'epic':    len(tickets.filtered(lambda t: t.ticket_type == 'epic')),
            'story':   len(tickets.filtered(lambda t: t.ticket_type == 'story')),
            'task':    len(tickets.filtered(lambda t: t.ticket_type == 'task')),
            'bug':     len(tickets.filtered(lambda t: t.ticket_type == 'bug')),
            'subtask': len(tickets.filtered(lambda t: t.ticket_type == 'subtask')),
        }
        color_map = {
            'epic': '#6f42c1', 'story': '#007bff',
            'task': '#28a745', 'bug': '#dc3545', 'subtask': '#fd7e14',
        }
        label_map = {
            'epic': 'Epic', 'story': 'Story',
            'task': 'Task', 'bug': 'Bug', 'subtask': 'Sub-task',
        }

        labels, data, colors = [], [], []
        for ticket_type, count in type_counts.items():
            if count > 0:
                labels.append(label_map[ticket_type])
                data.append(count)
                colors.append(color_map[ticket_type])
        return {'labels': labels, 'data': data, 'colors': colors}

    def get_tickets_by_priority_chart_data(self):
        """Returns data for Tickets by Priority chart (Horizontal Bar)"""
        self.ensure_one()
        if not self.project_id:
            return {'labels': [], 'data': [], 'colors': []}

        tickets = self.project_id.ticket_ids
        priority_counts = {
            '0': len(tickets.filtered(lambda t: t.priority == '0')),
            '1': len(tickets.filtered(lambda t: t.priority == '1')),
            '2': len(tickets.filtered(lambda t: t.priority == '2')),
            '3': len(tickets.filtered(lambda t: t.priority == '3')),
            '4': len(tickets.filtered(lambda t: t.priority == '4')),
        }
        color_map = {
            '0': '#6c757d', '1': '#17a2b8',
            '2': '#ffc107', '3': '#fd7e14', '4': '#dc3545',
        }
        label_map = {
            '0': 'Lowest', '1': 'Low',
            '2': 'Medium', '3': 'High', '4': 'Highest',
        }

        labels, data, colors = [], [], []
        for priority, count in priority_counts.items():
            if count > 0:
                labels.append(label_map[priority])
                data.append(count)
                colors.append(color_map[priority])
        return {'labels': labels, 'data': data, 'colors': colors}

    def get_burnup_chart_data(self):
        """Burnup Step Chart - Total Scope vs Completed Tickets over time"""
        self.ensure_one()
        if not self.project_id:
            return {'labels': [], 'completed': [], 'scope': []}

        tickets = self.project_id.ticket_ids.sorted('create_date')
        labels, completed_data, scope_data = [], [], []
        total_scope = len(tickets)
        cumulative_completed = 0

        for ticket in tickets:
            if ticket.ticket_status in ('done', 'complete'):
                cumulative_completed += 1
            labels.append(ticket.create_date.strftime('%Y-%m-%d'))
            completed_data.append(cumulative_completed)
            scope_data.append(total_scope)

        return {'labels': labels, 'completed': completed_data, 'scope': scope_data}

    def get_projects_pie_chart_data(self):
        """Returns data for projects pie chart"""
        self.ensure_one()
        projects = (self.project_ids
                    if self.project_ids
                    else self.env['jira.project'].search([]))
        labels, data = [], []
        colors = ['#FF6384', '#36A2EB', '#FFCE56', '#4BC0C0', '#9966FF', '#FF9F40']

        for project in projects:
            total = len(project.ticket_ids)
            completed = len(project.ticket_ids.filtered(
                lambda t: t.ticket_status in ('done', 'complete'))) if total > 0 else 0
            completion = (completed / total * 100) if total > 0 else 0.0
            labels.append(project.name)
            data.append(round(completion, 2))

        return {'labels': labels, 'data': data, 'colors': colors[:len(labels)]}

    def get_ticket_status_donut_data(self):
        """Returns data for ticket status donut chart with legend"""
        self.ensure_one()
        if self.project_ids:
            all_tickets = self.env['jira.ticket'].search([
                ('project_id', 'in', self.project_ids.ids)])
        else:
            all_tickets = self.env['jira.ticket'].search([])

        status_data = {}
        for ticket in all_tickets:
            status = ticket.ticket_status or 'unknown'
            status_data[status] = status_data.get(status, 0) + 1

        color_map = {
            'draft':       '#ffc107',
            'in_progress': '#FF9800',
            'done':        '#4CAF50',
            'complete':    '#2E4A8B',
        }
        label_map = {
            'draft':       'Draft',
            'in_progress': 'In Progress',
            'done':        'Done',
            'complete':    'Complete',
        }

        labels, counts, percentages, colors = [], [], [], []
        total = len(all_tickets)

        for status, count in status_data.items():
            labels.append(label_map.get(status, status.title()))
            counts.append(count)
            percentages.append(round(count / total * 100 if total > 0 else 0, 1))
            colors.append(color_map.get(status, '#999'))

        return {
            'labels': labels, 'data': counts,
            'percentages': percentages, 'colors': colors, 'total': total
        }

    def get_open_support_tickets_data(self):
        """Returns data for Open Support Tickets donut chart + table"""
        self.ensure_one()
        if self.project_ids:
            all_tickets = self.env['jira.ticket'].search([
                ('project_id', 'in', self.project_ids.ids)])
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
            count = len(all_tickets.filtered(
                lambda t, s=status['key']: t.ticket_status == s))
            if count > 0:
                result.append({
                    'label':      status['label'],
                    'color':      status['color'],
                    'count':      count,
                    'percentage': round(count / total * 100, 1) if total > 0 else 0.0,
                })

        return {
            'title':  'Open Support Tickets',
            'total':  total,
            'data':   result,
            'labels': [r['label'] for r in result],
            'counts': [r['count'] for r in result],
            'colors': [r['color'] for r in result],
        }

    # ─── Sprint Health Data for Widget ───────────────────
    def get_sprint_health_data(self):
        """Returns sprint health data for the dashboard widget"""
        self.ensure_one()
        assignees = (self.sprint_id.ticket_ids.mapped('assignee_id')
                     if self.sprint_id else [])
        return {
            'sprint_name':        self.sprint_id.name if self.sprint_id else '',
            'days_left':          self.days_left,
            'done_points':        self.done_points,
            'in_progress_points': self.in_progress_points,
            'todo_points':        self.todo_points,
            'total_points':       self.total_points,
            'work_complete':      round(self.work_complete_percent, 1),
            'time_elapsed':       round(self.time_elapsed_percent, 1),
            'blockers':           self.blocker_count,
            'flagged':            self.flagged_count,
            'assignees': [
                {
                    'id':       m.id,
                    'name':     m.name,
                    'initials': ''.join([n[0].upper() for n in m.name.split()[:2]])
                } for m in assignees
            ]
        }


def get_team_velocity_data(self):
    """Returns data for Team Velocity chart"""
    self.ensure_one()

    # ✅ Log pour déboguer
    import logging
    _logger = logging.getLogger(__name__)
    _logger.info(
        f"🔍 Getting velocity data for dashboard: {self.name}, project: {self.project_id.name if self.project_id else 'None'}")

    if not self.project_id:
        _logger.warning("⚠️ No project selected for velocity chart")
        return {
            'labels': [],
            'initial_scope': [],
            'final_scope': [],
            'completed': [],
            'avg_velocity': 0,
            'sprint_count': 0,
        }

    sprints = self.env['jira.sprint'].search([
        ('project_id', '=', self.project_id.id),
        ('state', 'in', ['active', 'completed'])
    ], order='start_date asc', limit=10)

    _logger.info(f"📊 Found {len(sprints)} sprints")

    labels = []
    initial_scope = []
    final_scope = []
    completed = []

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

        _logger.info(f"  Sprint {sprint.name}: {done_points}/{total_points} pts")

    # Average velocity
    avg = round(sum(completed) / len(completed), 1) if completed else 0

    result = {
        'labels': labels,
        'initial_scope': initial_scope,
        'final_scope': final_scope,
        'completed': completed,
        'avg_velocity': avg,
        'sprint_count': len(sprints),
    }

    _logger.info(f"✅ Velocity data: {result}")
    return result