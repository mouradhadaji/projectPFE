# controllers/performance_api.py
# -*- coding: utf-8 -*-
from odoo import http
from odoo.http import request
import json
import logging

_logger = logging.getLogger(__name__)


class PerformanceAPIController(http.Controller):

    @http.route('/jira/performance/projects', type='json', auth='user')
    def get_projects(self):
        """Return list of projects for the dropdown."""
        projects = request.env['jira.project'].search([])
        return [{
            'id': p.id,
            'name': p.name,
        } for p in projects]

    @http.route('/jira/performance/analyze_project', type='json', auth='user')
    def analyze_project(self, project_id):
        """Analyze a single project with ML."""
        from ..utils.performance_analyzer import PerformanceAnalyzer

        try:
            analyzer = PerformanceAnalyzer(request.env)
            result = analyzer.predict_project_health(int(project_id))
            return {'status': 'ok', 'data': result}
        except Exception as e:
            _logger.error("Project analysis failed: %s", str(e))
            return {'status': 'error', 'message': str(e)}

    @http.route('/jira/performance/analyze_team', type='json', auth='user')
    def analyze_team(self, project_id, days=30):
        """Analyze full team with ML predictions."""
        from ..utils.performance_analyzer import PerformanceAnalyzer

        try:
            analyzer = PerformanceAnalyzer(request.env)
            result = analyzer.analyze_full_team(int(project_id), int(days))
            return {'status': 'ok', 'data': result}
        except Exception as e:
            _logger.error("Team analysis failed: %s", str(e))
            return {'status': 'error', 'message': str(e)}

    @http.route('/jira/performance/analyze_member', type='json', auth='user')
    def analyze_member(self, member_id, project_id, days=30):
        """Analyze a single member with ML."""
        from ..utils.performance_analyzer import PerformanceAnalyzer

        try:
            analyzer = PerformanceAnalyzer(request.env)
            result = analyzer.predict_performance(
                int(member_id), int(project_id), int(days)
            )
            return {'status': 'ok', 'data': result}
        except Exception as e:
            _logger.error("Member analysis failed: %s", str(e))
            return {'status': 'error', 'message': str(e)}