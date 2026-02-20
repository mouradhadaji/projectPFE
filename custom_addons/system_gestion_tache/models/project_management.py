# -*- coding: utf-8 -*-
from odoo import models, fields, api


class ProjectManagement(models.Model):
    _name = 'project.management'
    _description = 'Gestion de Projets'
    _inherit = ['mail.thread', 'mail.activity.mixin']
    _order = 'create_date desc'

    name = fields.Char(
        string='Nom du Projet',
        required=True,
        tracking=True
    )

    key = fields.Char(
        string='Clé Projet',
        required=True,
        size=10,
        help="Ex: PROJ, TASK (sera utilisé pour nommer les tickets)"
    )

    description = fields.Html(string='Description')

    methodology = fields.Selection([
        ('kanban', 'Kanban'),
        ('scrum', 'Scrum')
    ], string='Méthodologie', default='scrum', required=True)

    state = fields.Selection([
        ('draft', 'Brouillon'),
        ('active', 'Actif'),
        ('completed', 'Terminé'),
        ('archived', 'Archivé')
    ], string='État', default='draft', tracking=True)

    # Relations
    team_member_ids = fields.Many2many(
        'res.users',
        string='Membres de l\'équipe'
    )

    ticket_ids = fields.One2many(
        'project.ticket',
        'project_id',
        string='Tickets'
    )

    sprint_ids = fields.One2many(
        'project.sprint',
        'project_id',
        string='Sprints'
    )

    # Champs calculés
    ticket_count = fields.Integer(
        string='Nombre de Tickets',
        compute='_compute_ticket_count'
    )

    sprint_count = fields.Integer(
        string='Nombre de Sprints',
        compute='_compute_sprint_count'
    )

    @api.depends('ticket_ids')
    def _compute_ticket_count(self):
        for project in self:
            project.ticket_count = len(project.ticket_ids)

    @api.depends('sprint_ids')
    def _compute_sprint_count(self):
        for project in self:
            project.sprint_count = len(project.sprint_ids)

    # Action pour voir les tickets
    def action_view_tickets(self):
        self.ensure_one()
        return {
            'name': f'Tickets - {self.name}',
            'type': 'ir.actions.act_window',
            'res_model': 'project.ticket',
            'view_mode': 'kanban,tree,form',
            'domain': [('project_id', '=', self.id)],
            'context': {
                'default_project_id': self.id,
                'search_default_project_id': self.id
            }
        }