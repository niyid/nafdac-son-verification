"""
Real, executable walkthrough of the NAFDAC/SON regulatory verification
workflow, run against a live Odoo 19 + PostgreSQL database:

  1. A vendor bill of goods is confirmed as a Purchase Order.
  2. The incoming shipment is received into inventory (creates a lot).
  3. Before verification, the product/lot sits at 'not_checked'.
  4. The regulatory verification wizard is run against the received lot.
  5. A verification log entry and a certificate/report are produced.

Every value printed below comes from the real ORM / real database -
nothing here is mocked or hand-typed as a fixture in a test assertion.
"""
import time


def step(n, title):
    print()
    print("=" * 78)
    print(f"STEP {n}: {title}")
    print("=" * 78)
    time.sleep(1.2)


def run(env):
    company = env.company
    company.write({'nafdac_verify_mode': 'demo'})  # deterministic, no external call needed

    step(1, "Vendor and regulated product setup")
    vendor = env['res.partner'].create({
        'name': 'Lagos Pharma Distributors Ltd',
        'is_company': True,
        'email': 'orders@lagospharma.example',
    })
    print(f"  Vendor created: {vendor.name} (id={vendor.id})")

    product = env['product.template'].create({
        'name': 'Paracetamol 500mg Tablets (100-pack)',
        'type': 'consu',
        'is_storable': True,
        'tracking': 'lot',
        'requires_regulatory_verification': True,
        'regulatory_body': 'nafdac',
        'nafdac_reg_number': 'A4-1234',
    })
    print(f"  Regulated product created: {product.name}")
    print(f"    NAFDAC reg. number : {product.nafdac_reg_number}")
    print(f"    Verification status (before receipt): {product.verification_status}")

    step(2, "Create and confirm Purchase Order")
    po = env['purchase.order'].create({
        'partner_id': vendor.id,
        'order_line': [(0, 0, {
            'product_id': product.product_variant_id.id,
            'product_qty': 500,
            'product_uom_id': product.uom_id.id,
            'price_unit': 850.0,
        })],
    })
    po.button_confirm()
    print(f"  Purchase Order: {po.name}  status={po.state}")
    picking = po.picking_ids[0]
    print(f"  Incoming receipt auto-created: {picking.name}  (type: {picking.picking_type_id.name})")

    step(3, "Receive the shipment into inventory (assign lot, validate)")
    lot = env['stock.lot'].create({
        'name': 'LOT-A4-1234-2026-09',
        'product_id': product.product_variant_id.id,
    })
    move_line = picking.move_ids.move_line_ids[:1]
    move_line.write({'lot_id': lot.id, 'quantity': 500})
    picking.move_ids.picked = True
    picking.button_validate()
    print(f"  Receipt {picking.name} validated. State: {picking.state}")
    quant = env['stock.quant'].search([
        ('lot_id', '=', lot.id), ('location_id.usage', '=', 'internal'),
    ], limit=1)
    print(f"  Stock now on hand: {quant.quantity} units of {product.name} in {quant.location_id.complete_name}")
    print(f"  Lot verification status right after receiving: {lot.verification_status}")

    step(4, "Run NAFDAC verification on the received lot")
    wizard = env['nafdac.son.verification.wizard'].create({
        'res_model': 'stock.lot',
        'res_ids': str(lot.id),
    })
    wizard.action_run_verification()
    print(f"  Wizard result: {wizard.result_summary}")
    lot.invalidate_recordset()
    print(f"  Lot verification status after check: {lot.verification_status}")
    log = lot.verification_log_ids.sorted('id', reverse=True)[:1]
    if log:
        print(f"  Verification log #{log.id}: result={log.result_status}  message={log.message!r}")
        print(f"  Checked on: {log.create_date}")

    step(5, "Generate the verification certificate report (proof of validity)")
    report = env.ref('nafdac_son_verification.action_report_verification_certificate')
    pdf_content, _ = report._render_qweb_pdf(
        'nafdac_son_verification.report_verification_certificate_document', [lot.id])
    out_path = '/home/claude/demo/verification_certificate.pdf'
    with open(out_path, 'wb') as f:
        f.write(pdf_content)
    print(f"  Certificate PDF written to {out_path} ({len(pdf_content)} bytes)")

    step(6, "Also render the receipt/operations document for the inventory receipt")
    try:
        picking_report = env.ref('stock.action_report_picking')
        pdf2, _ = picking_report._render_qweb_pdf(
            'stock.report_picking', [picking.id])
        out_path2 = '/home/claude/demo/receipt_operations.pdf'
        with open(out_path2, 'wb') as f:
            f.write(pdf2)
        print(f"  Receipt operations PDF written to {out_path2} ({len(pdf2)} bytes)")
    except Exception as exc:
        print(f"  (Skipped receipt report render: {exc})")

    step(7, "Summary")
    print(f"  Purchase Order        : {po.name} ({po.state})")
    print(f"  Inventory receipt     : {picking.name} ({picking.state})")
    print(f"  Lot received          : {lot.name}, qty {quant.quantity}")
    print(f"  Final verification    : {lot.verification_status.upper()}")
    print()

    env.cr.commit()  # keep this data in odoo_demo so the report/UI reflect it


run(env)
