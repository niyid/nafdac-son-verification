# -*- coding: utf-8 -*-
import json
import logging

from odoo import models, fields, api, _

_logger = logging.getLogger(__name__)


class RegulatorySubmissionQueue(models.Model):
    """One row per (evidence capture, provider) pair. Created the moment
    evidence is captured, regardless of whether the provider is active —
    so the backlog already exists and just needs draining once a real
    endpoint is switched on.
    """
    _name = "regulatory.submission.queue"
    _description = "Regulatory Submission Queue"
    _order = "create_date desc, id desc"
    _inherit = ["mail.thread"]

    evidence_id = fields.Many2one(
        comodel_name="mrp.production.evidence",
        required=True,
        ondelete="cascade",
        index=True,
    )
    provider_id = fields.Many2one(
        comodel_name="regulatory.submission.provider",
        required=True,
        ondelete="cascade",
        index=True,
    )
    state = fields.Selection(
        selection=[
            ("pending_no_provider", "Waiting — No Active Provider"),
            ("pending", "Pending"),
            ("sent", "Sent"),
            ("acknowledged", "Acknowledged by Regulator"),
            ("failed", "Failed"),
            ("skipped_missing_field", "Skipped — Required Field Missing"),
        ],
        default="pending_no_provider",
        required=True,
        tracking=True,
    )
    attempt_count = fields.Integer(default=0)
    last_attempt_at = fields.Datetime()
    next_attempt_at = fields.Datetime()
    payload_json = fields.Text(readonly=True, string="Last Built Payload")
    response_json = fields.Text(readonly=True, string="Last Response")
    error_message = fields.Text(readonly=True)

    def _build_payload(self):
        """Build the outgoing payload strictly from the provider's field
        mapping — never hardcoded here, so a payload-shape change from the
        regulator is a data edit to regulatory.field.mapping, not a code change.
        Returns (payload_dict, missing_required_fields).
        """
        self.ensure_one()
        evidence = self.evidence_id
        snapshot = {}
        if evidence.product_snapshot_json:
            try:
                snapshot = json.loads(evidence.product_snapshot_json)
            except (TypeError, ValueError):
                snapshot = {}

        payload = {}
        missing = []
        for mapping in self.provider_id.field_mapping_ids:
            if mapping.internal_source == "static_value":
                value = mapping.static_value
            elif mapping.internal_source == "product_snapshot_field":
                value = snapshot.get(mapping.internal_field_name)
            else:  # evidence_field
                value = None
                if mapping.internal_field_name in evidence._fields:
                    raw = evidence[mapping.internal_field_name]
                    value = raw.display_name if hasattr(raw, "display_name") else raw
                    if hasattr(value, "isoformat"):
                        value = value.isoformat()

            if (value in (None, "", [])) and mapping.required:
                missing.append(mapping.external_field_name)
            payload[mapping.external_field_name] = value

        return payload, missing

    def _send_to_provider(self, is_test=False):
        """The single integration point with the outside world.

        THIS IS A STUB. There is no known public NAFDAC or SON manufacturer
        submission API as of this writing (see the linked article's findings
        on their public verification tools). Wire the real HTTP call in here
        — requests.post(provider.endpoint_url, json=payload, headers=...) —
        once an endpoint and auth flow actually exist. Until then this method
        deliberately raises, so nothing silently pretends to have submitted.
        """
        self.ensure_one()
        provider = self.provider_id

        if provider.state != "active" and not is_test:
            return  # queue stays put; this is expected, not an error

        payload, missing = self._build_payload()
        self.payload_json = json.dumps(payload, ensure_ascii=False, indent=2)

        if missing:
            self.write({
                "state": "skipped_missing_field",
                "error_message": _(
                    "Required field(s) missing before submission: %s"
                ) % ", ".join(missing),
            })
            return

        if not provider.endpoint_url:
            self.write({
                "state": "failed",
                "error_message": _(
                    "Provider has no Submission Endpoint URL configured yet."
                ),
            })
            return

        # --- Real call goes here once an endpoint exists. Example shape: -----
        #
        # import requests
        # headers = {}
        # if provider.auth_type == "api_key":
        #     headers[provider.api_key_header] = provider.api_key
        # elif provider.auth_type == "oauth2_client_credentials":
        #     headers["Authorization"] = f"Bearer {provider._get_oauth_token()}"
        # response = requests.post(provider.endpoint_url, json=payload,
        #                           headers=headers, timeout=30)
        # response.raise_for_status()
        # self.response_json = json.dumps(response.json(), indent=2)
        # self.state = "sent"
        # -----------------------------------------------------------------

        _logger.info(
            "mrp_nafdac_son_registration: submission %s to provider '%s' "
            "skipped — no real endpoint wired in yet (stub). Payload was: %s",
            self.id, provider.name, self.payload_json,
        )
        self.write({
            "state": "failed",
            "attempt_count": self.attempt_count + 1,
            "last_attempt_at": fields.Datetime.now(),
            "error_message": _(
                "No live integration implemented yet for provider '%s'. "
                "This is expected until NAFDAC/SON publish a submission API — "
                "see _send_to_provider() in the code."
            ) % provider.name,
        })

    @api.model
    def _cron_drain_queue(self):
        """Scheduled action: only ever touches submissions whose provider is
        Active. Everything else sits untouched, exactly as designed.
        """
        active_providers = self.env["regulatory.submission.provider"].search(
            [("state", "=", "active")]
        )
        if not active_providers:
            return
        pending = self.search([
            ("provider_id", "in", active_providers.ids),
            ("state", "in", ("pending_no_provider", "pending")),
        ])
        # Re-flag anything that was waiting on a provider that has since gone active.
        pending.filtered(lambda s: s.state == "pending_no_provider").write(
            {"state": "pending"}
        )
        for submission in pending:
            submission._send_to_provider()
