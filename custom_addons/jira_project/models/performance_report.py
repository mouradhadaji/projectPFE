# models/performance_report.py
# -*- coding: utf-8 -*-
from odoo import models, fields, api
import logging

_logger = logging.getLogger(__name__)


class PerformanceReport(models.Model):
    _name = 'performance.report'
    _description = 'ML Performance Report'
    _order = 'create_date desc'

    member_id = fields.Many2one('res.users', string='Team Member')
    project_id = fields.Many2one('jira.project', string='Project')

    # Standard metrics
    total_tickets = fields.Integer()
    completion_rate = fields.Float()
    completed_points = fields.Float()
    blocked_count = fields.Integer()
    overdue_count = fields.Integer()
    performance_score = fields.Float()
    level = fields.Char()

    # ML fields
    ml_prediction = fields.Char(string='ML Prediction')
    ml_level = fields.Char(string='ML Performance Level')
    ml_available = fields.Boolean(string='ML Model Used')

    # Extra
    issues = fields.Text()
    recommendations = fields.Text()

    def action_run_analysis(self):
        """Button action to run ML analysis."""
        from ..utils.performance_analyzer import PerformanceAnalyzer

        analyzer = PerformanceAnalyzer(self.env)

        for record in self:
            if not record.member_id or not record.project_id:
                continue

            result = analyzer.predict_performance(
                record.member_id.id,
                record.project_id.id,
                days=30,
            )

            metrics = result.get('metrics', {})
            record.write({
                'total_tickets':     metrics.get('total_tickets', 0),
                'completion_rate':   metrics.get('completion_rate', 0),
                'completed_points':  metrics.get('completed_points', 0),
                'blocked_count':     metrics.get('blocked_count', 0),
                'overdue_count':     metrics.get('overdue_count', 0),
                'performance_score': result.get('performance_score', 0),
                'level':             result.get('level', ''),
                'ml_prediction':     str(result.get('ml_prediction', '')),
                'ml_level':          result.get('ml_level', ''),
                'ml_available':      result.get('ml_available', False),
                'issues':            '\n'.join(result.get('issues', [])),
                'recommendations':   '\n'.join(result.get('recommendations', [])),
            })

        return True