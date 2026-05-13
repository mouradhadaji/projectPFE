from odoo import models, fields, api, _


class JiraWorkflowState(models.Model):
    _name = 'jira.workflow.state'
    _description = 'Jira Workflow State'
    _order = 'sequence, name'

    name = fields.Char(string='State Name', required=True)
    project_id = fields.Many2one('jira.project', string='Project', required=True,
                                 ondelete='cascade')

    # State Properties
    sequence = fields.Integer(string='Sequence', default=10)
    is_default = fields.Boolean(string='Default State',
                                help='New tickets will be set to this state')
    is_closed = fields.Boolean(string='Closed State',
                               help='Tickets in this state are considered completed')

    # Display
    fold = fields.Boolean(string='Folded in Kanban',
                          help='This stage is folded in the kanban view')
    color = fields.Integer(string='Color Index', default=0)

    # Description
    description = fields.Text(string='Description')

    # State Category (like Jira)
    category = fields.Selection([
        ('todo', 'To Do'),
        ('in_progress', 'In Progress'),
        ('done', 'Done')
    ], string='Category', default='todo', required=True)

    _sql_constraints = [
        ('name_project_unique', 'unique(name, project_id)',
         'State name must be unique per project!')
    ]

    @api.constrains('is_default', 'project_id')
    def _check_single_default(self):
        for state in self:
            if state.is_default:
                other_defaults = self.search([
                    ('project_id', '=', state.project_id.id),
                    ('is_default', '=', True),
                    ('id', '!=', state.id)
                ])
                if other_defaults:
                    raise ValidationError(
                        _('Only one state can be set as default per project!')
                    )

    def name_get(self):
        result = []
        for state in self:
            name = state.name
            if state.category == 'done':
                name = f"✓ {name}"
            result.append((state.id, name))
        return result