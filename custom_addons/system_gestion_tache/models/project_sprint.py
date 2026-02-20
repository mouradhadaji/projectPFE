# -*- coding: utf-8 -*-
from odoo import models, fields, api


class ProjectSprint(models.Model):
    _name = 'project.sprint'
    _description = 'Sprint de Projet'
    _order = 'start_date desc'

    name = fields.Char(
        string='Nom du Sprint',
        required=True
    )

    project_id = fields.Many2one(
        'project.management',
        string='Projet',
        required=True,
        ondelete='cascade'
    )

    goal = fields.Text(string='Objectif du Sprint')

    state = fields.Selection([
        ('planned', 'Planifié'),
        ('active', 'Actif'),
        ('completed', 'Terminé')
    ], string='État', default='planned', required=True)

    start_date = fields.Date(
        string='Date de début',
        required=True
    )

    end_date = fields.Date(
        string='Date de fin',
        required=True
    )

    # Relations
    ticket_ids = fields.One2many(
        'project.ticket',
        'sprint_id',
        string='Tickets'
    )

    # Champs calculés
    ticket_count = fields.Integer(
        string='Nombre de Tickets',
        compute='_compute_ticket_count'
    )

    completed_tickets = fields.Integer(
        string='Tickets Terminés',
        compute='_compute_completed_tickets'
    )

    @api.depends('ticket_ids')
    def _compute_ticket_count(self):
        for sprint in self:
            sprint.ticket_count = len(sprint.ticket_ids)

    @api.depends('ticket_ids.state')
    def _compute_completed_tickets(self):
        for sprint in self:
            sprint.completed_tickets = len(
                sprint.ticket_ids.filtered(lambda t: t.state == 'done')
            )

            # Action pour voir les tickets
            def action_view_tickets(self):
                self.ensure_one()
                return {
                    'name': f'Tickets - {self.name}',
                    'type': 'ir.actions.act_window',
                    'res_model': 'project.ticket',
                    'view_mode': 'kanban,list,form',
                    'domain': [('sprint_id', '=', self.id)],
                    'context': {
                        'default_sprint_id': self.id,
                        'default_project_id': self.project_id.id
                    }
                }












