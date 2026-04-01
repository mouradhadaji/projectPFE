# utils/performance_analyzer.py
# -*- coding: utf-8 -*-
import logging
from datetime import date, timedelta
from .ml_predictor import MLPredictor

_logger = logging.getLogger(__name__)


class PerformanceAnalyzer:
    """
    Performance analyzer with ML predictions.
    """

    def __init__(self, env):
        self.env = env
        self.predictor = MLPredictor.get_instance()

    # ─── ML PREDICTION ───────────────────────────────────────────────────────

    def predict_performance(self, member_id, project_id, days=30):
        """
        Use ML model to predict team/member performance level.
        Returns prediction + standard analysis combined.
        """
        # Get standard analysis first
        analysis = self.analyze_team_member(member_id, project_id, days)
        metrics = analysis.get('metrics', {})

        if not metrics:
            analysis['ml_prediction'] = None
            analysis['ml_available'] = False
            return analysis

        # Build feature vector for the model
        # ⚠️ ADAPT these features to match your model's training data
        features = {
            'total_tickets':     metrics.get('total_tickets', 0),
            'completion_rate':   metrics.get('completion_rate', 0),
            'avg_story_points':  metrics.get('avg_story_points', 0),
            'completed_points':  metrics.get('completed_points', 0),
            'in_progress_count': metrics.get('in_progress_count', 0),
            'blocked_count':     metrics.get('blocked_count', 0),
            'overdue_count':     metrics.get('overdue_count', 0),
        }

        # Make prediction
        prediction = self.predictor.predict(features)
        probabilities = self.predictor.predict_proba(features)

        analysis['ml_prediction'] = prediction
        analysis['ml_probabilities'] = (
            probabilities.tolist() if probabilities is not None else None
        )
        analysis['ml_available'] = self.predictor.is_loaded

        # Override level with ML prediction if available
        if prediction is not None:
            analysis['ml_level'] = self._map_prediction_to_level(prediction)

        return analysis

    def predict_project_health(self, project_id):
        """
        Use ML to predict overall project health.
        """
        project_analysis = self.analyze_project(project_id)

        if 'error' in project_analysis:
            return project_analysis

        features = {
            'total_tickets':   project_analysis.get('total_tickets', 0),
            'completion_rate': project_analysis.get('completion_rate', 0),
            'done':            project_analysis.get('done', 0),
            'in_progress':     project_analysis.get('in_progress', 0),
            'total_points':    project_analysis.get('total_points', 0),
            'done_points':     project_analysis.get('done_points', 0),
            'points_rate':     project_analysis.get('points_rate', 0),
        }

        prediction = self.predictor.predict(features)
        project_analysis['ml_health_prediction'] = prediction
        project_analysis['ml_available'] = self.predictor.is_loaded

        return project_analysis

    def _map_prediction_to_level(self, prediction):
        """Map ML output to readable level."""
        # Adapt based on your model's output format
        mapping = {
            0: '❌ Critical',
            1: '🔴 Below Average',
            2: '⚠️ Average',
            3: '✅ Good',
            4: '🌟 Excellent',
        }

        if isinstance(prediction, (int, float)):
            return mapping.get(int(prediction), f'Score: {prediction}')

        return str(prediction)

    # ─── ANALYSE MEMBRE ──────────────────────────────────────────────────────

    def analyze_team_member(self, member_id, project_id, days=30):
        since = date.today() - timedelta(days=days)

        tickets = self.env['jira.ticket'].search([
            ('assignee_id', '=', member_id),
            ('project_id', '=', project_id),
        ])

        if not tickets:
            return {
                'member_id': member_id,
                'metrics': {},
                'issues': ['No tickets assigned in this period'],
                'performance_score': 0,
                'level': 'N/A',
                'recommendations': ['Assign tickets to this member'],
            }

        metrics = {
            'total_tickets':     len(tickets),
            'completion_rate':   self._calc_completion_rate(tickets),
            'avg_story_points':  self._calc_avg_story_points(tickets),
            'completed_points':  self._calc_completed_points(tickets),
            'in_progress_count': self._calc_in_progress(tickets),
            'blocked_count':     self._calc_blocked(tickets),
            'overdue_count':     self._calc_overdue(tickets),
        }

        team_avg = self._get_team_averages(project_id)
        issues = self._identify_issues(metrics, team_avg)
        score = self._calculate_score(metrics, team_avg)
        level = self._get_performance_level(score)
        recommendations = self._generate_recommendations(metrics, team_avg, issues)

        return {
            'member_id':          member_id,
            'metrics':            metrics,
            'team_avg':           team_avg,
            'issues':             issues,
            'performance_score':  round(score, 1),
            'level':              level,
            'recommendations':    recommendations,
        }

    # ─── ANALYSE PROJET ──────────────────────────────────────────────────────

    def analyze_project(self, project_id):
        project = self.env['jira.project'].browse(project_id)
        if not project.exists():
            return {'error': 'Project not found'}

        tickets = project.ticket_ids
        total = len(tickets)

        if total == 0:
            return {'error': 'No tickets in this project'}

        done = tickets.filtered(lambda t: t.ticket_status in ('done', 'complete'))
        in_progress = tickets.filtered(lambda t: t.ticket_status == 'in_progress')
        blocked = tickets.filtered(lambda t: t.ticket_status == 'blocked')
        draft = tickets.filtered(lambda t: t.ticket_status == 'draft')

        completion_rate = round(len(done) / total * 100, 1)
        total_points = sum(tickets.mapped('story_points') or [0])
        done_points = sum(done.mapped('story_points') or [0])
        points_rate = round(done_points / total_points * 100, 1) if total_points else 0

        health = self._calculate_project_health(completion_rate, len(blocked), total)
        risks = self._identify_project_risks(tickets, project)

        return {
            'project_name':    project.name,
            'total_tickets':   total,
            'done':            len(done),
            'in_progress':     len(in_progress),
            'draft':           len(draft),
            'completion_rate': completion_rate,
            'total_points':    total_points,
            'done_points':     done_points,
            'points_rate':     points_rate,
            'health':          health,
            'risks':           risks,
        }

    # ─── ANALYSE ÉQUIPE COMPLÈTE ─────────────────────────────────────────────

    def analyze_full_team(self, project_id, days=30):
        project = self.env['jira.project'].browse(project_id)
        if not project.exists():
            return {'error': 'Project not found'}

        member_ids = list(set(
            self.env['jira.ticket'].search([
                ('project_id', '=', project_id),
            ]).mapped('assignee_id.id')
        ))

        results = []
        for mid in member_ids:
            if mid:
                # Use ML prediction instead of standard analysis
                analysis = self.predict_performance(mid, project_id, days)
                member = self.env['res.users'].browse(mid)
                analysis['member_name'] = member.name if member else 'Unknown'
                results.append(analysis)

        results.sort(key=lambda x: x.get('performance_score', 0), reverse=True)

        return {
            'project_name': project.name,
            'team_size':    len(results),
            'period_days':  days,
            'members':      results,
            'ml_available': self.predictor.is_loaded,
        }

    # ─── HELPER METHODS (unchanged) ──────────────────────────────────────────

    def _calc_completion_rate(self, tickets):
        total = len(tickets)
        if not total:
            return 0.0
        done = len(tickets.filtered(lambda t: t.ticket_status in ('done', 'complete')))
        return round(done / total * 100, 1)

    def _calc_avg_story_points(self, tickets):
        pts = [p for p in tickets.mapped('story_points') if p]
        return round(sum(pts) / len(pts), 1) if pts else 0.0

    def _calc_completed_points(self, tickets):
        done = tickets.filtered(lambda t: t.ticket_status in ('done', 'complete'))
        return sum(done.mapped('story_points') or [0])

    def _calc_in_progress(self, tickets):
        return len(tickets.filtered(lambda t: t.ticket_status == 'in_progress'))

    def _calc_blocked(self, tickets):
        return len(tickets.filtered(lambda t: t.ticket_status == 'blocked'))

    def _calc_overdue(self, tickets):
        today = date.today()
        return sum(
            1 for t in tickets
            if t.ticket_status not in ('done', 'complete')
            and hasattr(t, 'due_date') and t.due_date and t.due_date < today
        )

    def _get_team_averages(self, project_id):
        tickets = self.env['jira.ticket'].search([('project_id', '=', project_id)])
        if not tickets:
            return {'avg_completion_rate': 0, 'avg_story_points': 0, 'avg_completed_points': 0}

        member_ids = [m for m in set(tickets.mapped('assignee_id.id')) if m]
        if not member_ids:
            return {'avg_completion_rate': 0, 'avg_story_points': 0, 'avg_completed_points': 0}

        rates, pts, comp = [], [], []
        for mid in member_ids:
            mt = tickets.filtered(lambda t: t.assignee_id.id == mid)
            rates.append(self._calc_completion_rate(mt))
            pts.append(self._calc_avg_story_points(mt))
            comp.append(self._calc_completed_points(mt))

        n = len(member_ids)
        return {
            'avg_completion_rate':  round(sum(rates) / n, 1),
            'avg_story_points':    round(sum(pts) / n, 1),
            'avg_completed_points': round(sum(comp) / n, 1),
        }

    def _identify_issues(self, metrics, team_avg):
        issues = []
        if metrics['completion_rate'] < team_avg.get('avg_completion_rate', 0) * 0.7:
            issues.append('Completion rate significantly below team average')
        if metrics['blocked_count'] > 2:
            issues.append(f"{metrics['blocked_count']} tickets blocked")
        if metrics['overdue_count'] > 0:
            issues.append(f"{metrics['overdue_count']} overdue tickets")
        if metrics['in_progress_count'] > 5:
            issues.append('Too many tickets in progress (WIP limit exceeded)')
        if metrics['completion_rate'] < 30:
            issues.append('Very low completion rate')
        return issues

    def _calculate_score(self, metrics, team_avg):
        score = 0
        avg_rate = team_avg.get('avg_completion_rate', 50) or 50
        score += min(40, (metrics['completion_rate'] / avg_rate) * 40)
        avg_pts = team_avg.get('avg_completed_points', 1) or 1
        score += min(30, (metrics['completed_points'] / avg_pts) * 30)
        score -= metrics['blocked_count'] * 3
        score -= metrics['overdue_count'] * 5
        if metrics['in_progress_count'] > 5:
            score -= (metrics['in_progress_count'] - 5) * 2
        if metrics['completion_rate'] >= 80:
            score += 10
        return max(0, min(100, score))

    def _get_performance_level(self, score):
        if score >= 85:   return '🌟 Excellent'
        elif score >= 70: return '✅ Good'
        elif score >= 50: return '⚠️ Average'
        elif score >= 30: return '🔴 Below Average'
        else:             return '❌ Critical'

    def _generate_recommendations(self, metrics, team_avg, issues):
        recs = []
        if metrics['completion_rate'] < 50:
            recs.append('Focus on completing existing tickets first')
        if metrics['blocked_count'] > 0:
            recs.append(f"Resolve {metrics['blocked_count']} blocked ticket(s)")
        if metrics['overdue_count'] > 0:
            recs.append(f"Prioritize {metrics['overdue_count']} overdue ticket(s)")
        if metrics['in_progress_count'] > 3:
            recs.append('Reduce Work In Progress')
        if not recs:
            recs.append('Keep up the great work! 🎉')
        return recs

    def _calculate_project_health(self, completion_rate, blocked_count, total):
        if blocked_count > total * 0.2:
            return {'status': '🔴 Critical', 'color': '#dc3545'}
        elif completion_rate >= 70:
            return {'status': '🟢 Healthy', 'color': '#28a745'}
        elif completion_rate >= 40:
            return {'status': '🟡 At Risk', 'color': '#ffc107'}
        return {'status': '🔴 Critical', 'color': '#dc3545'}

    def _identify_project_risks(self, tickets, project):
        risks = []
        total = len(tickets)

        blocked = tickets.filtered(lambda t: t.ticket_status == 'blocked')
        if blocked:
            risks.append({
                'type': 'Blocked Tickets', 'level': 'High',
                'detail': f'{len(blocked)} blocked', 'color': '#dc3545',
            })

        unassigned = tickets.filtered(lambda t: not t.assignee_id)
        if len(unassigned) > total * 0.3:
            risks.append({
                'type': 'Unassigned Tickets', 'level': 'Medium',
                'detail': f'{len(unassigned)} unassigned', 'color': '#ffc107',
            })

        if not risks:
            risks.append({
                'type': 'No Major Risks', 'level': 'Low',
                'detail': 'On track', 'color': '#28a745',
            })

        return risks