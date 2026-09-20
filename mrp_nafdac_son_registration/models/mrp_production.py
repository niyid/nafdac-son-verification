# -*- coding: utf-8 -*-
from odoo import models, fields, api


class MrpProduction(models.Model):
    _inherit = "mrp.production"

    nafdac_son_evidence_ids = fields.One2many(
        comodel_name="mrp.production.evidence",
        inverse_name="production_id",
        string="NAFDAC/SON Evidence Captures",
    )
    nafdac_son_evidence_count = fields.Integer(
        compute="_compute_nafdac_son_evidence_count",
    )

    @api.depends("nafdac_son_evidence_ids")
    def _compute_nafdac_son_evidence_count(self):
        for production in self:
            production.nafdac_son_evidence_count = len(production.nafdac_son_evidence_ids)

    def action_view_nafdac_son_evidence(self):
        self.ensure_one()
        return {
            "type": "ir.actions.act_window",
            "name": "NAFDAC/SON Evidence Captures",
            "res_model": "mrp.production.evidence",
            "view_mode": "list,form",
            "domain": [("production_id", "=", self.id)],
            "context": {"default_production_id": self.id},
        }

    def action_open_nafdac_son_capture_wizard(self):
        self.ensure_one()
        return {
            "type": "ir.actions.act_window",
            "name": "Capture NAFDAC/SON Evidence",
            "res_model": "mrp.production.evidence.capture.wizard",
            "view_mode": "form",
            "target": "new",
            "context": {"default_production_id": self.id},
        }
