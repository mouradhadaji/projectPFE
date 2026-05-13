# controllers/api.py
# -*- coding: utf-8 -*-
from odoo import http
from odoo.http import request
import json


class PerformanceAPI(http.Controller):

    @http.route('/api/performance/member', type='json', auth='user', methods=['POST'])
    def get_member_performance(self, member_id, project_id, days=30):
        from ..utils.performance_analyzer import PerformanceAnalyzer

        analyzer = PerformanceAnalyzer(request.env)
        result = analyzer.predict_performance(member_id, project_id, days)
        return result

    @http.route('/api/performance/project', type='json', auth='user', methods=['POST'])
    def get_project_performance(self, project_id):
        from ..utils.performance_analyzer import PerformanceAnalyzer

        analyzer = PerformanceAnalyzer(request.env)
        result = analyzer.predict_project_health(project_id)
        return result

    @http.route('/api/performance/team', type='json', auth='user', methods=['POST'])
    def get_team_performance(self, project_id, days=30):
        from ..utils.performance_analyzer import PerformanceAnalyzer

        analyzer = PerformanceAnalyzer(request.env)
        result = analyzer.analyze_full_team(project_id, days)
        return result