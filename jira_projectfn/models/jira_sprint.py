from odoo import models, fields, api, _
from odoo.exceptions import ValidationError
from datetime import timedelta


class JiraSprint(models.Model):
    """
    Jira Sprint - Time-boxed iteration (typically 2 weeks)
    """
    _name = 'jira.sprint'
    _description = 'Jira Sprint'
    _inherit = ['mail.thread', 'mail.activity.mixin']
    _order = 'start_date desc, name'

    # Basic Info
    name = fields.Char(
        string='Sprint Name',
        required=True,
        tracking=True,
        help='Name of the sprint (e.g., Sprint 1, Sprint Q1-2024)'
    )

    project_id = fields.Many2one(
        'jira.project',
        string='Project',
        required=True,
        ondelete='cascade',
        tracking=True,
        help='Project this sprint belongs to'
    )
    date_start = fields.Date(string='Start Date')
    date_end = fields.Date(string='End Date')

    # Dates
    start_date = fields.Date(
        string='Start Date',
        required=True,
        tracking=True,
        help='Sprint start date'
    )

    end_date = fields.Date(
        string='End Date',
        required=True,
        tracking=True,
        help='Sprint end date'
    )

    # Sprint Details
    goal = fields.Text(
        string='Sprint Goal',
        tracking=True,
        help='What the team aims to achieve in this sprint'
    )

    sequence = fields.Integer(
        string='Sequence',
        default=10,
        help='Order of display'
    )

    # Status
    state = fields.Selection([
        ('draft', 'Draft'),
        ('active', 'Active'),
        ('completed', 'Completed'),
        ('cancelled', 'Cancelled')
    ], string='Status',
        default='draft',
        tracking=True,
        required=True,
        group_expand='_expand_states',
        help='Current status of the sprint')

    # Relations
    ticket_ids = fields.One2many(
        'jira.ticket',
        'sprint_id',
        string='Tickets',
        help='All tickets in this sprint'
    )

    workflow_state_ids = fields.Many2many(
        'jira.workflow.state',
        'sprint_workflow_rel',
        'sprint_id',
        'state_id',
        string='Allowed States',
        help='Workflow states available for tickets in this sprint'
    )

    # Computed Fields
    ticket_count = fields.Integer(
        string='Total Tickets',
        compute='_compute_ticket_stats',
        store=True
    )

    completed_ticket_count = fields.Integer(
        string='Completed Tickets',
        compute='_compute_ticket_stats',
        store=True
    )

    progress = fields.Float(
        string='Progress (%)',
        compute='_compute_ticket_stats',
        store=True
    )

    duration_days = fields.Integer(
        string='Duration (Days)',
        compute='_compute_duration',
        store=True
    )

    # Story Points
    total_story_points = fields.Float(
        string='Total Story Points',
        compute='_compute_story_points',
        store=True
    )

    completed_story_points = fields.Float(
        string='Completed Story Points',
        compute='_compute_story_points',
        store=True
    )

    # Display
    color = fields.Integer(
        string='Color Index',
        default=0
    )

    active = fields.Boolean(
        string='Active',
        default=True
    )

    # Methods
    def _expand_states(self, states, domain):
        """Show all columns even if empty - like Jira"""
        return ['draft', 'active', 'completed', 'cancelled']

    @api.depends('ticket_ids', 'ticket_ids.state_id', 'ticket_ids.state_id.is_closed')
    def _compute_ticket_stats(self):
        """Calculate ticket statistics"""
        for sprint in self:
            total = len(sprint.ticket_ids)
            completed = len(sprint.ticket_ids.filtered(
                lambda t: t.state_id.is_closed
            ))
            sprint.ticket_count = total
            sprint.completed_ticket_count = completed
            sprint.progress = (completed / total * 100) if total > 0 else 0.0

    @api.depends('ticket_ids', 'ticket_ids.story_points',
                 'ticket_ids.state_id', 'ticket_ids.state_id.is_closed')
    def _compute_story_points(self):
        """Calculate story points"""
        for sprint in self:
            sprint.total_story_points = sum(sprint.ticket_ids.mapped('story_points'))
            sprint.completed_story_points = sum(
                sprint.ticket_ids.filtered(
                    lambda t: t.state_id.is_closed
                ).mapped('story_points')
            )

    @api.depends('start_date', 'end_date')
    def _compute_duration(self):
        """Calculate sprint duration in days"""
        for sprint in self:
            if sprint.start_date and sprint.end_date:
                delta = sprint.end_date - sprint.start_date
                sprint.duration_days = delta.days + 1
            else:
                sprint.duration_days = 0

    @api.constrains('start_date', 'end_date')
    def _check_dates(self):
        """Validate date logic"""
        for sprint in self:
            if sprint.start_date and sprint.end_date:
                if sprint.start_date > sprint.end_date:
                    raise ValidationError(_('End date must be after start date!'))

    @api.onchange('project_id')
    def _onchange_project_id(self):
        """Auto-assign workflow states from project"""
        if self.project_id:
            self.workflow_state_ids = self.project_id.workflow_state_ids

    def action_start_sprint(self):
        """Start the sprint"""
        self.write({'state': 'active'})

    def action_complete_sprint(self):
        """Complete the sprint"""
        self.write({'state': 'completed'})

    def action_view_tickets(self):
        """Open tickets view for this sprint"""
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

    @api.model
    def create(self, vals):
        """Create sprint and auto-assign workflow states"""
        sprint = super(JiraSprint, self).create(vals)

        # Auto-assign workflow states from project
        if sprint.project_id and not sprint.workflow_state_ids:
            sprint.workflow_state_ids = sprint.project_id.workflow_state_ids

        return sprint

    def write(self, vals):
        """Override write to handle state changes"""
        res = super(JiraSprint, self).write(vals)

        # Handle state changes if needed
        if 'state' in vals:
            for sprint in self:
                # Add any additional logic when state changes
                pass

        return res

    def action_view_quick_details(self):
        """Open sprint details popup"""
        return {
            'type': 'ir.actions.act_window',
            'name': f'Sprint: {self.name}',
            'res_model': 'jira.sprint',
            'res_id': self.id,
            'view_mode': 'form',
            'target': 'new',
            'context': dict(self.env.context),
        }