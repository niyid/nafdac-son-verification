# mrp_nafdac_son_registration

Manufacturing-side counterpart to `nafdac_son_verification` /
`website_sale_nafdac_son_verification`. Where those check a product's
registration status at checkout, this module captures evidence at the point
of production — closing the loop end-to-end, from manufacture through to
retail sale.

## What it does today

- Adds a **Capture NAFDAC/SON Evidence** button to Manufacturing Orders
  (`mrp.production`), opening a wizard to log:
  - Batch/lot identifier and product identification code
  - One or more photos and/or videos
  - Free-text notes
- On save, permanently snapshots the full product record (name, code,
  barcode, price, category, plus any extra fields you configure — see
  below) as JSON on the evidence record, so the evidence is self-contained
  even if the product record changes later.
- Queues that evidence for every configured **Regulatory Submission
  Provider** — shipped with NAFDAC and SON records, both **disabled**.
- A scheduled action (every 30 min) drains the queue for any provider
  whose state is **Active**. Disabled/Configured providers are never
  contacted automatically.

## What it deliberately does NOT do

There is no known public NAFDAC or SON API for manufacturers to submit
product/batch registration data automatically. The single integration
point — `RegulatorySubmissionQueue._send_to_provider()` in
`models/regulatory_submission_queue.py` — is a clearly marked stub. It
builds the payload from your field mapping and logs what *would* be sent,
then marks the submission `failed` with an explanatory message. Wire in
the real `requests.post(...)` call there once an endpoint exists.

## Turning it on when a real API shows up

No code changes needed for the common case:

1. Open **Manufacturing > NAFDAC/SON Registration > Submission Providers**.
2. Edit the NAFDAC or SON record: set the endpoint URL, auth type, and
   credentials.
3. On the **Field Mapping** tab, add one row per field the regulator's API
   expects, pointing it at either an evidence field (e.g. `lot_number`) or
   a key in the product snapshot (e.g. `barcode`).
4. Set **State** to `Configured`, use **Send Test Submission** against one
   real evidence record, check the Payload/Response tabs.
5. Once satisfied, set **State** to `Active`. The cron picks up the entire
   backlog automatically — including everything captured before the API
   existed.

Only if the regulator's actual auth flow is something other than a static
API key or OAuth2 client-credentials (e.g. mutual TLS, a signed-request
scheme) would `_send_to_provider()` need real code changes rather than
configuration.

## Known assumption to verify against your instance

This module does **not** assume field names from `nafdac_son_verification`
— I don't have that module's source in this session, so I built the
product snapshot against safe, universal `product.product` fields only
(`display_name`, `default_code`, `barcode`, `categ_id`, `list_price`,
`uom_id`).

To include your actual NAFDAC/SON registration fields in every snapshot
(and make them available to field mapping), set this system parameter
(**Settings > Technical > Parameters > System Parameters**):

- Key: `mrp_nafdac_son_registration.extra_product_snapshot_fields`
- Value: comma-separated technical field names, e.g.
  `nafdac_registration_number,son_registration_number,batch_expiry_date`
  — replace with whatever your mixin actually calls them.

## Untested against a live instance

This was written without access to a running Odoo 19 database, so please
run `-i mrp_nafdac_son_registration` in a dev/staging environment first —
in particular, verify the inherited view id
`mrp.mrp_production_form_view` and the security groups
`mrp.group_mrp_user` / `mrp.group_mrp_manager` still match your installed
version before deploying to production.
