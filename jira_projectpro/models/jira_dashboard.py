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

    @api.depends('project_id', 'project_id.ticket_ids', 'project_id.ticket_ids.ticket_status')
    def _compute_ticket_stats(self):
        """Calculate ticket statistics"""
        for dashboard in self:
            if dashboard.project_id:
                tickets = dashboard.project_id.ticket_ids
                dashboard.total_tickets = len(tickets)
                dashboard.completed_tickets = len(tickets.filtered(lambda t: t.ticket_status == 'complete'))
                dashboard.in_progress_tickets = len(tickets.filtered(lambda t: t.ticket_status == 'in_progress'))

                # Completion rate
                if dashboard.total_tickets > 0:
                    dashboard.completion_rate = (dashboard.completed_tickets / dashboard.total_tickets)
                else:
                    dashboard.completion_rate = 0.0
            else:
                dashboard.total_tickets = 0
                dashboard.completed_tickets = 0
                dashboard.in_progress_tickets = 0
                dashboard.completion_rate = 0.0

    # CHART DATA METHODS (NEW - Phase 2)
    # ========================================

    def get_tickets_by_status_chart_data(self):
        """
        Returns data for Tickets by Status chart (Pie/Doughnut)
        Usage: For displaying ticket distribution by status
        """
        self.ensure_one()

        if not self.project_id:
            return {
                'labels': [],
                'data': [],
                'colors': []
            }

        tickets = self.project_id.ticket_ids

        # Count tickets by status
        status_counts = {
            'to_do': len(tickets.filtered(lambda t: t.ticket_status == 'to_do')),
            'in_progress': len(tickets.filtered(lambda t: t.ticket_status == 'in_progress')),
            'complete': len(tickets.filtered(lambda t: t.ticket_status == 'complete')),
        }

        # Prepare data for chart
        labels = []
        data = []
        colors = []

        color_map = {
            'to_do': '#ffc107',  # Yellow
            'in_progress': '#17a2b8',  # Blue
            'complete': '#28a745',  # Green
        }

        label_map = {
            'to_do': 'To Do',
            'in_progress': 'In Progress',
            'complete': 'Complete',
        }

        # Filter out statuses with zero tickets
        for status, count in status_counts.items():
            if count > 0:
                labels.append(label_map[status])
                data.append(count)
                colors.append(color_map[status])

        return {
            'labels': labels,
            'data': data,
            'colors': colors
        }

    def get_tickets_by_type_chart_data(self):
        """
        Returns data for Tickets by Type chart (Bar chart)
        Usage: For displaying ticket distribution by type
        """
        self.ensure_one()

        if not self.project_id:
            return {
                'labels': [],
                'data': [],
                'colors': []
            }

        tickets = self.project_id.ticket_ids

        # Count tickets by type
        type_counts = {
            'epic': len(tickets.filtered(lambda t: t.ticket_type == 'epic')),
            'story': len(tickets.filtered(lambda t: t.ticket_type == 'story')),
            'task': len(tickets.filtered(lambda t: t.ticket_type == 'task')),
            'bug': len(tickets.filtered(lambda t: t.ticket_type == 'bug')),
        }

        # Prepare data for chart
        labels = []
        data = []
        colors = []

        color_map = {
            'epic': '#6f42c1',  # Purple
            'story': '#007bff',  # Blue
            'task': '#28a745',  # Green
            'bug': '#dc3545',  # Red
        }

        label_map = {
            'epic': 'Epic',
            'story': 'Story',
            'task': 'Task',
            'bug': 'Bug',
        }

        # Filter out types with zero tickets
        for ticket_type, count in type_counts.items():
            if count > 0:
                labels.append(label_map[ticket_type])
                data.append(count)
                colors.append(color_map[ticket_type])

        return {
            'labels': labels,
            'data': data,
            'colors': colors
        }

    def get_tickets_by_priority_chart_data(self):
        """
        Returns data for Tickets by Priority chart (Horizontal Bar)
        Usage: For displaying ticket distribution by priority
        """
        self.ensure_one()

        if not self.project_id:
            return {
                'labels': [],
                'data': [],
                'colors': []
            }

        tickets = self.project_id.ticket_ids

        # Count tickets by priority
        priority_counts = {
            '0': len(tickets.filtered(lambda t: t.priority == '0')),  # Low
            '1': len(tickets.filtered(lambda t: t.priority == '1')),  # Normal
            '2': len(tickets.filtered(lambda t: t.priority == '2')),  # High
            '3': len(tickets.filtered(lambda t: t.priority == '3')),  # Critical
        }

        # Prepare data for chart
        labels = []
        data = []
        colors = []

        color_map = {
            '0': '#6c757d',  # Gray - Low
            '1': '#007bff',  # Blue - Normal
            '2': '#ffc107',  # Yellow - High
            '3': '#dc3545',  # Red - Critical
        }

        label_map = {
            '0': 'Low',
            '1': 'Normal',
            '2': 'High',
            '3': 'Critical',
        }

        # Filter out priorities with zero tickets
        for priority, count in priority_counts.items():
            if count > 0:
                labels.append(label_map[priority])
                data.append(count)
                colors.append(color_map[priority])

        return {
            'labels': labels,
            'data': data,
            'colors': colors
        }

    def get_burnup_chart_data(self):
        """
        Burnup Step Chart Data
        Shows Total Scope vs Completed Tickets over time
        """
        self.ensure_one()

        if not self.project_id:
            return {
                'labels': [],
                'completed': [],
                'scope': []
            }

        tickets = self.project_id.ticket_ids.sorted('create_date')

        labels = []
        completed_data = []
        scope_data = []

        total_scope = len(tickets)
        cumulative_completed = 0

        for ticket in tickets:
            if ticket.ticket_status == 'complete':
                cumulative_completed += 1

            labels.append(ticket.create_date.strftime('%Y-%m-%d'))
            completed_data.append(cumulative_completed)
            scope_data.append(total_scope)

        return {
            'labels': labels,
            'completed': completed_data,
            'scope': scope_data
        }


    def get_projects_pie_chart_data(self):
        """Returns data for projects pie chart"""
        self.ensure_one()

        projects = self.project_ids if self.project_ids else self.env['jira.project'].search([])

        labels = []
        data = []
        colors = ['#FF6384', '#36A2EB', '#FFCE56', '#4BC0C0', '#9966FF', '#FF9F40']

        for project in projects:
            total = len(project.ticket_ids)
            if total > 0:
                completed = len(project.ticket_ids.filtered(lambda t: t.ticket_status == 'complete'))
                completion = (completed / total) * 100
            else:
                completion = 0.0

            labels.append(project.name)
            data.append(round(completion, 2))

        return {
            'labels': labels,
            'data': data,
            'colors': colors[:len(labels)]
        }

    def get_ticket_status_donut_data(self):
        """Returns data for ticket status donut chart with legend"""
        self.ensure_one()

        # Get tickets from selected projects
        if self.project_ids:
            all_tickets = self.env['jira.ticket'].search([
                ('project_id', 'in', self.project_ids.ids)
            ])
        else:
            all_tickets = self.env['jira.ticket'].search([])

        # Count by status
        status_data = {}
        for ticket in all_tickets:
            status = ticket.ticket_status or 'unknown'
            if status not in status_data:
                status_data[status] = 0
            status_data[status] += 1

        # Prepare chart data
        labels = []
        counts = []
        percentages = []
        colors = []

        color_map = {
            'to_do': '#5BC0DE',  # Light blue (Triage)
            'in_progress': '#FF9800',  # Orange (In Progress)
            'in_review': '#4CAF50',  # Green (In Review)
            'complete': '#2E4A8B',  # Dark blue (Complete)
            'blocked': '#F44336',  # Red (Blocked)
        }

        label_map = {
            'to_do': 'To Do',
            'in_progress': 'In Progress',
            'in_review': 'In Review',
            'complete': 'Complete',
            'blocked': 'Blocked',
        }

        total = len(all_tickets)

        for status, count in status_data.items():
            labels.append(label_map.get(status, status.title()))
            counts.append(count)
            percentage = (count / total * 100) if total > 0 else 0
            percentages.append(round(percentage, 1))
            colors.append(color_map.get(status, '#999'))

        return {
            'labels': labels,
            'data': counts,
            'percentages': percentages,
            'colors': colors,
            'total': total
        }