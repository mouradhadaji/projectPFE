# -*- coding: utf-8 -*-
from odoo import models, fields, api, _
from odoo.exceptions import UserError


class JiraCommunicationHub(models.TransientModel):
    """
    Communication Hub - Quick Action Center
    Allows users to quickly access standup/meeting/announcement
    without needing to navigate channels first.
    """
    _name = 'jira.communication.hub'
    _description = 'Communication'

    project_id = fields.Many2one(
        'jira.project',
        string='Project',
        help='Select your project to access communication features',
    )

    # ────────────────────────────────────────────────
    # HELPER : Get or create communication channel
    # ────────────────────────────────────────────────
    def _get_or_create_channel(self, project_id):
        """
        Find existing channel for project, or create new one.
        Returns: communication channel record
        """
        if not project_id:
            raise UserError(_("Please select a project first."))

        project = self.env['jira.project'].browse(project_id)

        # Search existing channel
        channel = self.env['jira.communication.channel'].search([
            ('project_id', '=', project_id),
            ('state', '=', 'active'),
        ], limit=1)

        # Create if not exists
        if not channel:
            # Get members from project
            users = project.team_ids
            if project.manager_id:
                users |= project.manager_id

            channel = self.env['jira.communication.channel'].create({
                'name': 'Channel - %s' % project.name,
                'project_id': project_id,
                'channel_type': 'project',
                'member_ids': [(6, 0, users.ids)],
            })

        return channel

    # ────────────────────────────────────────────────
    # QUICK ACTIONS
    # ────────────────────────────────────────────────
    def action_quick_standup(self):
        """Quick : Open Daily Standup form"""
        self.ensure_one()
        channel = self._get_or_create_channel(self.project_id.id)

        return {
            'type': 'ir.actions.act_window',
            'name': 'Daily Standup',
            'res_model': 'jira.standup.entry',
            'view_mode': 'form',
            'target': 'new',
            'context': {
                'default_channel_id': channel.id,
            },
        }

    def action_quick_meeting(self):
        """Quick : Schedule a Meeting"""
        self.ensure_one()
        channel = self._get_or_create_channel(self.project_id.id)

        return {
            'type': 'ir.actions.act_window',
            'name': 'Schedule a Meeting',
            'res_model': 'jira.meeting',
            'view_mode': 'form',
            'target': 'new',
            'context': {
                'default_communication_channel_id': channel.id,
                'default_project_id': channel.project_id.id,
                'default_participant_ids': [(6, 0, channel.member_ids.ids)],
                'default_name': "Meeting - %s" % channel.name,
            },
        }

    def action_quick_announcement(self):
        """Quick : New Announcement"""
        self.ensure_one()
        channel = self._get_or_create_channel(self.project_id.id)

        return {
            'type': 'ir.actions.act_window',
            'name': 'New Announcement',
            'res_model': 'jira.channel.message',
            'view_mode': 'form',
            'target': 'new',
            'context': {
                'default_channel_id': channel.id,
                'default_recipient_ids': [(6, 0, channel.member_ids.ids)],
            },
        }

    def action_quick_live(self):
        """Quick : Open Odoo Live (Discuss)"""
        self.ensure_one()
        channel = self._get_or_create_channel(self.project_id.id)

        # Check if Discuss channel exists
        discuss_channel = self.env['discuss.channel'].search([
            ('name', '=', 'Live: %s' % channel.name)
        ], limit=1)

        if not discuss_channel:
            partner_ids = channel.member_ids.mapped('partner_id').ids
            if self.env.user.partner_id.id not in partner_ids:
                partner_ids.append(self.env.user.partner_id.id)

            if not partner_ids:
                raise UserError(_(
                    "No members in the channel."
                ))

            discuss_channel = self.env['discuss.channel'].create({
                'name': 'Live: %s' % channel.name,
                'channel_type': 'group',
                'channel_partner_ids': [(4, pid) for pid in partner_ids],
                'description': 'Odoo Live for: %s' % channel.name,
            })

            discuss_channel.message_post(
                body=(
                    '<p>🎥 <b>Welcome to %s Live!</b></p>'
                    '<p>Real-time communication channel.</p>'
                ) % channel.name,
                message_type='comment',
            )

        return {
            'type': 'ir.actions.client',
            'tag': 'mail.action_discuss',
            'params': {'active_id': discuss_channel.id},
        }

    def action_view_channels(self):
        """View all channels (advanced)"""
        return {
            'type': 'ir.actions.act_window',
            'name': 'All Channels',
            'res_model': 'jira.communication.channel',
            'view_mode': 'kanban,list,form',
            'target': 'current',
        }