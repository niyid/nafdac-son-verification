"""
Bulk end-to-end workflow: several vendors, ~25 regulated products across both
NAFDAC and SON (a deliberate mix of well-formed and malformed registration
numbers so verification produces both 'verified' and 'failed' outcomes, not
just a single happy path), multiple Purchase Orders each received into
inventory as separate lots, and a single bulk run of the verification wizard
across every lot at once.

Also sets the admin password so this database can be driven live via
Selenium afterwards.
"""
import random

random.seed(42)

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


def step(n, title):
    print()
    print("=" * 78)
    print(f"STEP {n}: {title}")
    print("=" * 78)


def run(env):
    company = env.company
    company.write({'nafdac_verify_mode': 'demo', 'son_verify_mode': 'demo'})

    # Make sure there's a known admin login for the Selenium capture pass.
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

    step(3, "Confirm multiple Purchase Orders")
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

        step(f"3.{i + 1}", f"Receive {po.name} ({vendor.name}, {len(batch)} lines) into inventory")
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

    step(4, "Run bulk NAFDAC/SON verification across every received lot at once")
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

    step(5, "Sample of results")
    for lot in lots.sorted('id')[:6]:
        print(f"  {lot.name:<28} {lot.product_id.name[:35]:<35} -> {lot.verification_status}")
    print("  ...")
    for lot in lots.sorted('id')[-4:]:
        print(f"  {lot.name:<28} {lot.product_id.name[:35]:<35} -> {lot.verification_status}")

    step(6, "Summary")
    print(f"  Vendors            : {len(vendors)}")
    print(f"  Regulated products : {len(products)}")
    print(f"  Purchase Orders    : {po_count}")
    print(f"  Inventory receipts : {len(pickings)}")
    print(f"  Lots received      : {len(lots)}")
    print(f"  Verified / Failed  : {len(verified)} / {len(failed)}")
    print(f"  Verification logs  : {sum(len(l.verification_log_ids) for l in lots)}")

    env.cr.commit()


run(env)
