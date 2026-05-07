# -*- coding: utf-8 -*-
from odoo import models, fields, api
from odoo.exceptions import UserError


class JiraMoveToSprintWizard(models.TransientModel):
    _name = 'jira.move.to.sprint.wizard'
    _description = 'Move Ticket to Sprint'

    ticket_id = fields.Many2one(
        'jira.ticket',
        string='Ticket',
        required=True,
    )
    sprint_id = fields.Many2one(
        'jira.sprint',
        string='Target Sprint',
        required=True,
        domain=[('state', 'in', ('draft', 'active'))],
    )
    project_id = fields.Many2one(
        'jira.project',
        string='Project',
        related='ticket_id.project_id',
        readonly=True,
    )

    @api.model
    def default_get(self, fields_list):
        res = super().default_get(fields_list)
        ctx = self.env.context
        if ctx.get('default_ticket_id'):
            res['ticket_id'] = ctx['default_ticket_id']
        return res

    def action_move(self):
        self.ensure_one()
        if not self.sprint_id:
            raise UserError('Please select a sprint.')
        self.ticket_id.write({
            'sprint_id': self.sprint_id.id,
            'ticket_status': 'draft',
        })
        return {'type': 'ir.actions.act_window_close'}

    def action_cancel(self):
        return {'type': 'ir.actions.act_window_close'}