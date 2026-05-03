# -*- coding: utf-8 -*-
from odoo import models, fields, api


class JiraMeeting(models.Model):
    _name = 'jira.meeting'
    _description = 'Jira Team Meeting'
    _order = 'meeting_date asc'

    name = fields.Char(string='Meeting Title', required=True)
    meeting_date = fields.Datetime(string='Date & Time', required=True)
    duration = fields.Float(string='Duration (hours)', default=1.0)
    project_id = fields.Many2one('jira.project', string='Project')
    participant_ids = fields.Many2many('res.users', string='Participants')
    notes = fields.Text(string='Agenda / Notes')
    state = fields.Selection([
        ('scheduled', 'Scheduled'),
        ('done', 'Done'),
        ('cancelled', 'Cancelled'),
    ], string='Status', default='scheduled')

    @api.model
    def get_upcoming_meetings(self, project_ids=None):
        from datetime import datetime
        user = self.env.user
        domain = [
            ('meeting_date', '>=', fields.Datetime.now()),
            ('state', '=', 'scheduled'),
            '|',
            ('participant_ids', 'in', [user.id]),
            ('create_uid', '=', user.id),
        ]
        if project_ids:
            domain.append(('project_id', 'in', project_ids))
        meetings = self.search(domain, order='meeting_date asc', limit=10)

        result = []
        for m in meetings:
            result.append({
                'id': m.id,
                'name': m.name,
                'date': m.meeting_date.strftime('%d %b %Y'),
                'time': m.meeting_date.strftime('%H:%M'),
                'duration': m.duration,
                'meeting_type': m.meeting_type or 'presentiel',
                'project': m.project_id.name if m.project_id else '',
                'notes': m.notes or '',
                'participants': [{'name': p.name, 'initials': ''.join([n[0].upper() for n in p.name.split()[:2]])} for p in m.participant_ids],
                'state': m.state,
            })
        return result

    @api.model
    def create_meeting(self, vals):
        from datetime import datetime
        if vals.get('meeting_date'):
            vals['meeting_date'] = fields.Datetime.from_string(vals['meeting_date'])
        meeting = self.create(vals)
        return {'id': meeting.id, 'name': meeting.name}

    meeting_type = fields.Selection([
        ('presentiel', 'Présentiel'),
        ('en_ligne', 'En Ligne'),
    ], string='Type', default='presentiel')

    @api.model
    def update_meeting(self, meeting_id, vals):
        meeting = self.browse(meeting_id)
        if not meeting:
            return {'success': False, 'error': 'Meeting not found'}

        if vals.get('meeting_date'):
            vals['meeting_date'] = fields.Datetime.from_string(vals['meeting_date'])

        meeting.write(vals)
        return {
            'success': True,
            'id': meeting.id,
            'name': meeting.name
        }

    meet_url = fields.Char(string='Google Meet URL')