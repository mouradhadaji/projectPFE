from odoo import models, fields, api, _
from odoo.exceptions import ValidationError
from odoo.exceptions import UserError

class JiraProject(models.Model):
    _name = 'jira.project'
    _description = 'Jira Project'
    _inherit = ['mail.thread', 'mail.activity.mixin']
    _order = 'sequence, name'



    name = fields.Char(string='Project Name', required=True, tracking=True)
    key = fields.Char(string='Project Key', required=True, size=10, tracking=True,
                      help='Short key for the project (e.g., PROJ)')
    description = fields.Html(string='Description', tracking=True)
    sequence = fields.Integer(string='Sequence', default=10)
    user_id = fields.Many2one(
        'res.users',
        string='User',
        default=lambda self: self.env.user,

    )
    # Project Details
    project_lead_id = fields.Many2one('res.users', string='Project Lead',
                                      tracking=True, default=lambda self: self.env.user)
    team_ids = fields.Many2many('res.users', 'jira_project_team_rel',
                                'project_id', 'user_id', string='Team Members')

    # Dates
    start_date = fields.Date(string='Start Date', tracking=True)
    end_date = fields.Date(string='End Date', tracking=True)

    # Status
    state = fields.Selection([
        ('draft', 'Draft'),
        ('active', 'Active'),
        ('on_hold', 'On Hold'),
        ('completed', 'Completed'),
        ('cancelled', 'Cancelled')
    ], string='Status', default='draft', tracking=True, required=True)

    # Relations
    sprint_ids = fields.One2many('jira.sprint', 'project_id', string='Sprints')
    ticket_ids = fields.One2many('jira.ticket', 'project_id', string='Tickets')
    workflow_state_ids = fields.One2many('jira.workflow.state', 'project_id',
                                         string='Workflow States')

    # Computed Fields
    sprint_count = fields.Integer(string='Sprint Count', compute='_compute_counts')
    ticket_count = fields.Integer(string='Ticket Count', compute='_compute_counts')
    active_sprint_count = fields.Integer(string='Active Sprints',
                                         compute='_compute_counts')

    # Settings
    active = fields.Boolean(string='Active', default=True)
    color = fields.Integer(string='Color Index', default=0)

    # Avatar/Image
    avatar_128 = fields.Image(string='Avatar', max_width=128, max_height=128)

    @api.depends('sprint_ids', 'ticket_ids', 'ticket_ids.sprint_id')
    def _compute_counts(self):
        for project in self:
            project.sprint_count = len(project.sprint_ids)
            project.ticket_count = len(project.ticket_ids)
            project.active_sprint_count = len(project.sprint_ids.filtered(
                lambda s: s.state == 'active'
            ))
            project.backlog_count = len(project.ticket_ids.filtered(  # ← DANS la boucle !
                lambda t: not t.sprint_id
            ))
    @api.constrains('key')
    def _check_key_unique(self):
        for project in self:
            if self.search_count([('key', '=', project.key), ('id', '!=', project.id)]) > 0:
                raise ValidationError(_('Project key must be unique!'))

    @api.constrains('start_date', 'end_date')
    def _check_dates(self):
        for project in self:
            if project.start_date and project.end_date:
                if project.start_date > project.end_date:
                    raise ValidationError(_('End date must be after start date!'))

    def action_set_active(self):
        self.write({'state': 'active'})

    def action_set_completed(self):
        self.write({'state': 'completed'})

    def action_view_sprints(self):
        return {
            'name': 'Sprints',
            'type': 'ir.actions.act_window',
            'res_model': 'jira.sprint',
            'view_mode': 'kanban,list,form',
            'domain': [('project_id', '=', self.id)],
            'context': {
                'default_project_id': self.id,
                'kanban_view_ref': 'jira_project.view_jira_sprint_kanban'
            },
        }

    def action_view_tickets(self):
        return {
            'name': _('Tickets'),
            'type': 'ir.actions.act_window',
            'res_model': 'jira.ticket',
            'view_mode': 'kanban,list,form',
            'domain': [('project_id', '=', self.id)],
            'context': {'default_project_id': self.id}
        }

    def action_create_sprint_from_project(self):
        """Open sprint creation form with project pre-filled"""
        return {
            'name': _('Create Sprint'),
            'type': 'ir.actions.act_window',
            'res_model': 'jira.sprint',
            'view_mode': 'form',
            'target': 'new',
            'context': {
                'default_project_id': self.id,
                'dialog_size': 'medium'
            }
        }

    def action_create_backlog_ticket(self):

        return {
            'name': _('Add to Backlog'),
            'type': 'ir.actions.act_window',
            'res_model': 'jira.ticket',
            'view_mode': 'form',
            'target': 'new',
            'context': {
                'default_project_id': self.id,
                'default_sprint_id': False,
            }
        }

    def action_create_sprint(self):
        return {
            'type': 'ir.actions.act_window',
            'name': 'New Sprint',
            'res_model': 'jira.sprint',
            'view_mode': 'form',
            'target': 'new',
            'context': {
                'default_project_id': self.id,
            },
        }

    @api.model_create_multi
    def create(self, vals_list):
        if not self.env.user.has_group('jira_project.group_jira_director'):
            raise UserError('Seul un Director peut créer un projet.')
        return super().create(vals_list)

    def write(self, vals):
            if self.env.user.has_group('jira_project.group_jira_director'):
                return super().write(vals)
            raise UserError('Seul un Director peut modifier un projet.')


    def unlink(self):
        if not self.env.user.has_group('jira_project.group_jira_director'):
            raise UserError('Seul un Director peut supprimer un projet.')
        return super().unlink()

    manager_id = fields.Many2one(
        'res.users',
        string='Manager',
        tracking=True,
        help='Manager assigned to this project'
    )

    backlog_ticket_ids = fields.One2many(
        'jira.ticket',
        'project_id',
        string='Product Backlog',
        domain=[('sprint_id', '=', False)]  # Tickets sans sprint = backlog
    )

    backlog_count = fields.Integer(
        string='Backlog Count',
        compute='_compute_counts'
    )