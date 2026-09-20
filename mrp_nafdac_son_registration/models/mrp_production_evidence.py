# -*- coding: utf-8 -*-
import json
import logging

from odoo import models, fields, api, _

_logger = logging.getLogger(__name__)

# Config parameter an admin can set (Settings > Technical > Parameters > System
# Parameters) to include extra product fields in every snapshot without a code
# change — e.g. fields added later by the nafdac_son_verification mixin.
# Example value: "nafdac_registration_number,son_registration_number,batch_expiry_date"
EXTRA_SNAPSHOT_FIELDS_PARAM = "mrp_nafdac_son_registration.extra_product_snapshot_fields"

# Always-included product fields — safe defaults present on every Odoo product.
BASE_SNAPSHOT_FIELDS = [
    "display_name",
    "default_code",
    "barcode",
    "categ_id",
    "list_price",
    "uom_id",
]


class MrpProductionEvidenceMedia(models.Model):
    """One row per photo or video attached to a capture. Kept as its own model
    (rather than raw ir.attachment on the evidence record) so each item can
    carry its own caption, sequence, and capture timestamp.
    """
    _name = "mrp.production.evidence.media"
    _description = "Manufacturing Evidence Media Item"
    _order = "sequence, id"

    evidence_id = fields.Many2one(
        comodel_name="mrp.production.evidence",
        required=True,
        ondelete="cascade",
    )
    sequence = fields.Integer(default=10)
    media_type = fields.Selection(
        selection=[("photo", "Photo"), ("video", "Video")],
        required=True,
        default="photo",
    )
    attachment_id = fields.Many2one(
        comodel_name="ir.attachment",
        required=True,
        ondelete="cascade",
    )
    caption = fields.Char()
    captured_at = fields.Datetime(default=fields.Datetime.now)


class MrpProductionEvidence(models.Model):
    """The manufacturing-stage counterpart to the checkout-time audit log in
    nafdac_son_verification. Captures identification + media + a full product
    record snapshot at the moment a batch/lot is produced, independent of
    whether any regulator submission channel exists yet.
    """
    _name = "mrp.production.evidence"
    _description = "Manufacturing NAFDAC/SON Evidence Capture"
    _order = "capture_datetime desc, id desc"
    _inherit = ["mail.thread"]

    name = fields.Char(
        default=lambda self: _("New"), copy=False, readonly=True,
    )
    production_id = fields.Many2one(
        comodel_name="mrp.production",
        string="Manufacturing Order",
        required=True,
        ondelete="cascade",
        index=True,
    )
    product_id = fields.Many2one(
        comodel_name="product.product",
        related="production_id.product_id",
        store=True,
    )
    lot_id = fields.Many2one(
        comodel_name="stock.lot",
        string="Lot/Serial",
        domain="[('product_id', '=', product_id)]",
    )
    lot_number = fields.Char(
        string="Batch/Lot Identifier",
        help="Free-text batch or lot code, in case it's assigned outside the "
             "stock.lot flow (e.g. a NAFDAC/SON-specific batch code).",
    )
    product_identification_code = fields.Char(
        help="The code this specific unit/batch will be identified by downstream "
             "— barcode, serial, or provisional registration reference.",
    )

    capture_datetime = fields.Datetime(default=fields.Datetime.now, required=True)
    operator_id = fields.Many2one(
        comodel_name="res.users",
        default=lambda self: self.env.user,
        required=True,
    )
    workcenter_id = fields.Many2one(comodel_name="mrp.workcenter", string="Station")
    notes = fields.Text()

    media_ids = fields.One2many(
        comodel_name="mrp.production.evidence.media",
        inverse_name="evidence_id",
        string="Photos & Video",
    )
    photo_count = fields.Integer(compute="_compute_media_counts")
    video_count = fields.Integer(compute="_compute_media_counts")

    product_snapshot_json = fields.Text(
        string="Product Record Snapshot",
        readonly=True,
        help="Full product-record data captured at the moment of this evidence "
             "record, stored as JSON so the audit trail is self-contained even "
             "if the product record itself later changes.",
    )

    state = fields.Selection(
        selection=[
            ("draft", "Draft"),
            ("captured", "Captured"),
            ("queued", "Queued for Submission"),
        ],
        default="draft",
        required=True,
        tracking=True,
    )

    submission_ids = fields.One2many(
        comodel_name="regulatory.submission.queue",
        inverse_name="evidence_id",
        string="Submissions",
    )
    submission_count = fields.Integer(compute="_compute_submission_count")

    @api.depends("media_ids", "media_ids.media_type")
    def _compute_media_counts(self):
        for rec in self:
            rec.photo_count = len(rec.media_ids.filtered(lambda m: m.media_type == "photo"))
            rec.video_count = len(rec.media_ids.filtered(lambda m: m.media_type == "video"))

    @api.depends("submission_ids")
    def _compute_submission_count(self):
        for rec in self:
            rec.submission_count = len(rec.submission_ids)

    @api.model_create_multi
    def create(self, vals_list):
        for vals in vals_list:
            if vals.get("name", _("New")) == _("New"):
                vals["name"] = self.env["ir.sequence"].next_by_code(
                    "mrp.production.evidence"
                ) or _("New")
        records = super().create(vals_list)
        for rec in records:
            rec._snapshot_product_record()
        return records

    def _snapshot_product_record(self):
        """Serialize a substantial slice of the product record into JSON and
        store it on the evidence record permanently. This is what makes each
        capture a self-contained piece of evidence — not just a photo, but the
        product data that photo corresponds to, at that moment in time.
        """
        self.ensure_one()
        if not self.product_id:
            return

        param_model = self.env["ir.config_parameter"].sudo()
        extra_fields_raw = param_model.get_param(EXTRA_SNAPSHOT_FIELDS_PARAM, "")
        extra_fields = [f.strip() for f in extra_fields_raw.split(",") if f.strip()]

        field_names = BASE_SNAPSHOT_FIELDS + extra_fields
        product = self.product_id
        snapshot = {"_snapshot_taken_at": fields.Datetime.now().isoformat()}

        for field_name in field_names:
            if field_name not in product._fields:
                snapshot[field_name] = None
                continue
            try:
                value = product[field_name]
            except Exception:  # noqa: BLE001 - defensive: never let a bad field name break capture
                _logger.warning(
                    "mrp_nafdac_son_registration: could not read field '%s' on "
                    "product %s while snapshotting.", field_name, product.id,
                )
                continue

            field_type = product._fields[field_name].type
            if field_type in ("many2one",):
                snapshot[field_name] = value.display_name if value else None
            elif field_type in ("many2many", "one2many"):
                snapshot[field_name] = value.mapped("display_name")
            else:
                # date/datetime/monetary/etc. all render safely through str()
                snapshot[field_name] = value if isinstance(
                    value, (str, int, float, bool, type(None))
                ) else str(value)

        self.product_snapshot_json = json.dumps(snapshot, ensure_ascii=False, indent=2)

    def action_mark_captured(self):
        for rec in self:
            if not rec.media_ids:
                # Not a hard requirement, but flag it — see README on making
                # media mandatory via a server action if your process needs that.
                rec.message_post(body=_(
                    "Marked captured with no photo/video attached."
                ))
            rec.state = "captured"
        self._queue_for_all_providers()

    def _queue_for_all_providers(self):
        """Create one queue entry per known provider (active or not) so that
        nothing captured today is ever missed once a provider goes active
        later — the queue entry already exists, just waiting.
        """
        queue_model = self.env["regulatory.submission.queue"]
        providers = self.env["regulatory.submission.provider"].search([])
        for rec in self:
            existing_provider_ids = rec.submission_ids.mapped("provider_id.id")
            to_create = providers.filtered(lambda p: p.id not in existing_provider_ids)
            for provider in to_create:
                queue_model.create({
                    "evidence_id": rec.id,
                    "provider_id": provider.id,
                    "state": "pending" if provider.state == "active" else "pending_no_provider",
                })
            if to_create and rec.state != "queued":
                rec.state = "queued"
