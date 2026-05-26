# -*- coding: utf-8 -*-
from odoo import models, fields, api, _
from odoo.exceptions import UserError


class JiraCommunicationChannel(models.Model):
    _name = 'jira.communication.channel'
    _description = 'Communication Channel'
    _inherit = ['mail.thread', 'mail.activity.mixin']
    _order = 'create_date desc'
    _rec_name = 'name'

    # Identification
    name = fields.Char(string='Nom du canal', required=True, tracking=True)
    description = fields.Text(string='Description')

    channel_type = fields.Selection([
        ('project', 'Canal projet'),
        ('direct', 'Message direct'),
        ('broadcast', 'Annonce generale'),
    ], string='Type', default='project', required=True, tracking=True)

    # Relations
    project_id = fields.Many2one(
        'jira.project',
        string='Projet',
        ondelete='cascade',
        tracking=True,
    )
    creator_id = fields.Many2one(
        'res.users',
        string='Createur',
        default=lambda self: self.env.user,
        readonly=True,
    )
    member_ids = fields.Many2many(
        'res.users',
        'jira_channel_member_rel',
        'channel_id', 'user_id',
        string='Membres',
    )

    # Meetings
    meeting_ids = fields.One2many(
        'jira.meeting',
        'communication_channel_id',
        string='Reunions',
    )
    meeting_count = fields.Integer(
        compute='_compute_counts',
        string='Nombre de reunions',
    )

    # Messages
    message_announcement_ids = fields.One2many(
        'jira.channel.message',
        'channel_id',
        string='Annonces',
    )
    announcement_count = fields.Integer(
        compute='_compute_counts',
        string='Nombre d annonces',
    )

    # Statut
    state = fields.Selection([
        ('active', 'Actif'),
        ('archived', 'Archive'),
    ], string='Statut', default='active', tracking=True)

    color = fields.Integer(string='Color', default=1)

    @api.depends('meeting_ids', 'message_announcement_ids')
    def _compute_counts(self):
        for rec in self:
            rec.meeting_count = len(rec.meeting_ids)
            rec.announcement_count = len(rec.message_announcement_ids)

    @api.onchange('project_id')
    def _onchange_project_id(self):
        if self.project_id:
            users = self.project_id.team_ids
            if self.project_id.manager_id:
                users |= self.project_id.manager_id
            self.member_ids = users
            if not self.name:
                self.name = "Canal - %s" % self.project_id.name

    def action_view_meetings(self):
        self.ensure_one()
        return {
            'type': 'ir.actions.act_window',
            'name': 'Reunions',
            'res_model': 'jira.meeting',
            'view_mode': 'list,form,kanban',
            'domain': [('communication_channel_id', '=', self.id)],
            'context': {
                'default_communication_channel_id': self.id,
                'default_project_id': self.project_id.id,
                'default_participant_ids': [(6, 0, self.member_ids.ids)],
            },
        }

    def action_new_meeting(self):
        self.ensure_one()
        return {
            'type': 'ir.actions.act_window',
            'name': 'Programmer une reunion',
            'res_model': 'jira.meeting',
            'view_mode': 'form',
            'target': 'new',
            'context': {
                'default_communication_channel_id': self.id,
                'default_project_id': self.project_id.id,
                'default_participant_ids': [(6, 0, self.member_ids.ids)],
                'default_name': "Reunion - %s" % self.name,
            },
        }

    def action_new_announcement(self):
        self.ensure_one()
        return {
            'type': 'ir.actions.act_window',
            'name': 'Nouvelle annonce',
            'res_model': 'jira.channel.message',
            'view_mode': 'form',
            'target': 'new',
            'context': {
                'default_channel_id': self.id,
                'default_recipient_ids': [(6, 0, self.member_ids.ids)],
            },
        }

    def action_archive(self):
        self.write({'state': 'archived'})

    def action_unarchive(self):
        self.write({'state': 'active'})

    @api.model_create_multi
    def create(self, vals_list):
        if not self.env.user.has_group('jira_project.group_jira_manager') and \
           not self.env.user.has_group('base.group_system'):
            raise UserError(_("Action not allowed"))
        return super().create(vals_list)


class JiraChannelMessage(models.Model):
    _name = 'jira.channel.message'
    _description = 'Channel Announcement'
    _inherit = ['mail.thread']
    _order = 'date desc, id desc'
    _rec_name = 'subject'

    subject = fields.Char(string='Sujet', required=True, tracking=True)
    content = fields.Html(string='Contenu', required=True)

    channel_id = fields.Many2one(
        'jira.communication.channel',
        string='Canal',
        required=True,
        ondelete='cascade',
    )
    author_id = fields.Many2one(
        'res.users',
        string='Auteur',
        default=lambda self: self.env.user,
        readonly=True,
    )
    date = fields.Datetime(
        string='Date',
        default=fields.Datetime.now,
        readonly=True,
    )
    recipient_ids = fields.Many2many(
        'res.users',
        'channel_message_recipient_rel',
        'message_id', 'user_id',
        string='Destinataires',
    )
    read_by_ids = fields.Many2many(
        'res.users',
        'channel_message_read_rel',
        'message_id', 'user_id',
        string='Lu par',
    )

    priority = fields.Selection([
        ('0', 'Normale'),
        ('1', 'Importante'),
        ('2', 'Urgente'),
    ], string='Priorite', default='0')

    is_announcement = fields.Boolean(string='Annonce', default=True)
    attachment_ids = fields.Many2many('ir.attachment', string='Pieces jointes')

    def action_send(self):
        self.ensure_one()
        if not self.recipient_ids:
            raise UserError(_("Aucun destinataire."))

        partner_ids = self.recipient_ids.mapped('partner_id').ids

        priority_label = {
            '0': '',
            '1': '[IMPORTANT] ',
            '2': '[URGENT] ',
        }.get(self.priority, '')

        message_body = "<p><b>%s%s</b></p>%s" % (
            priority_label, self.subject, self.content or ''
        )

        if self.channel_id.project_id:
            self.channel_id.message_post(
                body=message_body,
                subject=self.subject,
                partner_ids=partner_ids,
                message_type='notification',
            )

        return {
            'type': 'ir.actions.client',
            'tag': 'display_notification',
            'params': {
                'title': _('Annonce envoyee'),
                'message': _('Message envoye a %s destinataires') % len(self.recipient_ids),
                'type': 'success',
                'sticky': False,
            }
        }

    def action_mark_as_read(self):
        for msg in self:
            if self.env.user not in msg.read_by_ids:
                msg.read_by_ids = [(4, self.env.user.id)]