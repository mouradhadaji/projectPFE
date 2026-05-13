from odoo import models, fields, api, _
from odoo.exceptions import ValidationError
from odoo.exceptions import UserError


class JiraTicket(models.Model):
    _name = 'jira.ticket'
    _description = 'Jira Ticket'
    _inherit = ['mail.thread', 'mail.activity.mixin']
    _order = 'sequence, priority desc, id desc'

    name = fields.Char(string='Summary', required=True, tracking=True)
    ticket_number = fields.Char(string='Ticket Number', readonly=True, copy=False)

    # Relations
    project_id = fields.Many2one('jira.project', string='Project', required=True,
                                 ondelete='cascade', tracking=True)
    sprint_id = fields.Many2one('jira.sprint', string='Sprint',
                                domain="[('project_id', '=', project_id)]",
                                tracking=True)

    ticket_type = fields.Selection([
        ('story', 'Story'),
        ('task', 'Task'),
        ('bug', 'Bug'),
        ('epic', 'Epic'),
        ('subtask', 'Sub-task')
    ], string='Type', required=True, default='task', tracking=True)

    description = fields.Html(string='Description')

    state_id = fields.Many2one('jira.workflow.state', string='Status',
                               domain="[('project_id', '=', project_id)]",
                               tracking=True)

    priority = fields.Selection([
        ('0', 'Lowest'),
        ('1', 'Low'),
        ('2', 'Medium'),
        ('3', 'High'),
        ('4', 'Highest')
    ], string='Priority', default='2', tracking=True)

    assignee_id = fields.Many2one('res.users', string='Assignee', tracking=True)
    reporter_id = fields.Many2one('res.users', string='Reporter',
                                  default=lambda self: self.env.user,
                                  tracking=True)

    story_points = fields.Float(string='Story Points', tracking=True)
    original_estimate = fields.Float(string='Original Estimate (hours)', tracking=True)
    remaining_estimate = fields.Float(string='Remaining Estimate (hours)', tracking=True)
    time_spent = fields.Float(string='Time Spent (hours)', tracking=True)

    created_date = fields.Datetime(string='Created', default=fields.Datetime.now,
                                   readonly=True)
    updated_date = fields.Datetime(string='Updated', readonly=True)
    due_date = fields.Date(string='Due Date', tracking=True)

    label_ids = fields.Many2many('jira.label', string='Labels')
    component_ids = fields.Many2many('jira.component', string='Components')

    epic_id = fields.Many2one('jira.ticket', string='Epic Link',
                              domain="[('ticket_type', '=', 'epic'), ('project_id', '=', project_id)]",
                              tracking=True)

    parent_id = fields.Many2one('jira.ticket', string='Parent Task',
                                domain="[('ticket_type', '!=', 'subtask'), ('project_id', '=', project_id)]",
                                tracking=True)
    subtask_ids = fields.One2many('jira.ticket', 'parent_id', string='Sub-tasks')

    blocked_by_ids = fields.Many2many('jira.ticket', 'ticket_blocker_rel',
                                      'ticket_id', 'blocker_id',
                                      string='Blocked By')
    blocks_ids = fields.Many2many('jira.ticket', 'ticket_blocker_rel',
                                  'blocker_id', 'ticket_id',
                                  string='Blocks')
    related_ids = fields.Many2many('jira.ticket', 'ticket_related_rel',
                                   'ticket_id', 'related_id',
                                   string='Related To')

    attachment_ids = fields.One2many('ir.attachment', 'res_id',
                                     domain=[('res_model', '=', 'jira.ticket')],
                                     string='Attachments')

    subtask_count = fields.Integer(string='Subtasks', compute='_compute_subtask_count')
    attachment_count = fields.Integer(string='Attachments',
                                      compute='_compute_attachment_count')
    is_overdue = fields.Boolean(string='Overdue', compute='_compute_is_overdue')

    sequence = fields.Integer(string='Sequence', default=10)
    color = fields.Integer(string='Color Index', compute='compute_color')

    @api.depends('priority')
    def compute_color(self):
        for ticket in self:
            ticket.color = int(ticket.priority)

    kanban_state = fields.Selection([
        ('normal', 'In Progress'),
        ('done', 'Ready'),
        ('blocked', 'Blocked')
    ], string='Kanban State', default='normal')

    is_flagged = fields.Boolean(string='Flagged', default=False, tracking=True)

    ticket_status = fields.Selection([
        ('draft', 'Draft'),
        ('in_progress', 'In Progress'),
        ('done', 'Done'),
        ('complete', 'Complete')
    ], string='Ticket Status', default='draft', tracking=True,
       group_expand='_expand_ticket_status')

    active = fields.Boolean(string='Active', default=True)

    @api.model
    def _read_group_ticket_status(self, stages, domain, order):
        return ['draft', 'in_progress', 'done', 'complete']

    _group_by_full = {
        'ticket_status': _read_group_ticket_status,
    }

    @api.depends('subtask_ids')
    def _compute_subtask_count(self):
        for ticket in self:
            ticket.subtask_count = len(ticket.subtask_ids)

    @api.model
    def _expand_ticket_status(self, states, domain, order=None):
        return ['draft', 'in_progress', 'done', 'complete']

    @api.depends('attachment_ids')
    def _compute_attachment_count(self):
        for ticket in self:
            ticket.attachment_count = len(ticket.attachment_ids)

    @api.depends('due_date', 'state_id.is_closed')
    def _compute_is_overdue(self):
        today = fields.Date.today()
        for ticket in self:
            if ticket.due_date and not ticket.state_id.is_closed:
                ticket.is_overdue = ticket.due_date < today
            else:
                ticket.is_overdue = False

    @api.model_create_multi
    def create(self, vals_list):
        if not self.env.user.has_group('jira_project.group_jira_manager'):
            raise UserError('Vous n\'avez pas le droit de créer des tickets.')
        for vals in vals_list:
            if not vals.get('ticket_number'):
                project = self.env['jira.project'].browse(vals.get('project_id'))
                sequence = self.env['ir.sequence'].next_by_code('jira.ticket.sequence') or '0001'
                vals['ticket_number'] = f"{project.key}-{sequence}"
            if not vals.get('state_id') and vals.get('project_id'):
                project = self.env['jira.project'].browse(vals['project_id'])
                default_state = project.workflow_state_ids.filtered(lambda s: s.is_default)
                if default_state:
                    vals['state_id'] = default_state[0].id
            vals['updated_date'] = fields.Datetime.now()
        return super().create(vals_list)

    def write(self, vals):
        if not self.env.user.has_group('jira_project.group_jira_manager'):
            allowed_fields = {'ticket_status', 'kanban_state', 'sequence', 'priority'}
            forbidden = set(vals.keys()) - allowed_fields
            if forbidden:
                raise UserError('Vous ne pouvez modifier que le statut du ticket.')
        vals['updated_date'] = fields.Datetime.now()
        return super().write(vals)

    def unlink(self):
        if not self.env.user.has_group('jira_project.group_jira_director'):
            raise UserError('Seul un Director peut supprimer des tickets.')
        return super().unlink()

    @api.onchange('project_id')
    def _onchange_project_id(self):
        if self.project_id:
            default_state = self.project_id.workflow_state_ids.filtered(
                lambda s: s.is_default
            )
            if default_state:
                self.state_id = default_state[0]

    @api.constrains('parent_id')
    def _check_parent_recursion(self):
        if not self._check_recursion():
            raise ValidationError(_('You cannot create recursive ticket hierarchy!'))

    def action_view_subtasks(self):
        return {
            'name': _('Sub-tasks'),
            'type': 'ir.actions.act_window',
            'res_model': 'jira.ticket',
            'view_mode': 'list,kanban,form',
            'domain': [('parent_id', '=', self.id)],
            'context': {
                'default_parent_id': self.id,
                'default_project_id': self.project_id.id,
                'default_ticket_type': 'subtask'
            }
        }

    def action_move_to_sprint(self):
        """Ouvre un wizard pour choisir le sprint cible"""
        active_sprints = self.env['jira.sprint'].search([
            ('project_id', '=', self.project_id.id),
            ('state', 'in', ['draft', 'active'])
        ])
        if not active_sprints:
            raise UserError(
                "Aucun sprint disponible pour ce projet. "
                "Créez d'abord un sprint."
            )
        return {
            'type': 'ir.actions.act_window',
            'name': 'Déplacer vers un Sprint',
            'res_model': 'jira.move.to.sprint.wizard',
            'view_mode': 'form',
            'target': 'new',
            'context': {
                'default_ticket_id': self.id,
                'default_project_id': self.project_id.id,
            },
        }

    def action_add_to_sprint(self):
        """Ajoute la tâche au sprint depuis le planning"""
        sprint_id = (
            self.env.context.get('active_id') or
            self.env.context.get('default_sprint_id')
        )
        if sprint_id:
            self.write({'sprint_id': sprint_id})

    def action_remove_from_sprint(self):
        """Retire la tâche du sprint → remet dans le backlog"""
        self.write({'sprint_id': False})


class JiraLabel(models.Model):
    _name = 'jira.label'
    _description = 'Jira Label'

    name = fields.Char(string='Label', required=True)
    color = fields.Integer(string='Color Index', default=0)


class JiraComponent(models.Model):
    _name = 'jira.component'
    _description = 'Jira Component'

    name = fields.Char(string='Component', required=True)
    description = fields.Text(string='Description')
    lead_id = fields.Many2one('res.users', string='Component Lead')

    # Ajouter ce champ
    history_ids = fields.One2many(
        'jira.ticket.history', 'ticket_id',
        string='Historique des statuts'
    )

    # Ajouter cette méthode
    def write(self, vals):
        if 'ticket_status' in vals:
            for ticket in self:
                if ticket.ticket_status != vals['ticket_status']:
                    self.env['jira.ticket.history'].create({
                        'ticket_id': ticket.id,
                        'old_status': ticket.ticket_status,
                        'new_status': vals['ticket_status'],
                        'change_date': fields.Datetime.now(),
                        'user_id': self.env.user.id,
                    })
        return super().write(vals)