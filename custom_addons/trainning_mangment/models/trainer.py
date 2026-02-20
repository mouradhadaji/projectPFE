from odoo import models,fields,api
from odoo.exceptions import ValidationError
class trainer(models.Model):
    _name='training.trainer'
    _description='trainer'

    name=fields.Char(string='name',required=True)
    age=fields.Integer(string='Age')
    date_Naisse=fields.Date(string='date de naissance')
    active=fields.Boolean(default=True)

    @api.constrains('age')
    def _check_age(self):
        for record in self:
            if record.age < 18:
                raise ValidationError("L'âge du formateur doit être supérieur ou égal à 18 ans.")