from odoo import models, fields, api, _
from odoo.exceptions import ValidationError


class JiraTicket(models.Model):
    """
    Jira Ticket/Issue - Story, Task, Bug, Epic, or Sub-task
    """
    _name = 'jira.ticket'
    _description = 'Jira Ticket'
    _inherit = ['mail.thread', 'mail.activity.mixin']
    _order = 'sequence, priority desc, id desc'

    # Basic Info
    name = fields.Char(
        string='Summary',
        required=True,
        tracking=True,
        help='Short description of the ticket'
    )

    ticket_number = fields.Char(
        string='Ticket Number',
        readonly=True,
        copy=False,
        help='Auto-generated ticket number (e.g., PROJ-001)'
    )

    # Relations
    project_id = fields.Many2one(
        'jira.project',
        string='Project',
        required=True,
        ondelete='cascade',
        tracking=True
    )

    sprint_id = fields.Many2one(
        'jira.sprint',
        string='Sprint',
        domain="[('project_id', '=', project_id)]",
        tracking=True,
        help='Sprint this ticket belongs to (optional)'
    )

    # Ticket Type
    ticket_type = fields.Selection([
        ('story', 'Story'),
        ('task', 'Task'),
        ('bug', 'Bug'),
        ('epic', 'Epic'),
        ('subtask', 'Sub-task')
    ], string='Type',
        required=True,
        default='task',
        tracking=True,
        help='Type of ticket')

    # Description
    description = fields.Html(
        string='Description',
        tracking=True,
        help='Detailed description of the ticket'
    )

    # Workflow
    state_id = fields.Many2one(
        'jira.workflow.state',
        string='Status',
        domain="[('project_id', '=', project_id)]",
        tracking=True,
        required=True,
        help='Current workflow state'
    )

    # Priority
    priority = fields.Selection([
        ('0', 'Lowest'),
        ('1', 'Low'),
        ('2', 'Medium'),
        ('3', 'High'),
        ('4', 'Highest')
    ], string='Priority',
        default='2',
        tracking=True,
        help='Priority level of the ticket')

    # Assignment
    assignee_id = fields.Many2one(
        'res.users',
        string='Assignee',
        tracking=True,
        help='Person assigned to work on this ticket'
    )

    reporter_id = fields.Many2one(
        'res.users',
        string='Reporter',
        default=lambda self: self.env.user,
        tracking=True,
        help='Person who created this ticket'
    )

    # Estimation
    story_points = fields.Float(
        string='Story Points',
        tracking=True,
        help='Complexity/effort estimation in story points'
    )

    original_estimate = fields.Float(
        string='Original Estimate (hours)',
        tracking=True,
        help='Initial time estimation in hours'
    )

    remaining_estimate = fields.Float(
        string='Remaining Estimate (hours)',
        tracking=True,
        help='Remaining time to complete in hours'
    )

    time_spent = fields.Float(
        string='Time Spent (hours)',
        tracking=True,
        help='Actual time spent working on this ticket'
    )

    # Dates
    created_date = fields.Datetime(
        string='Created',
        default=fields.Datetime.now,
        readonly=True
    )

    updated_date = fields.Datetime(
        string='Updated',
        readonly=True
    )

    due_date = fields.Date(
        string='Due Date',
        tracking=True,
        help='Target completion date'
    )

    # Labels and Components
    label_ids = fields.Many2many(
        'jira.label',
        string='Labels',
        help='Tags/labels for categorization'
    )

    component_ids = fields.Many2many(
        'jira.component',
        string='Components',
        help='Components this ticket affects'
    )

    # Epic Link
    epic_id = fields.Many2one(
        'jira.ticket',
        string='Epic Link',
        domain="[('ticket_type', '=', 'epic'), ('project_id', '=', project_id)]",
        tracking=True,
        help='Parent epic for this ticket'
    )

    # Parent/Subtask relationship
    parent_id = fields.Many2one(
        'jira.ticket',
        string='Parent Task',
        domain="[('ticket_type', '!=', 'subtask'), ('project_id', '=', project_id)]",
        tracking=True,
        help='Parent ticket if this is a subtask'
    )

    subtask_ids = fields.One2many(
        'jira.ticket',
        'parent_id',
        string='Sub-tasks',
        help='Sub-tasks of this ticket'
    )

    # Linked Issues
    blocked_by_ids = fields.Many2many(
        'jira.ticket',
        'ticket_blocker_rel',
        'ticket_id',
        'blocker_id',
        string='Blocked By',
        help='This ticket is blocked by these tickets'
    )

    blocks_ids = fields.Many2many(
        'jira.ticket',
        'ticket_blocker_rel',
        'blocker_id',
        'ticket_id',
        string='Blocks',
        help='This ticket blocks these tickets'
    )

    related_ids = fields.Many2many(
        'jira.ticket',
        'ticket_related_rel',
        'ticket_id',
        'related_id',
        string='Related To',
        help='Related tickets'
    )

    # Attachments
    attachment_ids = fields.One2many(
        'ir.attachment',
        'res_id',
        domain=[('res_model', '=', 'jira.ticket')],
        string='Attachments',
        help='Files attached to this ticket'
    )

    # Computed Fields
    subtask_count = fields.Integer(
        string='Subtasks',
        compute='_compute_subtask_count',
        store=True
    )

    attachment_count = fields.Integer(
        string='Attachments',
        compute='_compute_attachment_count',
        store=True
    )

    is_overdue = fields.Boolean(
        string='Overdue',
        compute='_compute_is_overdue',
        store=True
    )

    # Display Fields
    sequence = fields.Integer(
        string='Sequence',
        default=10
    )

    color = fields.Integer(
        string='Color Index',
        compute='_compute_color',
        store=True
    )

    kanban_state = fields.Selection([
        ('normal', 'In Progress'),
        ('done', 'Ready'),
        ('blocked', 'Blocked')
    ], string='Kanban State',
        default='normal',
        tracking=True,
        help='State for Kanban view')

    active = fields.Boolean(
        string='Active',
        default=True
    )

    # Compute Methods
    @api.depends('priority')
    def _compute_color(self):
        """Set color based on priority"""
        for ticket in self:
            ticket.color = int(ticket.priority)

    @api.depends('subtask_ids')
    def _compute_subtask_count(self):
        """Count subtasks"""
        for ticket in self:
            ticket.subtask_count = len(ticket.subtask_ids)

    @api.depends('attachment_ids')
    def _compute_attachment_count(self):
        """Count attachments"""
        for ticket in self:
            ticket.attachment_count = len(ticket.attachment_ids)

    @api.depends('due_date', 'state_id.is_closed')
    def _compute_is_overdue(self):
        """Check if ticket is overdue"""
        today = fields.Date.today()
        for ticket in self:
            if ticket.due_date and not ticket.state_id.is_closed:
                ticket.is_overdue = ticket.due_date < today
            else:
                ticket.is_overdue = False

    @api.model
    def create(self, vals):
        """Create ticket with auto-generated number"""
        # Generate ticket number
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
        """Update timestamp on write"""
        vals['updated_date'] = fields.Datetime.now()
        return super(JiraTicket, self).write(vals)

    @api.onchange('project_id')
    def _onchange_project_id(self):
        """Set default state when project changes"""
        if self.project_id:
            default_state = self.project_id.workflow_state_ids.filtered(
                lambda s: s.is_default
            )
            if default_state:
                self.state_id = default_state[0]

    @api.constrains('parent_id')
    def _check_parent_recursion(self):
        """Prevent recursive parent relationships"""
        if not self._check_recursion():
            raise ValidationError(_('You cannot create recursive ticket hierarchy!'))

    def action_view_subtasks(self):
        """Open subtasks view"""
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


class JiraLabel(models.Model):
    """Labels for categorizing tickets"""
    _name = 'jira.label'
    _description = 'Jira Label'

    name = fields.Char(string='Label', required=True)
    color = fields.Integer(string='Color Index', default=0)


class JiraComponent(models.Model):
    """Components/modules affected by tickets"""
    _name = 'jira.component'
    _description = 'Jira Component'

    name = fields.Char(string='Component', required=True)
    description = fields.Text(string='Description')
    lead_id = fields.Many2one('res.users', string='Component Lead')