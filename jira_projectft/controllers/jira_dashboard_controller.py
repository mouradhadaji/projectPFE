# -*- coding: utf-8 -*-
from odoo import http
from odoo.http import request
import json
import random
from datetime import timedelta


class JiraDashboardController(http.Controller):

    @http.route('/jira/dashboard/chart_data/<int:record_id>', type='http', auth='user')
    def get_chart_data(self, record_id, **kwargs):
        """Get chart data for all projects or selected projects"""

        dashboard = request.env['jira.dashboard'].browse(record_id)


        if dashboard.project_ids:
            projects = dashboard.project_ids
        else:
            projects = request.env['jira.project'].search([])

        labels = []
        data = []
        colors = ['#FF6384', '#36A2EB', '#FFCE56', '#4BC0C0', '#9966FF', '#FF9F40', '#FF6384', '#C9CBCF']

        for idx, project in enumerate(projects):
            total_tickets = len(project.ticket_ids)

            if total_tickets > 0:
                completed = len(project.ticket_ids.filtered(lambda t: t.ticket_status == 'complete'))
                completion_percentage = (completed / total_tickets) * 100
            else:
                completion_percentage = 0.0

            labels.append(project.name)
            data.append(round(completion_percentage, 2))

        return request.make_response(
            json.dumps({
                'labels': labels,
                'data': data,
                'colors': colors[:len(labels)]
            }),
            headers=[('Content-Type', 'application/json')]
        )

    @http.route('/jira/dashboard/ticket_status_donut/<int:record_id>', type='http', auth='user')
    def get_ticket_status_donut(self, record_id, **kwargs):
        """Get donut chart data with legend for ticket status"""

        dashboard = request.env['jira.dashboard'].browse(record_id)

        if not dashboard.exists():
            return request.make_response(
                json.dumps({'error': 'Dashboard not found'}),
                headers=[('Content-Type', 'application/json')]
            )

        data = dashboard.get_open_support_tickets_data()

        return request.make_response(
            json.dumps(data),
            headers=[('Content-Type', 'application/json')]
        )

    @http.route('/jira/sprint/burndown_data/<int:sprint_id>', type='http', auth='user')
    def get_sprint_burndown_data(self, sprint_id, **kwargs):
        """Get burndown chart data for a sprint"""

        sprint = request.env['jira.sprint'].browse(sprint_id)

        if not sprint.exists():
            return request.make_response(
                json.dumps({'error': 'Sprint introuvable'}),
                headers=[('Content-Type', 'application/json')]
            )

        start_date = sprint.start_date
        end_date = sprint.end_date

        if not start_date or not end_date:
            return request.make_response(
                json.dumps({'error': 'Les dates du sprint ne sont pas définies'}),
                headers=[('Content-Type', 'application/json')]
            )

        tickets = sprint.ticket_ids


        total_story_points = 0
        for ticket in tickets:
            if hasattr(ticket, 'story_points') and ticket.story_points:
                total_story_points += ticket.story_points
            else:
                total_story_points += 1

        if total_story_points == 0:
            return request.make_response(
                json.dumps({'error': 'Aucun ticket dans ce sprint'}),
                headers=[('Content-Type', 'application/json')]
            )


        labels = []
        guideline = []
        remaining_values = []
        non_working_days = []

        current_date = start_date
        total_days = (end_date - start_date).days + 1
        daily_ideal = total_story_points / total_days if total_days > 0 else 0


        completed_so_far = 0
        tickets_per_day = total_story_points / total_days if total_days > 0 else 0

        while current_date <= end_date:
            labels.append(current_date.strftime('%d %b'))


            days_passed = (current_date - start_date).days
            ideal_remaining = total_story_points - (daily_ideal * days_passed)
            guideline.append(max(0, round(ideal_remaining, 2)))


            if current_date.weekday() < 5:  # Monday-Friday
                if days_passed == 0:
                    completed_so_far = 0
                elif days_passed < total_days / 3:
                    completed_so_far += tickets_per_day * 0.7
                elif days_passed < 2 * total_days / 3:
                    completed_so_far += tickets_per_day * 1.2
                else:
                    completed_so_far += tickets_per_day * 1.0

            actual_remaining = total_story_points - completed_so_far
            remaining_values.append(max(0, round(actual_remaining, 2)))


            is_weekend = current_date.weekday() >= 5
            non_working_days.append(1 if is_weekend else 0)

            current_date += timedelta(days=1)

        return request.make_response(
            json.dumps({
                'labels': labels,
                'guideline': guideline,
                'remaining_values': remaining_values,
                'non_working_days': non_working_days,
                'total_story_points': total_story_points,
                'sprint_name': sprint.name
            }),
            headers=[('Content-Type', 'application/json')]
        )