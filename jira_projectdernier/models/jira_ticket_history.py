# models/jira_ticket_history.py
# -*- coding: utf-8 -*-
from odoo import models, fields, api

class JiraTicketHistory(models.Model):
    _name = 'jira.ticket.history'
    _description = 'Ticket Status History'
    _order = 'change_date desc'

    ticket_id = fields.Many2one(
        'jira.ticket', string='Ticket',
        required=True, ondelete='cascade'
    )
    old_status = fields.Selection([
        ('draft', 'To Do'),
        ('in_progress', 'In Progress'),
        ('in_review', 'In Review'),
        ('blocked', 'Blocked'),
        ('done', 'Done'),
        ('complete', 'Complete'),
    ], string='Ancien statut')

    new_status = fields.Selection([
        ('draft', 'To Do'),
        ('in_progress', 'In Progress'),
        ('in_review', 'In Review'),
        ('blocked', 'Blocked'),
        ('done', 'Done'),
        ('complete', 'Complete'),
    ], string='Nouveau statut', required=True)

    change_date = fields.Datetime(
        string='Date du changement',
        default=fields.Datetime.now
    )
    project_id = fields.Many2one(
        'jira.project', string='Projet',
        related='ticket_id.project_id', store=True
    )
    user_id = fields.Many2one(          # ← ce champ doit être présent
        'res.users', string='Modifié par',
        default=lambda self: self.env.user
    )