from odoo import models, fields, api, _
from odoo.exceptions import ValidationError, UserError
from datetime import timedelta


class JiraSprint(models.Model):
    _name = 'jira.sprint'
    _description = 'Jira Sprint'
    _inherit = ['mail.thread', 'mail.activity.mixin']
    _order = 'start_date desc, name'

    name = fields.Char(string='Sprint Name', required=True, tracking=True)
    project_id = fields.Many2one('jira.project', string='Project',
                                 required=True, ondelete='cascade', tracking=True)
    start_date = fields.Date(string='Start Date', required=True, tracking=True)
    end_date = fields.Date(string='End Date', required=True, tracking=True)
    goal = fields.Text(string='Sprint Goal', tracking=True)
    sequence = fields.Integer(string='Sequence', default=10)

    state = fields.Selection([
        ('draft', 'Draft'),
        ('active', 'Active'),
        ('completed', 'Completed'),
        ('cancelled', 'Cancelled')
    ], string='Status', default='draft', tracking=True,
       required=True, group_expand='_expand_states')

    ticket_ids = fields.One2many('jira.ticket', 'sprint_id', string='Tickets')
    workflow_state_ids = fields.Many2many(
        'jira.workflow.state', 'sprint_workflow_rel',
        'sprint_id', 'state_id', string='Allowed States')

    ticket_count = fields.Integer(compute='_compute_ticket_stats', store=True)
    completed_ticket_count = fields.Integer(compute='_compute_ticket_stats', store=True)
    progress = fields.Float(compute='_compute_ticket_stats', store=True)
    duration_days = fields.Integer(compute='_compute_duration', store=True)
    total_story_points = fields.Float(compute='_compute_story_points', store=True)
    completed_story_points = fields.Float(compute='_compute_story_points', store=True)
    color = fields.Integer(default=0)
    active = fields.Boolean(default=True)

    # Backlog disponible pour ce sprint (tâches du projet sans sprint)
    backlog_ticket_ids = fields.One2many(
        'jira.ticket',
        compute='_compute_backlog_tickets',
        string='Backlog disponible',
    )

    def _expand_states(self, states, domain):
        return ['draft', 'active', 'completed', 'cancelled']

    @api.depends('project_id', 'project_id.ticket_ids',
                 'project_id.ticket_ids.sprint_id')
    def _compute_backlog_tickets(self):
        for sprint in self:
            if sprint.project_id:
                sprint.backlog_ticket_ids = sprint.project_id.ticket_ids.filtered(
                    lambda t: not t.sprint_id
                )
            else:
                sprint.backlog_ticket_ids = self.env['jira.ticket']

    @api.depends('ticket_ids', 'ticket_ids.state_id.is_closed')
    def _compute_ticket_stats(self):
        for sprint in self:
            total = len(sprint.ticket_ids)
            completed = len(sprint.ticket_ids.filtered(
                lambda t: t.state_id.is_closed))
            sprint.ticket_count = total
            sprint.completed_ticket_count = completed
            sprint.progress = (completed / total * 100) if total > 0 else 0.0

    @api.depends('ticket_ids', 'ticket_ids.story_points',
                 'ticket_ids.state_id.is_closed')
    def _compute_story_points(self):
        for sprint in self:
            sprint.total_story_points = sum(
                sprint.ticket_ids.mapped('story_points'))
            sprint.completed_story_points = sum(
                sprint.ticket_ids.filtered(
                    lambda t: t.state_id.is_closed
                ).mapped('story_points'))

    @api.depends('start_date', 'end_date')
    def _compute_duration(self):
        for sprint in self:
            if sprint.start_date and sprint.end_date:
                sprint.duration_days = (
                    sprint.end_date - sprint.start_date).days + 1
            else:
                sprint.duration_days = 0

    @api.constrains('start_date', 'end_date')
    def _check_dates(self):
        for sprint in self:
            if sprint.start_date and sprint.end_date:
                if sprint.start_date > sprint.end_date:
                    raise ValidationError(
                        _('End date must be after start date!'))

    @api.onchange('project_id')
    def _onchange_project_id(self):
        if self.project_id:
            self.workflow_state_ids = self.project_id.workflow_state_ids

    # ── Actions ──────────────────────────────────────────────────

    def action_sprint_planning(self):
        """Ouvre la vue Sprint Planning dédiée"""
        return {
            'type': 'ir.actions.act_window',
            'name': f'Sprint Planning — {self.name}',
            'res_model': 'jira.sprint',
            'view_mode': 'form',
            'res_id': self.id,
            'view_id': self.env.ref(
                'jira_project.view_jira_sprint_planning_form'
            ).id,
            'target': 'current',
        }

    def action_start_sprint(self):
        """Démarre le sprint après vérification"""
        if not self.ticket_ids:
            raise UserError(
                "Impossible de démarrer un sprint vide. "
                "Ajoutez des tâches depuis le backlog."
            )
        self.write({'state': 'active'})
        return {
            'type': 'ir.actions.act_window',
            'name': f'Sprint Board — {self.name}',
            'res_model': 'jira.ticket',
            'view_mode': 'kanban,list',
            'domain': [('sprint_id', '=', self.id)],
            'context': {'default_sprint_id': self.id},
        }

    def action_complete_sprint(self):
        """Termine le sprint"""
        self.write({'state': 'completed'})

    def action_view_tickets(self):
        return {
            'name': _('Sprint Tickets'),
            'type': 'ir.actions.act_window',
            'res_model': 'jira.ticket',
            'view_mode': 'kanban,list,form',
            'domain': [('sprint_id', '=', self.id)],
            'context': {
                'default_sprint_id': self.id,
                'default_project_id': self.project_id.id,
            }
        }

    def action_view_quick_details(self):
        return {
            'type': 'ir.actions.act_window',
            'name': f'Sprint: {self.name}',
            'res_model': 'jira.sprint',
            'res_id': self.id,
            'view_mode': 'form',
            'target': 'new',
            'context': dict(self.env.context),
        }

    # ── Security ─────────────────────────────────────────────────

    @api.model_create_multi
    def create(self, vals_list):
        if not self.env.user.has_group('jira_project.group_jira_manager'):
            raise UserError(_('Vous n\'avez pas le droit de créer un sprint.'))
        sprints = super().create(vals_list)
        for sprint in sprints:
            if sprint.project_id and not sprint.workflow_state_ids:
                sprint.workflow_state_ids = sprint.project_id.workflow_state_ids
        return sprints

    def write(self, vals):
        if not self.env.user.has_group('jira_project.group_jira_manager'):
            raise UserError(
                _('Vous n\'avez pas le droit de modifier un sprint.'))
        return super().write(vals)

    def unlink(self):
        if not self.env.user.has_group('jira_project.group_jira_director'):
            raise UserError(
                _('Seul un Director peut supprimer un sprint.'))
        return super().unlink()