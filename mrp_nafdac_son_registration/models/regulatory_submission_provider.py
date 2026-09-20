# -*- coding: utf-8 -*-
from odoo import models, fields, api, _
from odoo.exceptions import UserError


class RegulatorySubmissionProvider(models.Model):
    """A configurable target for auto-submitting manufacturing evidence to a
    regulator (NAFDAC, SON, or any future one). Mirrors the shape of Odoo's own
    payment.provider: ships disabled, becomes usable purely through configuration
    once the regulator publishes a real endpoint — no code changes needed.
    """
    _name = "regulatory.submission.provider"
    _description = "Regulatory Submission Provider (NAFDAC / SON / other)"
    _order = "sequence, id"

    name = fields.Char(required=True)
    sequence = fields.Integer(default=10)
    code = fields.Selection(
        selection=[
            ("nafdac", "NAFDAC"),
            ("son", "SON"),
            ("other", "Other"),
        ],
        required=True,
        default="other",
        help="Which regulator this provider record targets. Used only for grouping "
             "and default field-mapping suggestions — does not affect behavior.",
    )
    state = fields.Selection(
        selection=[
            ("disabled", "Disabled"),
            ("configured", "Configured (test mode)"),
            ("active", "Active"),
        ],
        required=True,
        default="disabled",
        tracking=True,
        help="Disabled: never contacted, submissions queue and wait.\n"
             "Configured: endpoint/credentials filled in, but submissions still "
             "queue — use 'Send Test Submission' to verify manually before going live.\n"
             "Active: the scheduled action will drain the queue automatically.",
    )

    endpoint_url = fields.Char(
        string="Submission Endpoint URL",
        help="The regulator's ingestion endpoint, once one exists. Leave blank while unknown.",
    )
    auth_type = fields.Selection(
        selection=[
            ("none", "None"),
            ("api_key", "API Key (header)"),
            ("oauth2_client_credentials", "OAuth2 – Client Credentials"),
        ],
        default="none",
        required=True,
    )
    api_key_header = fields.Char(
        string="API Key Header Name",
        default="X-API-Key",
        help="Only used when Auth Type = API Key.",
    )
    api_key = fields.Char(string="API Key", groups="base.group_system")
    oauth_token_url = fields.Char(string="OAuth Token URL")
    oauth_client_id = fields.Char(string="OAuth Client ID")
    oauth_client_secret = fields.Char(string="OAuth Client Secret", groups="base.group_system")

    field_mapping_ids = fields.One2many(
        comodel_name="regulatory.field.mapping",
        inverse_name="provider_id",
        string="Field Mapping",
        help="Maps this module's internal evidence/product fields to the field "
             "names the regulator's API actually expects. Edit this, not the code, "
             "when the real payload shape is published.",
    )

    submission_ids = fields.One2many(
        comodel_name="regulatory.submission.queue",
        inverse_name="provider_id",
        string="Submissions",
    )
    submission_count = fields.Integer(compute="_compute_submission_count")
    pending_submission_count = fields.Integer(compute="_compute_submission_count")

    active = fields.Boolean(default=True)
    notes = fields.Text(
        help="Free-text space to paste links to the regulator's API docs, contact "
             "person, onboarding status, etc. once that conversation starts."
    )

    @api.depends("submission_ids", "submission_ids.state")
    def _compute_submission_count(self):
        for provider in self:
            submissions = provider.submission_ids
            provider.submission_count = len(submissions)
            provider.pending_submission_count = len(
                submissions.filtered(lambda s: s.state in ("pending_no_provider", "pending"))
            )

    def action_view_submissions(self):
        self.ensure_one()
        return {
            "type": "ir.actions.act_window",
            "name": _("Submissions"),
            "res_model": "regulatory.submission.queue",
            "view_mode": "list,form",
            "domain": [("provider_id", "=", self.id)],
        }

    def action_send_test_submission(self):
        """Manual, explicit test call — never triggered by the cron. Lets you
        verify a newly-configured provider against one real submission before
        flipping it to Active and letting the queue drain automatically.
        """
        self.ensure_one()
        if self.state == "disabled":
            raise UserError(_(
                "This provider is Disabled. Set it to 'Configured' first, fill in "
                "the endpoint and credentials, then try the test again."
            ))
        if not self.endpoint_url:
            raise UserError(_("No Submission Endpoint URL is set yet."))

        queue_model = self.env["regulatory.submission.queue"]
        latest = queue_model.search(
            [("provider_id", "=", self.id)], order="create_date desc", limit=1
        )
        if not latest:
            raise UserError(_(
                "There is nothing queued for this provider yet. Capture at least "
                "one manufacturing evidence record first."
            ))
        latest._send_to_provider(is_test=True)
        return {
            "type": "ir.actions.client",
            "tag": "display_notification",
            "params": {
                "title": _("Test submission attempted"),
                "message": _("Check the submission record's status and response log."),
                "sticky": False,
            },
        }
