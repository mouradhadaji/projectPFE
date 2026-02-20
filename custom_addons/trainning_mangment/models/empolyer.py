from odoo import models, fields,api

class emploiyerInherit(models.Model):
    _inherit = 'hr.employee'

    trainer_id=fields.Many2one('training.trainer')
