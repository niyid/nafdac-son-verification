# -*- coding: utf-8 -*-
from odoo import models, fields


class RegulatoryFieldMapping(models.Model):
    """One row = one field the regulator's API expects, and where to pull the
    value from on our side. This is the piece meant to be edited by an admin
    (or by you, as configuration, not code) once a real payload spec exists —
    the goal is that onboarding a new/changed API is a data-entry task.
    """
    _name = "regulatory.field.mapping"
    _description = "Regulatory Submission Field Mapping"
    _order = "sequence, id"

    provider_id = fields.Many2one(
        comodel_name="regulatory.submission.provider",
        required=True,
        ondelete="cascade",
    )
    sequence = fields.Integer(default=10)

    internal_source = fields.Selection(
        selection=[
            ("evidence_field", "Evidence Capture Field"),
            ("product_snapshot_field", "Product Record Snapshot Field"),
            ("static_value", "Static Value"),
        ],
        required=True,
        default="evidence_field",
        help="Evidence Capture Field: a field on mrp.production.evidence "
             "(e.g. lot_number, capture_datetime).\n"
             "Product Record Snapshot Field: a key inside the JSON product-record "
             "snapshot taken at capture time (e.g. default_code, barcode, "
             "any extra field you listed in Settings).\n"
             "Static Value: a constant this provider always expects, "
             "e.g. a fixed 'source_system' identifier.",
    )
    internal_field_name = fields.Char(
        string="Internal Field / Key",
        help="Technical field name (for Evidence Capture Field) or JSON key "
             "(for Product Record Snapshot Field). Leave blank for Static Value.",
    )
    static_value = fields.Char(
        help="Only used when Internal Source = Static Value.",
    )
    external_field_name = fields.Char(
        string="Regulator's Field Name",
        required=True,
        help="Exactly what the regulator's API documentation calls this field "
             "in the submitted payload.",
    )
    required = fields.Boolean(
        default=True,
        help="If checked and the internal value is empty, the submission is "
             "held with an error instead of being sent with a blank field.",
    )
