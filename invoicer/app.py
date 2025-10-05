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
from .utils import ensure_float, ensure_int, money, image_file_to_data_uri
from .models import Customer

def main():
    ap = argparse.ArgumentParser(description="Invoicer (HTML → PDF) modular")
    ap.add_argument("--csv", required=True, help="CSV input path")
    ap.add_argument("--out", required=True, help="Output folder for PDFs")
    ap.add_argument("--config", default="config_example.yaml", help="Path to YAML config")
    ap.add_argument("--only", help="Process only this E-Mail address")
    ap.add_argument("--list", action="store_true", help="Create an order list only")
    ap.add_argument("--send", action="store_true", help="Send emails (config email.enabled must be true)")
    args = ap.parse_args()

    # loading config
    cfg = yaml.safe_load(Path(args.config).read_text(encoding="utf-8"))

    numbering = InvoiceNumbering(
        title = cfg["invoice"].get("title", ""),
        prefix=cfg["invoice"]["numbering"].get("prefix", "RE"),
        date_format=cfg["invoice"]["numbering"].get("date_format", "%d.%m.%Y"),
        start=int(cfg["invoice"]["numbering"].get("per_run_sequence_start", 1)),
    )

    renderer = HTMLRenderer(templates_dir=str(Path("templates")))
    email_cfg = cfg.get("email", {})
    mailer = None
    if args.send and email_cfg.get("enabled", False):
        mailer = EmailSender(
            host=email_cfg["smtp_host"],
            port=email_cfg["smtp_port"],
            username=email_cfg.get("username", ""),
            password=email_cfg.get("password", ""),
            use_tls=bool(email_cfg.get("use_tls", True)),
            sender_email=email_cfg["sender_email"],
        )

    logo_data = image_file_to_data_uri(cfg["company"].get("logo_path","")) if cfg["company"].get("logo_path") else ""

    net_prices = bool(cfg["invoice"].get("net_prices", True))
    vat_default = ensure_float(cfg["invoice"].get("default_vat_rate", 0.0))
    currency = cfg["invoice"].get("currency","EUR")

    models_cfg = cfg.get("models", {})
    customer_cfg = models_cfg.get("customer", {})
    name_tag = customer_cfg.get("name_tag", "name")
    mail_tag = customer_cfg.get("mail_tag", "mail")
    time_tag = customer_cfg.get("time_tag", "time")

    order_cfg = models_cfg.get("order", {})
    order_exclude_columns = order_cfg.get("exclude_columns", [])
    order_exclude_data_columns = order_cfg.get("exclude_data_columns", [])
    order_date_format = order_cfg.get("date_format", "%d.%m.%Y %H:%M:%S")

    orders = CSVLoader(csv_path=args.csv, reference_tag=mail_tag, exclude_columns=order_exclude_columns).parse_orders()
    out_dir = Path(args.out)
    out_dir.mkdir(parents=True, exist_ok=True)

    for email, data in orders.items():
        if (args.only and email != args.only) \
                or not isinstance(email, str) or not isinstance(data, dict):
            continue

        customer = Customer(
            name=data.get(name_tag,""),
            order_time=data.get(time_tag,"")
        )

        date_str = data.get(time_tag) or datetime.now().strftime(order_date_format)
        try:
            date_obj = dateparser.parse(date_str).date()
        except Exception:
            date_obj = datetime.now().date()

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
        shipping = 0.0
        notes = ""

        # process items_data to items list
        for name, qty in items_data.items():
            qty = ensure_int(qty)
            name = str(name)
            items.append({
                "name": name,
                "quantity": qty
            })

        if not args.list:

            # for r in data:
            #     qty = ensure_float(r.get("quantity"), 0.0)
            #     unit = ensure_float(r.get("unit_price"), 0.0)
            #     tax = ensure_float(r.get("tax_rate"), vat_default)
            #     name = r.get("item_name","" )
            #
            #     if net_prices:
            #         line_net = qty * unit
            #         line_vat = line_net * tax
            #     else:
            #         gross = qty * unit
            #         line_net = gross / (1 + tax) if (1 + tax) else gross
            #         line_vat = gross - line_net
            #
            #     items.append({
            #         "name": name,
            #         "quantity": f"{qty:g}",
            #         "unit_price": unit,
            #         "unit_price_fmt": money(unit),
            #         "tax_rate": tax,
            #         "tax_rate_pct": int(round(tax*100)),
            #         "line_net": line_net,
            #         "line_net_fmt": money(line_net),
            #     })
            #     net_sum += line_net
            #     vat_sum += line_vat
            #
            #     shipping = shipping or ensure_float(r.get("shipping"), 0.0)
            #     if r.get("notes"): notes = r.get("notes")
            #
            net_sum += shipping

        grand = net_sum + vat_sum

        if cfg["bank"].get("iban") and cfg["bank"].get("bic"):
            payload = QRService.epc_sepa_qr_payload(
                iban=cfg["bank"]["iban"],
                bic=cfg["bank"]["bic"],
                name=cfg["bank"].get("account_holder", cfg["company"]["name"]),
                amount=grand,
                remittance=f"Rechnung {invoice_no}",
                currency=currency
            )
            sepa_qr = QRService.make_qr_data_uri(payload)

        if cfg.get("paypal", {}).get("link_template"):
            pp_link = cfg["paypal"]["link_template"].format(amount=f"{grand:.2f}")
            pp_qr = QRService.make_qr_data_uri(pp_link)

        context = {
            "company": {**cfg["company"], "logo_data": logo_data},
            "bank": cfg["bank"],
            "paypal": {"link": pp_link, "qr": pp_qr},
            "invoice": {
                "invoice_no": invoice_no,
                "date_str": date_obj.strftime(order_date_format),
                "location": cfg["invoice"].get("sender_location_for_date_line",""),
                "payment_terms": cfg["invoice"].get("payment_terms",""),
                "footer_note": cfg["invoice"].get("footer_note",""),
            },
            "customer": customer.__dict__,
            "items": items,
            "shipping": shipping,
            "totals": {
                "net": net_sum, "net_fmt": money(net_sum),
                "vat": vat_sum, "vat_fmt": money(vat_sum),
                "gross": grand, "gross_fmt": money(grand),
            },
            "currency": currency,
            "notes": notes,
            "sepa_qr": sepa_qr,
        }

        out_pdf = Path(args.out) / f"{invoice_no}_{customer.name}.pdf"

        if args.list:
            renderer.render_to_pdf(out_pdf, context, "order-list.html")
        else:
            renderer.render_to_pdf(out_pdf, context)

        print(f"Created {out_pdf.name} for order{"-list" if args.list else ""} {email} amount {grand:.2f} {currency}")

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
            mailer.send(customer.email, subject, body, str(out_pdf))
            print(f"  → sent to {customer.email}")
