{
    "name": "Manufacturing NAFDAC/SON Registration Capture",
    "version": "19.0.1.0.0",
    "category": "Manufacturing",
    "summary": "Capture manufacturing-stage product identification, photo/video evidence, "
                "and product-record data, ready to auto-submit to NAFDAC/SON once an "
                "official submission API exists.",
    "description": """
Manufacturing NAFDAC/SON Registration Capture
==============================================

Closes the loop with the nafdac_son_verification / website_sale_nafdac_son_verification
checkout-side modules by capturing evidence at the *manufacturing* end instead of only
at the point of sale.

What this module does today (works with zero external dependencies):

* Adds an evidence-capture step to Manufacturing Orders (mrp.production): photos,
  video, batch/lot identifiers, operator, station, and a full snapshot of the
  product record at the moment of capture.
* Stores every capture permanently, regardless of whether any regulator submission
  channel exists yet.
* Provides a configurable "Regulatory Submission Provider" record (same pattern as
  Odoo's own Payment Providers) for NAFDAC and SON, shipped in a disabled state.
* Provides a submission queue: every capture is queued the moment it happens, sitting
  as "no provider configured" until a provider is switched to Active.
* A scheduled action drains the queue automatically once a provider is configured and
  active — no re-work needed on historical captures when that day comes.

What this module deliberately does NOT do yet:

* It does not call any live NAFDAC or SON API, because no public manufacturer-facing
  submission API is known to exist as of this writing. The HTTP call is a single,
  clearly marked stub method (`_send_to_provider`) — wire in the real endpoint and
  payload shape there once one exists.
""",
    "author": "Techducat",
    "website": "https://niyid.github.io",
    "license": "LGPL-3",
    "depends": ["mrp", "product", "mail"],
    "data": [
        "security/ir.model.access.csv",
        "data/regulatory_submission_provider_data.xml",
        "data/ir_cron_data.xml",
        "views/regulatory_submission_provider_views.xml",
        "views/regulatory_field_mapping_views.xml",
        "views/regulatory_submission_queue_views.xml",
        "views/mrp_production_evidence_views.xml",
        "views/mrp_production_views.xml",
        "wizard/mrp_production_evidence_capture_wizard_views.xml",
        "views/menus.xml",
    ],
    "installable": True,
    "application": False,
}
