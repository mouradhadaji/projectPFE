# -*- coding: utf-8 -*-
from odoo import models, fields, api
import logging
from odoo.exceptions import UserError
from odoo import _

_logger = logging.getLogger(__name__)

class JiraReport(models.Model):
    _name = 'jira.report'
    _description = 'Jira Report Schedule'
    _inherit = ['mail.thread']

    name = fields.Char(string='Report Name', required=True)
    project_id = fields.Many2one('jira.project', string='Project')
    sprint_id = fields.Many2one('jira.sprint', string='Sprint')
    frequency = fields.Selection([
        ('weekly', 'Weekly'),
        ('monthly', 'Monthly'),
    ], string='Frequency', default='weekly', required=True)

    recipient_ids = fields.Many2many(
        'res.users',
        string='Recipients'
    )

    include_tickets = fields.Boolean(
        string='Include Tickets Report',
        default=True
    )
    include_sprint = fields.Boolean(
        string='Include Sprint Report',
        default=True
    )

    last_sent = fields.Datetime(
        string='Last Sent',
        readonly=True
    )

    active = fields.Boolean(default=True)

    # ── Envoi manuel ──────────────────────────────
    def action_send_report(self):
        self.ensure_one()
        try:
            self._send_report()
            return {
                'type': 'ir.actions.client',
                'tag': 'display_notification',
                'params': {
                    'title': _('Report Sent'),
                    'message': _('Report sent successfully to %d recipients!')
                               % len(self.recipient_ids),
                    'type': 'success',

                }
            }
        except Exception as e:
            _logger.error("Failed to send report %s: %s", self.name, str(e))
            raise UserError(_("Failed to send report: %s") % str(e))

    # ── Cron hebdomadaire ─────────────────────────
    @api.model
    def _cron_send_weekly_reports(self):
        reports = self.search([
            ('frequency', '=', 'weekly'),
            ('active', '=', True)
        ])
        for report in reports:
            try:
                report._send_report()
            except Exception as e:
                _logger.error('Error sending report %s: %s', report.name, str(e))

    # ── Logique d'envoi ───────────────────────────
    def _send_report(self):
        self.ensure_one()

        if not self.recipient_ids:
            return

        # Données du rapport
        data = self._get_report_data()

        # Corps de l'email
        body = self._build_email_body(data)

        # Destinataires
        recipients = self.recipient_ids.mapped('partner_id')

        # Envoi email
        mail_values = {
            'subject': f'📊 Weekly Report — {self.name}',
            'body_html': body,
            'recipient_ids': [(4, p.id) for p in recipients],
            'email_from': self.env.user.email
              or self.env.company.email
              or 'noreply@jirapm.com',
        }

        mail = self.env['mail.mail'].create(mail_values)
        mail = self.env['mail.mail'].create(mail_values)
        mail.send()


        if mail.state == 'exception':
            raise Exception(f"Mail failed: {mail.failure_reason}")

        # Mise à jour date d'envoi
        self.last_sent = fields.Datetime.now()

        _logger.info('Report %s sent to %d recipients', self.name, len(recipients))

    # ── Données du rapport ────────────────────────
    def _get_report_data(self):
        data = {
            'report_name': self.name,
            'project': self.project_id.name if self.project_id else 'All Projects',
            'date': fields.Date.today(),
            'tickets': [],
            'sprint': {},
        }

        # Tickets
        if self.include_tickets and self.project_id:
            tickets = self.project_id.ticket_ids
            data['tickets'] = {
                'total': len(tickets),
                'completed': len(tickets.filtered(
                    lambda t: t.ticket_status in ('done', 'complete')
                )),
                'in_progress': len(tickets.filtered(
                    lambda t: t.ticket_status == 'in_progress'
                )),
                'draft': len(tickets.filtered(
                    lambda t: t.ticket_status == 'draft'
                )),
                'completion_rate': round(
                    len(tickets.filtered(
                        lambda t: t.ticket_status in ('done', 'complete')
                    )) / len(tickets) * 100, 1
                ) if tickets else 0,
            }

        # Sprint
        # Sprint
        if self.include_sprint and self.sprint_id:
            sprint = self.sprint_id
            days_left = (sprint.end_date - fields.Date.today()).days \
                if sprint.end_date else 0
            data['sprint'] = {
                'name': sprint.name,
                'state': sprint.state,
                'progress': sprint.progress,
                'total_points': sprint.total_story_points,
                'completed_points': sprint.completed_story_points,
                'days_left': max(0, days_left),
                'is_overdue': days_left < 0,
                'overdue_days': abs(days_left) if days_left < 0 else 0,
            }

        return data

    # ── Corps HTML de l'email ─────────────────────
    def _build_email_body(self, data):
        tickets = data.get('tickets', {})
        sprint = data.get('sprint', {})

        body = f"""
        <div style="font-family: Arial, sans-serif; max-width: 700px; margin: 0 auto;">

            <!-- Header -->
            <div style="background: linear-gradient(90deg, #0D1B2A, #1B2A3B);
                        padding: 30px; border-radius: 10px 10px 0 0;">
                <h1 style="color: #1FC7DE; margin: 0; font-size: 24px;">
                    📊 Weekly Report
                </h1>
                <p style="color: rgba(255,255,255,0.7); margin: 8px 0 0;">
                    {data['project']} — {data['date']}
                </p>
            </div>

            <!-- KPIs Tickets -->
            {"" if not tickets else f'''
            <div style="padding: 24px; background: #f8f9fa; border-left: 4px solid #1FC7DE;">
                <h2 style="color: #2c3e50; margin: 0 0 16px;">🎫 Tickets Summary</h2>
                <div style="display: grid; grid-template-columns: repeat(4, 1fr); gap: 12px;">
                    <div style="background: white; padding: 16px; border-radius: 8px;
                                border-left: 4px solid #007bff; text-align: center;">
                        <div style="font-size: 28px; font-weight: 700;
                                    color: #007bff;">{tickets.get("total", 0)}</div>
                        <div style="color: #6c757d; font-size: 12px;">Total</div>
                    </div>
                    <div style="background: white; padding: 16px; border-radius: 8px;
                                border-left: 4px solid #28a745; text-align: center;">
                        <div style="font-size: 28px; font-weight: 700;
                                    color: #28a745;">{tickets.get("completed", 0)}</div>
                        <div style="color: #6c757d; font-size: 12px;">Completed</div>
                    </div>
                    <div style="background: white; padding: 16px; border-radius: 8px;
                                border-left: 4px solid #ffc107; text-align: center;">
                        <div style="font-size: 28px; font-weight: 700;
                                    color: #ffc107;">{tickets.get("in_progress", 0)}</div>
                        <div style="color: #6c757d; font-size: 12px;">In Progress</div>
                    </div>
                    <div style="background: white; padding: 16px; border-radius: 8px;
                                border-left: 4px solid #17a2b8; text-align: center;">
                        <div style="font-size: 28px; font-weight: 700;
                                    color: #17a2b8;">{tickets.get("completion_rate", 0)}%</div>
                        <div style="color: #6c757d; font-size: 12px;">Completion</div>
                    </div>
                </div>
            </div>
            '''}

            <!-- Sprint Summary -->
            {"" if not sprint else f'''
            <div style="padding: 24px; background: white; border-left: 4px solid #185FA5;">
                <h2 style="color: #2c3e50; margin: 0 0 16px;">🚀 Sprint Summary</h2>
                <table style="width: 100%; border-collapse: collapse;">
                    <tr style="background: #f8f9fa;">
                        <td style="padding: 10px; font-weight: 600;">Sprint</td>
                        <td style="padding: 10px;">{sprint.get("name", "")}</td>
                    </tr>
                    <tr>
                        <td style="padding: 10px; font-weight: 600;">Status</td>
                        <td style="padding: 10px;">{sprint.get("state", "")}</td>
                    </tr>
                    <tr style="background: #f8f9fa;">
                        <td style="padding: 10px; font-weight: 600;">Progress</td>
                        <td style="padding: 10px;">{sprint.get("progress", 0)}%</td>
                    </tr>
                    <tr>
                        <td style="padding: 10px; font-weight: 600;">Story Points</td>
                        <td style="padding: 10px;">
                            {sprint.get("completed_points", 0)} /
                            {sprint.get("total_points", 0)}
                        </td>
                    </tr>
                    <tr style="background: #f8f9fa;">
                        <td style="padding: 10px; font-weight: 600;">Days Left</td>
                        <td style="padding: 10px; color: {'red' if sprint.get('is_overdue') else 'black'};">
                         {'⚠️ En retard de ' + str(sprint.get('overdue_days')) + ' jours'
                          if sprint.get('is_overdue')
                          else str(sprint.get('days_left')) + ' days left'}
                        </td>
                    </tr>
                </table>
            </div>
            '''}

            <!-- Footer -->
            <div style="background: #0D1B2A; padding: 20px;
                        border-radius: 0 0 10px 10px; text-align: center;">
                <p style="color: rgba(255,255,255,0.5); margin: 0; font-size: 12px;">
                    Generated automatically by Jira PM • Odoo 18
                </p>
            </div>

        </div>
        """
        return body