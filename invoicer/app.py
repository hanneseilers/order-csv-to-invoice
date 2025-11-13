#!/usr/bin/env python3
# -*- coding: utf-8 -*-
import argparse, yaml
from pathlib import Path
from datetime import datetime
from dateutil import parser as dateparser
from weasyprint.css.validation.properties import order

from .csv_loader import CSVLoader
from .numbering import InvoiceNumbering
from .qr import QRService
from .renderer import HTMLRenderer
from .emailer import EmailSender
from .utils import ensure_float, ensure_int, money, money_to_float, image_file_to_data_uri
from .models import Customer

def main():
    ap = argparse.ArgumentParser(description="Invoicer (HTML → PDF) modular")
    ap.add_argument("--csv", required=True, help="CSV input file")
    ap.add_argument("--out", required=True, help="Output folder for PDFs")
    ap.add_argument("--config", default="config_example.yaml", help="Path to YAML config")
    ap.add_argument("--costs", help="CSV costs input file")
    ap.add_argument("--only", help="Process only this E-Mail address")
    ap.add_argument("--list", action="store_true", help="Create an order list only")
    ap.add_argument("--send", action="store_true", help="Send emails (config email.enabled must be true)")
    args = ap.parse_args()

    # Loading config
    cfg = yaml.safe_load(Path(args.config).read_text(encoding="utf-8"))

    # Initiate numbering system
    numbering = InvoiceNumbering(
        title = cfg["invoice"].get("title", ""),
        prefix=cfg["invoice"]["numbering"].get("prefix", "RE"),
        date_format=cfg["invoice"]["numbering"].get("date_format", "%m%Y"),
        start=int(cfg["invoice"]["numbering"].get("per_run_sequence_start", 1)),
    )

    # Initiate html page renderer
    renderer = HTMLRenderer(templates_dir=str(Path("templates")))

    # Initiate sending emails, if requested
    email_cfg = cfg.get("email", {})
    mailer = None
    if args.send and email_cfg.get("enabled", False):
        mailer = EmailSender(
            host=email_cfg["smtp_host"],
            port=email_cfg["smtp_port"],
            username=email_cfg.get("username", ""),
            password=email_cfg.get("password", ""),
            sender_email=email_cfg["sender_email"],
        )

    # Get company logo
    logo_data = image_file_to_data_uri(cfg["company"].get("logo_path","")) if cfg["company"].get("logo_path") else ""

    # Get custom configuration values
    net_prices = bool(cfg["invoice"].get("net_prices", True))
    vat_default = ensure_float(cfg["invoice"].get("default_vat_rate", 0.0))
    currency = cfg["invoice"].get("currency", "EUR")
    shipping = cfg["invoice"].get("shipping", 0.0)

    models_cfg = cfg.get("models", {})
    customer_cfg = models_cfg.get("customer", {})
    name_tag = customer_cfg.get("name_tag", "name")
    mail_tag = customer_cfg.get("mail_tag", "mail")
    time_tag = customer_cfg.get("time_tag", "time")

    order_cfg = models_cfg.get("order", {})
    order_exclude_columns = order_cfg.get("exclude_columns", [])
    order_exclude_data_columns = order_cfg.get("exclude_data_columns", [])
    order_date_format = order_cfg.get("date_format", "%d.%m.%Y %H:%M:%S")

    costs_cfg = models_cfg.get("costs", {})
    costs_item_name_tag = costs_cfg.get("name_pack_tag", "name")
    costs_item_replacement_tag = costs_cfg.get("replacement_tag", "replacement")
    costs_item_price_tag = costs_cfg.get("price_tag", "price")
    costs_item_qty_per_pack_tag = costs_cfg.get("qty_per_pack_tag", "quatitiy per pack")
    costs_item_tax_tag = costs_cfg.get("tax_tag", "tax rate")

    # Load orders list and generate output directory
    orders = CSVLoader(csv_path=args.csv, reference_tag=mail_tag, exclude_columns=order_exclude_columns).parse_orders()
    out_dir = Path(args.out)
    out_dir.mkdir(parents=True, exist_ok=True)

    # Process each order one-by-one
    mails = []
    order_list = []
    for email, data in orders.items():
        if (args.only and email != args.only) \
                or not isinstance(email, str) or not isinstance(data, dict):
            continue

        # Create customer out of order data
        customer = Customer(
            name=data.get(name_tag,""),
            order_time=data.get(time_tag,""),
            email=str(email)
        )

        # Generate date string
        date_str = data.get(time_tag) or datetime.now().strftime(order_date_format)
        try:
            date_obj = dateparser.parse(date_str).date()
        except Exception:
            date_obj = datetime.now().date()

        # Gather ordered items from oder data
        items_data = {
            k: v.strip() if isinstance(v, str) else v
            for k, v in data.items()
            if k not in order_exclude_data_columns and v not in (None, "", " ")
        }

        invoice_no = numbering.next_number()
        sepa_qr = ""
        pp_link = ""
        pp_qr = ""

        items = []
        net_sum = 0.0
        vat_sum = 0.0
        notes = ""

        # Calculate costs, if requested
        costs = {}
        if args.costs:
            costs = CSVLoader(csv_path=args.costs, reference_tag=costs_item_name_tag).parse_orders()

            for item_name, item_value in costs.items():

                if item_name and "UNKNOWN" not in item_name.upper() \
                    and isinstance(item_value, dict):

                    if costs_item_replacement_tag not in item_value:
                        item_value[costs_item_replacement_tag] = None

                    if costs_item_tax_tag not in item_value:
                        item_value[costs_item_tax_tag] = vat_default

        # process items_data to items list
        for name, qty in items_data.items():
            qty = ensure_int(qty)
            name = str(name)
            price = None
            subtotal = None
            replacement = None
            qty_per_pack = None
            tax_rate = None

            # Calculate customers item costs
            if name in costs:
                costs_item = costs[name]
                if isinstance(costs_item, dict):

                    qty_per_pack = ensure_int(costs_item[costs_item_qty_per_pack_tag])

                    price = costs_item[costs_item_price_tag]
                    if isinstance(price, str):
                        price = money_to_float(price)
                    subtotal = price * qty * qty_per_pack

                    if costs_item_replacement_tag in costs_item:
                        replacement = str(costs_item[costs_item_replacement_tag])

                    if costs_item_tax_tag in costs_item:
                        tax_rate = ensure_float(costs_item[costs_item_tax_tag])

            # Add calculated item to customers ordered items
            items.append({
                "name": name,
                "replacement": replacement,
                "quantity": qty,
                "quantity per pack": qty_per_pack,
                "price": price,
                "subtotal": subtotal,
                "vat": ensure_int(tax_rate * 100.0) if net_prices else None
            })

        # Calculate prices
        if not args.list:

            for n in range(len(items)):
                item = items[n]
                subtotal = ensure_float(item.get("subtotal"))
                net_sum += subtotal

                #calculate price incl. vat for all items
                tax = item.get("vat")
                if net_prices and tax > 0:
                    tax = ensure_float(tax / 100.0)
                    vat_sum += subtotal * tax

        # Normalize total costs
        net_sum = round(net_sum, 2)
        vat_sum = round(vat_sum, 2)
        grand = round(net_sum + shipping + vat_sum, 2)

        # Generate payment information
        if cfg["bank"].get("iban") and cfg["bank"].get("bic"):
            payload = QRService.epc_sepa_qr_payload(
                iban=cfg["bank"]["iban"],
                bic=cfg["bank"]["bic"],
                name=cfg["bank"].get("account_holder", cfg["company"]["name"]),
                amount=grand,
                remittance=f"{invoice_no}",
                currency=currency
            )
            sepa_qr = QRService.make_qr_data_uri(payload)

        if cfg.get("paypal", {}).get("link_template"):
            pp_link = cfg["paypal"]["link_template"].format(amount=f"{grand:.2f}")
            pp_qr = QRService.make_qr_data_uri(pp_link)

        # Create context for pdf generation
        context = {
            "company": {**cfg["company"], "logo_data": logo_data},
            "bank": cfg["bank"],
            "paypal": {"link": pp_link, "qr": pp_qr},
            "invoice": {
                "title": cfg["invoice"].get("title",""),
                "invoice_no": invoice_no,
                "date_str": date_obj.strftime(order_date_format),
                "location": cfg["invoice"].get("sender_location_for_date_line",""),
                "payment_terms": cfg["invoice"].get("payment_terms",""),
                "footer_note": cfg["invoice"].get("footer_note",""),
                "table_ust_id_name": cfg["invoice"].get("table_ust_id_name"),
                "table_pos": cfg["invoice"].get("table_pos"),
                "table_desc": cfg["invoice"].get("table_desc"),
                "table_qty": cfg["invoice"].get("table_qty"),
                "table_tax": cfg["invoice"].get("table_tax"),
                "table_single_price": cfg["invoice"].get("table_single_price"),
                "table_subtotal": cfg["invoice"].get("table_subtotal"),
                "table_sum": cfg["invoice"].get("table_sum"),
                "table_total": cfg["invoice"].get("table_total"),
                "table_shipping": cfg["invoice"].get("table_shipping"),
                "table_notes": cfg["invoice"].get("table_notes"),
                "table_payment_terms": cfg["invoice"].get("table_payment_terms"),
                "table_bank_account": cfg["invoice"].get("table_bank_account"),
                "table_ordered_at": cfg["invoice"].get("table_ordered_at"),
                "table_for": cfg["invoice"].get("table_for"),
                "table_replacement": cfg["invoice"].get("table_replacement")
            },
            "customer": customer.__dict__,
            "items": items,
            "shipping": shipping,
            "totals": {
                "net": net_sum,
                "vat": vat_sum,
                "grand": grand
            },
            "currency": currency,
            "notes": notes,
            "sepa_qr": sepa_qr,
        }

        # Add customer to total list
        order_list.append( {'name': customer.name, 'ordered_items': items} )

        # Generate PDF
        out_pdf = Path(args.out) / f"{invoice_no}_{customer.name}.pdf"
        if args.list:
            renderer.render_to_pdf(out_pdf, context, "order-list.html")
        else:
            renderer.render_to_pdf(out_pdf, context)

        print(f"Created {out_pdf.name} for order{"-list" if args.list else ""} from {email} amount {grand:.2f} {currency}")

        # Generate Mail
        if args.send and email_cfg.get("enabled", False) and mailer:
            subject = email_cfg["subject_template"].format(invoice_no=invoice_no)
            body = email_cfg["body_template"].format(
                customer_name=customer.name,
                invoice_no=invoice_no,
                amount=grand,
                currency=currency,
                payment_terms=cfg["invoice"].get("payment_terms",""),
                company_name=cfg["company"]["name"],
            )

            mails.append(
                mailer.create_mail(customer.email, subject, body, str(out_pdf))
            )

    # Render complete orders list
    context = {
        "company": {**cfg["company"], "logo_data": logo_data},
        "orders": order_list
    }
    out_pdf = Path(args.out) / f"orders-checklist.pdf"
    renderer.render_to_pdf(out_pdf, context, "orders-checklist.html")

    # Send mails
    if mailer:
        mailer.send(mails)
