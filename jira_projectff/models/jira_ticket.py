from odoo import models, fields, api, _
from odoo.exceptions import ValidationError


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

    # Ticket Type
    ticket_type = fields.Selection([
        ('story', 'Story'),
        ('task', 'Task'),
        ('bug', 'Bug'),
        ('epic', 'Epic'),
        ('subtask', 'Sub-task')
    ], string='Type', required=True, default='task', tracking=True)

    # Description
    description = fields.Html(string='Description', tracking=True)

    # Workflow
    state_id = fields.Many2one('jira.workflow.state', string='Status',
                               domain="[('project_id', '=', project_id)]",
                               tracking=True, )

    # Priority
    priority = fields.Selection([
        ('0', 'Lowest'),
        ('1', 'Low'),
        ('2', 'Medium'),
        ('3', 'High'),
        ('4', 'Highest')
    ], string='Priority', default='2', tracking=True)

    # Assignment
    assignee_id = fields.Many2one('res.users', string='Assignee', tracking=True)
    reporter_id = fields.Many2one('res.users', string='Reporter',
                                  default=lambda self: self.env.user,
                                  tracking=True)

    # Estimation
    story_points = fields.Float(string='Story Points', tracking=True)
    original_estimate = fields.Float(string='Original Estimate (hours)', tracking=True)
    remaining_estimate = fields.Float(string='Remaining Estimate (hours)', tracking=True)
    time_spent = fields.Float(string='Time Spent (hours)', tracking=True)

    # Dates
    created_date = fields.Datetime(string='Created', default=fields.Datetime.now,
                                   readonly=True)
    updated_date = fields.Datetime(string='Updated', readonly=True)
    due_date = fields.Date(string='Due Date', tracking=True)

    # Labels and Components
    label_ids = fields.Many2many('jira.label', string='Labels')
    component_ids = fields.Many2many('jira.component', string='Components')

    # Epic Link
    epic_id = fields.Many2one('jira.ticket', string='Epic Link',
                              domain="[('ticket_type', '=', 'epic'), ('project_id', '=', project_id)]",
                              tracking=True)

    # Parent/Subtask relationship
    parent_id = fields.Many2one('jira.ticket', string='Parent Task',
                                domain="[('ticket_type', '!=', 'subtask'), ('project_id', '=', project_id)]",
                                tracking=True)
    subtask_ids = fields.One2many('jira.ticket', 'parent_id', string='Sub-tasks')

    # Linked Issues
    blocked_by_ids = fields.Many2many('jira.ticket', 'ticket_blocker_rel',
                                      'ticket_id', 'blocker_id',
                                      string='Blocked By')
    blocks_ids = fields.Many2many('jira.ticket', 'ticket_blocker_rel',
                                  'blocker_id', 'ticket_id',
                                  string='Blocks')
    related_ids = fields.Many2many('jira.ticket', 'ticket_related_rel',
                                   'ticket_id', 'related_id',
                                   string='Related To')

    # Attachments
    attachment_ids = fields.One2many('ir.attachment', 'res_id',
                                     domain=[('res_model', '=', 'jira.ticket')],
                                     string='Attachments')

    # Computed Fields
    subtask_count = fields.Integer(string='Subtasks', compute='_compute_subtask_count')
    attachment_count = fields.Integer(string='Attachments',
                                      compute='_compute_attachment_count')
    is_overdue = fields.Boolean(string='Overdue', compute='_compute_is_overdue')

    # Display Fields
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
    # Ticket Status for Kanban Drag & Drop
    ticket_status = fields.Selection([
        ('draft', 'Draft'),
        ('in_progress', 'In Progress'),
        ('done', 'Done'),
        ('complete', 'Complete')
    ], string='Ticket Status', default='draft', tracking=True, group_expand='_expand_ticket_status')
    active = fields.Boolean(string='Active', default=True)

    @api.model
    def _read_group_ticket_status(self, stages, domain, order):
        """Always show all ticket status columns in kanban view"""
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
        """Force all ticket status columns to always show in kanban"""
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

    @api.model
    def create(self, vals):
        if not vals.get('ticket_number'):
            project = self.env['jira.project'].browse(vals.get('project_id'))
            sequence = self.env['ir.sequence'].next_by_code('jira.ticket.sequence') or '0001'
            vals['ticket_number'] = f"{project.key}-{sequence}"

        # Set default state from project
        if not vals.get('state_id') and vals.get('project_id'):
            project = self.env['jira.project'].browse(vals['project_id'])
            default_state = project.workflow_state_ids.filtered(lambda s: s.is_default)
            if default_state:
                vals['state_id'] = default_state[0].id

        vals['updated_date'] = fields.Datetime.now()
        return super(JiraTicket, self).create(vals)

    def write(self, vals):
        vals['updated_date'] = fields.Datetime.now()
        return super(JiraTicket, self).write(vals)

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
            'type': '',
            'res_model': 'jira.ticket',
            'view_mode': 'list,kanban,form',
            'domain': [('parent_id', '=', self.id)],
            'context': {
                'default_parent_id': self.id,
                'default_project_id': self.project_id.id,
                'default_ticket_type': 'subtask'
            }
        }


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

