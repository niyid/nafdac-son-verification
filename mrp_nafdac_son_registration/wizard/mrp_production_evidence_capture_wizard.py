# -*- coding: utf-8 -*-
from odoo import models, fields, api, _
from odoo.exceptions import UserError


class MrpProductionEvidenceCaptureWizardLine(models.TransientModel):
    _name = "mrp.production.evidence.capture.wizard.line"
    _description = "Manufacturing Evidence Capture — Media Line"

    wizard_id = fields.Many2one(
        comodel_name="mrp.production.evidence.capture.wizard",
        ondelete="cascade",
    )
    media_type = fields.Selection(
        selection=[("photo", "Photo"), ("video", "Video")],
        required=True,
        default="photo",
    )
    media_file = fields.Binary(string="File", required=True)
    media_filename = fields.Char(string="Filename")
    caption = fields.Char()


class MrpProductionEvidenceCaptureWizard(models.TransientModel):
    _name = "mrp.production.evidence.capture.wizard"
    _description = "Capture NAFDAC/SON Manufacturing Evidence"

    production_id = fields.Many2one(
        comodel_name="mrp.production",
        required=True,
    )
    product_id = fields.Many2one(
        related="production_id.product_id",
        readonly=True,
    )
    lot_id = fields.Many2one(
        comodel_name="stock.lot",
        domain="[('product_id', '=', product_id)]",
    )
    lot_number = fields.Char(string="Batch/Lot Identifier")
    product_identification_code = fields.Char()
    notes = fields.Text()
    line_ids = fields.One2many(
        comodel_name="mrp.production.evidence.capture.wizard.line",
        inverse_name="wizard_id",
        string="Photos & Video",
    )

    def action_confirm(self):
        self.ensure_one()
        if not self.line_ids:
            raise UserError(_(
                "Attach at least one photo or video before confirming — this "
                "is meant to be visual evidence, not just a data record."
            ))

        evidence = self.env["mrp.production.evidence"].create({
            "production_id": self.production_id.id,
            "lot_id": self.lot_id.id or False,
            "lot_number": self.lot_number,
            "product_identification_code": self.product_identification_code,
            "notes": self.notes,
        })

        attachment_model = self.env["ir.attachment"]
        media_model = self.env["mrp.production.evidence.media"]
        for line in self.line_ids:
            attachment = attachment_model.create({
                "name": line.media_filename or (
                    "capture_photo" if line.media_type == "photo" else "capture_video"
                ),
                "datas": line.media_file,
                "res_model": "mrp.production.evidence",
                "res_id": evidence.id,
            })
            media_model.create({
                "evidence_id": evidence.id,
                "media_type": line.media_type,
                "attachment_id": attachment.id,
                "caption": line.caption,
            })

        evidence.action_mark_captured()

        return {
            "type": "ir.actions.act_window",
            "name": _("Manufacturing Evidence"),
            "res_model": "mrp.production.evidence",
            "view_mode": "form",
            "res_id": evidence.id,
        }
