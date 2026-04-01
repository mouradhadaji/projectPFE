# -*- coding: utf-8 -*-
import logging
from datetime import date, timedelta

_logger = logging.getLogger(__name__)


class PerformanceAnalyzer:
    """
    Analyseur de performance pour les membres de l'équipe et les projets.
    Calcule les métriques, compare avec les moyennes et identifie les problèmes.
    """

    def __init__(self, env):
        self.env = env

    # ─── ANALYSE MEMBRE ──────────────────────────────────────────────────────

    def analyze_team_member(self, member_id, project_id, days=30):
        """
        Analyse les performances d'un membre de l'équipe sur les X derniers jours.
        Retourne les métriques, problèmes et score de performance.
        """
        since = date.today() - timedelta(days=days)

        # Récupère les tickets du membre
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
                'recommendations': ['Assign tickets to this member to track performance'],
            }

        # Calcule les métriques individuelles
        metrics = {
            'total_tickets':      len(tickets),
            'completion_rate':    self._calc_completion_rate(tickets),
            'avg_story_points':   self._calc_avg_story_points(tickets),
            'completed_points':   self._calc_completed_points(tickets),
            'in_progress_count':  self._calc_in_progress(tickets),
            'blocked_count':      self._calc_blocked(tickets),
            'overdue_count':      self._calc_overdue(tickets),
        }

        # Compare avec les moyennes de l'équipe
        team_avg = self._get_team_averages(project_id)

        # Identifie les problèmes
        issues = self._identify_issues(metrics, team_avg)

        # Calcule le score global
        score = self._calculate_score(metrics, team_avg)

        # Niveau de performance
        level = self._get_performance_level(score)

        # Recommandations
        recommendations = self._generate_recommendations(metrics, team_avg, issues)

        return {
            'member_id':       member_id,
            'metrics':         metrics,
            'team_avg':        team_avg,
            'issues':          issues,
            'performance_score': round(score, 1),
            'level':           level,
            'recommendations': recommendations,
        }

    # ─── ANALYSE PROJET ──────────────────────────────────────────────────────

    def analyze_project(self, project_id):
        """
        Analyse globale d'un projet : santé, risques, progression.
        """
        project = self.env['jira.project'].browse(project_id)
        if not project.exists():
            return {'error': 'Project not found'}

        tickets = project.ticket_ids
        total = len(tickets)

        if total == 0:
            return {'error': 'No tickets in this project'}

        done = tickets.filtered(lambda t: t.ticket_status in ('done', 'complete'))
        in_progress = tickets.filtered(lambda t: t.ticket_status == 'in_progress')
        blocked = tickets.filtered(lambda t: t.ticket_status == 'blocked') \
            if hasattr(tickets, 'ticket_status') else []
        draft = tickets.filtered(lambda t: t.ticket_status == 'draft')

        completion_rate = round(len(done) / total * 100, 1) if total > 0 else 0

        # Story points
        total_points = sum(tickets.mapped('story_points') or [0])
        done_points = sum(done.mapped('story_points') or [0])
        points_rate = round(done_points / total_points * 100, 1) if total_points > 0 else 0

        # Santé du projet
        health = self._calculate_project_health(completion_rate, len(blocked), total)

        # Risques
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
        """
        Analyse tous les membres de l'équipe d'un projet.
        Retourne un classement et les statistiques globales.
        """
        project = self.env['jira.project'].browse(project_id)
        if not project.exists():
            return {'error': 'Project not found'}

        # Récupère tous les membres assignés
        member_ids = self.env['jira.ticket'].search([
            ('project_id', '=', project_id),
        ]).mapped('assignee_id.id')

        member_ids = list(set(member_ids))  # déduplique

        results = []
        for member_id in member_ids:
            if member_id:
                analysis = self.analyze_team_member(member_id, project_id, days)
                member = self.env['res.users'].browse(member_id)
                analysis['member_name'] = member.name if member else 'Unknown'
                results.append(analysis)

        # Trie par score décroissant
        results.sort(key=lambda x: x.get('performance_score', 0), reverse=True)

        return {
            'project_name': project.name,
            'team_size':    len(results),
            'period_days':  days,
            'members':      results,
        }

    # ─── MÉTRIQUES INDIVIDUELLES ─────────────────────────────────────────────

    def _calc_completion_rate(self, tickets):
        total = len(tickets)
        if total == 0:
            return 0.0
        done = len(tickets.filtered(
            lambda t: t.ticket_status in ('done', 'complete')
        ))
        return round(done / total * 100, 1)

    def _calc_avg_story_points(self, tickets):
        points = tickets.mapped('story_points')
        points = [p for p in points if p]
        return round(sum(points) / len(points), 1) if points else 0.0

    def _calc_completed_points(self, tickets):
        done = tickets.filtered(lambda t: t.ticket_status in ('done', 'complete'))
        return sum(done.mapped('story_points') or [0])

    def _calc_in_progress(self, tickets):
        return len(tickets.filtered(lambda t: t.ticket_status == 'in_progress'))

    def _calc_blocked(self, tickets):
        return len(tickets.filtered(lambda t: t.ticket_status == 'blocked'))

    def _calc_overdue(self, tickets):
        today = date.today()
        overdue = 0
        for t in tickets:
            if t.ticket_status not in ('done', 'complete'):
                if hasattr(t, 'due_date') and t.due_date and t.due_date < today:
                    overdue += 1
        return overdue

    # ─── MOYENNES ÉQUIPE ─────────────────────────────────────────────────────

    def _get_team_averages(self, project_id):
        """Calcule les moyennes de l'équipe pour comparaison."""
        tickets = self.env['jira.ticket'].search([
            ('project_id', '=', project_id),
        ])

        if not tickets:
            return {
                'avg_completion_rate': 0,
                'avg_story_points':    0,
                'avg_completed_points': 0,
            }

        member_ids = list(set(tickets.mapped('assignee_id.id')))
        member_ids = [m for m in member_ids if m]

        if not member_ids:
            return {
                'avg_completion_rate': 0,
                'avg_story_points':    0,
                'avg_completed_points': 0,
            }

        completion_rates = []
        story_points_list = []
        completed_points_list = []

        for member_id in member_ids:
            member_tickets = tickets.filtered(lambda t: t.assignee_id.id == member_id)
            completion_rates.append(self._calc_completion_rate(member_tickets))
            story_points_list.append(self._calc_avg_story_points(member_tickets))
            completed_points_list.append(self._calc_completed_points(member_tickets))

        return {
            'avg_completion_rate':   round(sum(completion_rates) / len(completion_rates), 1),
            'avg_story_points':      round(sum(story_points_list) / len(story_points_list), 1),
            'avg_completed_points':  round(sum(completed_points_list) / len(completed_points_list), 1),
        }

    # ─── IDENTIFICATION PROBLÈMES ────────────────────────────────────────────

    def _identify_issues(self, metrics, team_avg):
        issues = []

        if metrics['completion_rate'] < team_avg.get('avg_completion_rate', 0) * 0.7:
            issues.append('Completion rate significantly below team average')

        if metrics['blocked_count'] > 2:
            issues.append(f"{metrics['blocked_count']} tickets blocked")

        if metrics['overdue_count'] > 0:
            issues.append(f"{metrics['overdue_count']} overdue tickets")

        if metrics['in_progress_count'] > 5:
            issues.append('Too many tickets in progress simultaneously (WIP limit exceeded)')

        if metrics['completion_rate'] < 30:
            issues.append('Very low completion rate — needs attention')

        return issues

    # ─── CALCUL SCORE ────────────────────────────────────────────────────────

    def _calculate_score(self, metrics, team_avg):
        """
        Score de 0 à 100 basé sur plusieurs facteurs.
        """
        score = 0

        # Completion rate (40 pts max)
        avg_rate = team_avg.get('avg_completion_rate', 50) or 50
        score += min(40, (metrics['completion_rate'] / avg_rate) * 40)

        # Story points complétés (30 pts max)
        avg_pts = team_avg.get('avg_completed_points', 1) or 1
        score += min(30, (metrics['completed_points'] / avg_pts) * 30)

        # Pénalités
        score -= metrics['blocked_count'] * 3   # -3 par ticket bloqué
        score -= metrics['overdue_count'] * 5   # -5 par ticket en retard
        if metrics['in_progress_count'] > 5:
            score -= (metrics['in_progress_count'] - 5) * 2

        # Bonus si completion_rate > 80%
        if metrics['completion_rate'] >= 80:
            score += 10

        return max(0, min(100, score))

    # ─── NIVEAU PERFORMANCE ──────────────────────────────────────────────────

    def _get_performance_level(self, score):
        if score >= 85:
            return '🌟 Excellent'
        elif score >= 70:
            return '✅ Good'
        elif score >= 50:
            return '⚠️ Average'
        elif score >= 30:
            return '🔴 Below Average'
        else:
            return '❌ Critical'

    # ─── RECOMMANDATIONS ─────────────────────────────────────────────────────

    def _generate_recommendations(self, metrics, team_avg, issues):
        recommendations = []

        if metrics['completion_rate'] < 50:
            recommendations.append(
                'Focus on completing existing tickets before taking new ones'
            )

        if metrics['blocked_count'] > 0:
            recommendations.append(
                f"Resolve {metrics['blocked_count']} blocked ticket(s) with team lead"
            )

        if metrics['overdue_count'] > 0:
            recommendations.append(
                f"Prioritize {metrics['overdue_count']} overdue ticket(s) immediately"
            )

        if metrics['in_progress_count'] > 3:
            recommendations.append(
                'Reduce Work In Progress — finish current tasks before starting new ones'
            )

        if metrics['avg_story_points'] > team_avg.get('avg_story_points', 0) * 1.5:
            recommendations.append(
                'Story points seem high — consider breaking down large tickets'
            )

        if not recommendations:
            recommendations.append('Keep up the great work! 🎉')

        return recommendations

    # ─── SANTÉ PROJET ────────────────────────────────────────────────────────

    def _calculate_project_health(self, completion_rate, blocked_count, total):
        if blocked_count > total * 0.2:
            return {'status': '🔴 Critical', 'color': '#dc3545'}
        elif completion_rate >= 70:
            return {'status': '🟢 Healthy', 'color': '#28a745'}
        elif completion_rate >= 40:
            return {'status': '🟡 At Risk', 'color': '#ffc107'}
        else:
            return {'status': '🔴 Critical', 'color': '#dc3545'}

    # ─── RISQUES PROJET ──────────────────────────────────────────────────────

    def _identify_project_risks(self, tickets, project):
        risks = []
        total = len(tickets)

        blocked = tickets.filtered(lambda t: t.ticket_status == 'blocked')
        if len(blocked) > 0:
            risks.append({
                'type':    'Blocked Tickets',
                'level':   'High',
                'detail':  f'{len(blocked)} ticket(s) are blocked',
                'color':   '#dc3545',
            })

        unassigned = tickets.filtered(lambda t: not t.assignee_id)
        if len(unassigned) > total * 0.3:
            risks.append({
                'type':    'Unassigned Tickets',
                'level':   'Medium',
                'detail':  f'{len(unassigned)} ticket(s) have no assignee',
                'color':   '#ffc107',
            })

        sprints = self.env['jira.sprint'].search([
            ('project_id', '=', project.id),
            ('state', '=', 'active'),
        ])
        if not sprints:
            risks.append({
                'type':    'No Active Sprint',
                'level':   'Medium',
                'detail':  'No sprint is currently active',
                'color':   '#ffc107',
            })

        if not risks:
            risks.append({
                'type':    'No Major Risks',
                'level':   'Low',
                'detail':  'Project is on track',
                'color':   '#28a745',
            })

        return risks