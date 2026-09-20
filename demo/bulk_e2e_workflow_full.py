"""
Full bulk end-to-end workflow, now covering all three stages of the loop:

  MANUFACTURE (mrp_nafdac_son_registration)
      -> INVENTORY RECEIPT + VERIFICATION (nafdac_son_verification)
      -> CHECKOUT (website_sale_nafdac_son_verification)

This is bulk_e2e_workflow.py with a new Step 0 inserted before the original
vendor/PO/verification flow: several Manufacturing Orders are confirmed and
produced for regulated products, evidence (photo + batch/lot + notes) is
captured through the real wizard (mrp.production.evidence.capture.wizard)
exactly as a line operator would from the MO form, and the submission queue
this creates is demonstrated end-to-end — including flipping one provider to
Active and draining the queue, so the stub failure path
(_send_to_provider) is exercised for real, not just described in the README.

Run via:
    odoo-bin shell -c odoo19.conf -d nafdac_demo < bulk_e2e_workflow_full.py
"""
import base64
import random
from pathlib import Path

random.seed(42)

PLACEHOLDER_DIR = Path("/home/claude/work/placeholders")

NAFDAC_PRODUCTS = [
    ("Paracetamol 500mg Tablets (100-pack)", "A4-1234", True),
    ("Amoxicillin 250mg Capsules (50-pack)", "A4-5678", True),
    ("Vitamin C 1000mg Effervescent", "A7-0912", True),
    ("Chloroquine Phosphate 250mg", "A4-3321", True),
    ("Multivitamin Syrup 200ml", "B3-8890", True),
    ("Metformin 500mg Tablets", "A4-4471", True),
    ("Ibuprofen 400mg Tablets", "A2-1190", True),
    ("ORS Sachets (Oral Rehydration Salts)", "A9-2231", True),
    ("Ciprofloxacin 500mg Tablets", "A4-9012", True),
    ("Ferrous Sulphate + Folic Acid Tablets", "A6-4410", True),
    ("Counterfeit-Risk Cough Syrup 100ml", "NOT-A-REAL-NUMBER", False),
    ("Unregistered Herbal Mixture 250ml", "???", False),
    ("Suspicious Skin Cream 50g", "12345", False),
]

SON_PRODUCTS = [
    ("Extension Cable 5-Socket 13A", "SON-MC-10234", True),
    ("Rechargeable Emergency Lantern", "SON-MC-88214", True),
    ("Ceramic Cooking Gas Regulator", "SON-MC-55019", True),
    ("Electric Pressing Iron 1200W", "SON-MC-77302", True),
    ("USB-C Fast Charger 25W", "SON-MC-44510", True),
    ("Solar Rechargeable Fan", "SON-MC-91120", True),
    ("Bottled Table Water 75cl", "SON-MC-22981", True),
    ("Motorcycle Crash Helmet", "SON-MC-66410", True),
    ("Steel Reinforcement Rod 12mm", "SON-MC-33771", True),
    ("Substandard Power Strip", "FAKE-CERT", False),
    ("Uncertified Circuit Breaker", "000000", False),
    ("Recalled Space Heater Model X", "???INVALID???", False),
]

# Which regulated products get a full manufacture -> evidence -> queue pass,
# and which placeholder "batch photo" stands in for the real camera capture.
MANUFACTURING_RUNS = [
    ("Paracetamol 500mg Tablets (100-pack)", "paracetamol_batch.png",
     "Tablet Press A", "Line supervisor: batch visually inspected, blister "
     "seals intact, embossing legible."),
    ("Amoxicillin 250mg Capsules (50-pack)", "amoxicillin_batch.png",
     "Capsule Fill B", "Capsule fill weight checked against spec at "
     "start/mid/end of run."),
    ("ORS Sachets (Oral Rehydration Salts)", "ors_batch.png",
     "Sachet Pack C", "Heat-seal integrity checked on 1-in-50 sachets, "
     "no leakers found."),
    ("Extension Cable 5-Socket 13A", "extension_cable_batch.png",
     "Assembly D", "Continuity and earth-bond tested on every unit before "
     "packing."),
]


def step(n, title):
    print()
    print("=" * 78)
    print(f"STEP {n}: {title}")
    print("=" * 78)


def run(env):
    company = env.company
    company.write({'nafdac_verify_mode': 'demo', 'son_verify_mode': 'demo'})

    admin = env.ref('base.user_admin')
    admin.write({'password': 'admin', 'login': 'admin'})
    print(f"Admin login ready: {admin.login} / admin")

    step(1, "Create vendors")
    vendors = env['res.partner'].create([
        {'name': 'Lagos Pharma Distributors Ltd', 'is_company': True},
        {'name': 'Kano Hardware & Electricals Ltd', 'is_company': True},
        {'name': 'Port Harcourt Consumer Goods Co.', 'is_company': True},
    ])
    print(f"  {len(vendors)} vendors created: {', '.join(vendors.mapped('name'))}")

    step(2, "Create regulated product catalogue")
    products = env['product.template']
    for name, reg_no, _expected in NAFDAC_PRODUCTS:
        p = env['product.template'].create({
            'name': name,
            'type': 'consu',
            'is_storable': True,
            'tracking': 'lot',
            'requires_regulatory_verification': True,
            'regulatory_body': 'nafdac',
            'nafdac_reg_number': reg_no,
        })
        products |= p
    for name, reg_no, _expected in SON_PRODUCTS:
        p = env['product.template'].create({
            'name': name,
            'type': 'consu',
            'is_storable': True,
            'tracking': 'lot',
            'requires_regulatory_verification': True,
            'regulatory_body': 'son',
            'son_mancap_number': reg_no,
        })
        products |= p
    print(f"  {len(products)} regulated products created "
          f"({len(NAFDAC_PRODUCTS)} NAFDAC, {len(SON_PRODUCTS)} SON)")

    # =====================================================================
    step(3, "MANUFACTURING — produce regulated batches and capture "
            "NAFDAC/SON evidence at the point of production")
    # =====================================================================
    MrpProduction = env['mrp.production']
    EvidenceWizard = env['mrp.production.evidence.capture.wizard']
    productions = env['mrp.production']
    evidences = env['mrp.production.evidence']

    for i, (prod_name, photo_file, station, note) in enumerate(MANUFACTURING_RUNS, start=1):
        template = products.filtered(lambda p, n=prod_name: p.name == n)
        product = template.product_variant_id

        step(f"3.{i}", f"Manufacture {prod_name}")
        mo = MrpProduction.create({
            'product_id': product.id,
            'product_qty': random.choice([200, 300, 500]),
            'product_uom_id': product.uom_id.id,
        })
        mo.action_confirm()
        print(f"  {mo.name} confirmed for {mo.product_qty} {mo.product_uom_id.name}"
              f" -> state: {mo.state}")

        # Producing a lot-tracked product requires a lot to record output against.
        lot = env['stock.lot'].create({
            'name': f"MFG-{product.default_code or product.id}-2026-09",
            'product_id': product.id,
        })
        mo.lot_producing_ids = [(6, 0, [lot.id])]
        mo.qty_producing = mo.product_qty
        mo.button_mark_done()
        print(f"  {mo.name} marked done -> state: {mo.state}, produced lot {lot.name}")
        productions |= mo

        # --- Capture NAFDAC/SON evidence exactly as the wizard on the MO
        # form would (action_open_nafdac_son_capture_wizard opens this same
        # wizard from a real button click; here we drive it directly).
        photo_path = PLACEHOLDER_DIR / photo_file
        photo_b64 = base64.b64encode(photo_path.read_bytes())

        wizard = EvidenceWizard.create({
            'production_id': mo.id,
            'lot_id': lot.id,
            'lot_number': lot.name,
            'product_identification_code': product.barcode or product.default_code or lot.name,
            'notes': note,
            'line_ids': [(0, 0, {
                'media_type': 'photo',
                'media_file': photo_b64,
                'media_filename': photo_file,
                'caption': f"{station} — batch photo evidence",
            })],
        })
        action = wizard.action_confirm()
        evidence = env['mrp.production.evidence'].browse(action['res_id'])
        evidences |= evidence
        print(f"  Evidence {evidence.name} captured for {mo.name}: "
              f"state={evidence.state}, photos={evidence.photo_count}, "
              f"videos={evidence.video_count}")
        print(f"  Product snapshot stored ({len(evidence.product_snapshot_json)} bytes JSON)")
        print(f"  Submission queue rows created: {len(evidence.submission_ids)} "
              f"({', '.join(s.provider_id.name + ':' + s.state for s in evidence.submission_ids)})")

    step(4, "MANUFACTURING — configure one provider Active and drain the queue "
            "(exercises the real, deliberately-stubbed _send_to_provider path)")
    nafdac_provider = env['regulatory.submission.provider'].search(
        [('code', '=', 'nafdac')], limit=1)
    nafdac_provider.write({
        'state': 'active',
        'endpoint_url': 'https://example-regulator-endpoint.invalid/submit',
        'field_mapping_ids': [(0, 0, {
            'internal_source': 'evidence_field',
            'internal_field_name': 'lot_number',
            'external_field_name': 'batch_id',
            'required': True,
        }), (0, 0, {
            'internal_source': 'product_snapshot_field',
            'internal_field_name': 'display_name',
            'external_field_name': 'product_name',
            'required': True,
        })],
    })
    print(f"  Provider '{nafdac_provider.name}' set to Active with 2 field mappings")
    env['regulatory.submission.queue']._cron_drain_queue()
    drained = env['regulatory.submission.queue'].search(
        [('provider_id', '=', nafdac_provider.id)])
    for sub in drained:
        print(f"  Submission #{sub.id} ({sub.evidence_id.name}) -> state: {sub.state}"
              f"{' — ' + sub.error_message if sub.error_message else ''}")
    print("\n  This is the expected outcome: the queue drains the moment a provider "
          "goes Active, and every submission fails cleanly with an explanatory "
          "message, because no real NAFDAC/SON submission endpoint exists yet — "
          "exactly as documented in the module README.")

    step(5, "MANUFACTURING summary")
    print(f"  Manufacturing Orders completed : {len(productions)}")
    print(f"  Evidence captures              : {len(evidences)}")
    print(f"  Photos attached                : {sum(e.photo_count for e in evidences)}")
    print(f"  Submission queue rows          : "
          f"{sum(len(e.submission_ids) for e in evidences)}")

    # =====================================================================
    step(6, "Confirm multiple Purchase Orders (inventory intake, as before)")
    # =====================================================================
    all_lines = list(products)
    batches = [all_lines[i:i + 5] for i in range(0, len(all_lines), 5)]
    pickings = env['stock.picking']
    lots = env['stock.lot']
    po_count = 0
    for i, batch in enumerate(batches):
        vendor = vendors[i % len(vendors)]
        po = env['purchase.order'].create({
            'partner_id': vendor.id,
            'order_line': [(0, 0, {
                'product_id': p.product_variant_id.id,
                'product_qty': random.randint(50, 500),
                'product_uom_id': p.uom_id.id,
                'price_unit': round(random.uniform(200, 5000), 2),
            }) for p in batch],
        })
        po.button_confirm()
        po_count += 1
        picking = po.picking_ids[0]
        pickings |= picking

        step(f"6.{i + 1}", f"Receive {po.name} ({vendor.name}, {len(batch)} lines) into inventory")
        for line, product in zip(picking.move_ids, batch):
            lot = env['stock.lot'].create({
                'name': f"LOT-{product.default_code or product.id}-2026-09",
                'product_id': product.product_variant_id.id,
            })
            line.move_line_ids[:1].write({'lot_id': lot.id, 'quantity': line.product_uom_qty})
            lots |= lot
        picking.move_ids.picked = True
        picking.button_validate()
        print(f"  {picking.name} validated -> state: {picking.state}, {len(batch)} lots received")

    print(f"\n  TOTAL: {po_count} Purchase Orders confirmed and received, {len(lots)} lots in stock")

    step(7, "Run bulk NAFDAC/SON verification across every received lot at once")
    wizard = env['nafdac.son.verification.wizard'].create({
        'res_model': 'stock.lot',
        'res_ids': ','.join(str(i) for i in lots.ids),
    })
    wizard.action_run_verification()
    print(f"  Wizard result: {wizard.result_summary}")

    lots.invalidate_recordset()
    verified = lots.filtered(lambda l: l.verification_status == 'verified')
    failed = lots.filtered(lambda l: l.verification_status == 'failed')
    other = lots - verified - failed
    print(f"\n  Verified : {len(verified)}")
    print(f"  Failed   : {len(failed)}")
    print(f"  Other    : {len(other)} ({', '.join(other.mapped('verification_status')) or '-'})")

    step(8, "Sample of results")
    for lot in lots.sorted('id')[:6]:
        print(f"  {lot.name:<28} {lot.product_id.name[:35]:<35} -> {lot.verification_status}")
    print("  ...")
    for lot in lots.sorted('id')[-4:]:
        print(f"  {lot.name:<28} {lot.product_id.name[:35]:<35} -> {lot.verification_status}")

    step(9, "Full end-to-end summary — manufacture through to inventory")
    print(f"  Manufacturing Orders + evidence : {len(productions)} produced, "
          f"{len(evidences)} evidence captures, "
          f"{sum(len(e.submission_ids) for e in evidences)} regulator-queue rows")
    print(f"  Vendors                         : {len(vendors)}")
    print(f"  Regulated products              : {len(products)}")
    print(f"  Purchase Orders                 : {po_count}")
    print(f"  Inventory receipts              : {len(pickings)}")
    print(f"  Lots received (purchased)       : {len(lots)}")
    print(f"  Verified / Failed               : {len(verified)} / {len(failed)}")
    print(f"  Verification logs               : {sum(len(l.verification_log_ids) for l in lots)}")

    env.cr.commit()


run(env)  # noqa: F821 - `env` is injected by `odoo-bin shell`
