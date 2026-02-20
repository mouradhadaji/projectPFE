# -*- coding: utf-8 -*-
from odoo import models, fields, api


class ProjectTicket(models.Model):
    _name = 'project.ticket'
    _description = 'Project Ticket'
    _inherit = ['mail.thread', 'mail.activity.mixin']
    _order = 'priority desc, sequence, id desc'

    name = fields.Char(string='Ticket Number', readonly=True, default='New')
    title = fields.Char(string='Title', required=True, tracking=True)
    description = fields.Html(string='Description')

    project_id = fields.Many2one(
        'project.management',
        string='Project',
        required=True,
        ondelete='cascade',
        tracking=True
    )
    sprint_id = fields.Many2one(
        'project.sprint',
        string='Sprint',
        ondelete='set null',
        tracking=True
    )

    ticket_type = fields.Selection([
        ('epic', 'Epic'),
        ('story', 'Story'),
        ('task', 'Task'),
        ('bug', 'Bug'),
        ('improvement', 'Improvement')
    ], string='Type', default='task', required=True, tracking=True)

    state = fields.Selection([
        ('backlog', 'Backlog'),
        ('todo', 'To Do'),
        ('in_progress', 'In Progress'),
        ('review', 'In Review'),
        ('done', 'Done'),
        ('blocked', 'Blocked')
    ], string='Status', default='backlog', required=True, tracking=True, group_expand='_expand_states')

    priority = fields.Selection([
        ('0', 'Low'),
        ('1', 'Normal'),
        ('2', 'High'),
        ('3', 'Critical')
    ], string='Priority', default='1', tracking=True)

    assigned_to = fields.Many2one('res.users', string='Assigned To', tracking=True)
    reporter_id = fields.Many2one('res.users', string='Reporter', default=lambda self: self.env.user, tracking=True)
    tag_ids = fields.Many2many('project.ticket.tag', string='Tags')

    story_points = fields.Integer(string='Story Points')
    estimated_hours = fields.Float(string='Estimated Hours')
    spent_hours = fields.Float(string='Spent Hours')

    created_date = fields.Datetime(string='Created Date', default=fields.Datetime.now, readonly=True)
    start_date = fields.Datetime(string='Start Date')
    end_date = fields.Datetime(string='End Date')

    sequence = fields.Integer(string='Sequence', default=10)
    color = fields.Integer(string='Color', default=0)
    active = fields.Boolean(default=True)

    @api.model_create_multi
    def create(self, vals_list):
        for vals in vals_list:
            if vals.get('name', 'New') == 'New':
                project_id = vals.get('project_id')
                if project_id:
                    project = self.env['project.management'].browse(project_id)
                    if project and project.key:
                        sequence = self.env['ir.sequence'].next_by_code('project.ticket.sequence') or '0001'
                        vals['name'] = f"{project.key}-{sequence}"
        return super().create(vals_list)

    def _expand_states(self, states, domain, order):
        return [key for key, val in type(self).state.selection]

    def write(self, vals):
        if 'state' in vals:
            for ticket in self:
                if vals['state'] == 'in_progress' and not ticket.start_date:
                    vals['start_date'] = fields.Datetime.now()
                elif vals['state'] == 'done' and not ticket.end_date:
                    vals['end_date'] = fields.Datetime.now()
        return super().write(vals)


class ProjectTicketTag(models.Model):
    _name = 'project.ticket.tag'
    _description = 'Ticket Tag'
    _order = 'name'

    name = fields.Char(string='Tag Name', required=True, translate=True)
    color = fields.Integer(string='Color', default=0)
    active = fields.Boolean(default=True)

    _sql_constraints = [
        ('name_uniq', 'unique (name)', 'Tag name already exists!')
    ]