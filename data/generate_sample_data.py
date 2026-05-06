"""Author-time data generator. Run once locally:

    cd data && python generate_sample_data.py [--source PATH_TO_LANGCHAIN_AGENT_PYTHON_REPO]

Outputs:
    customers.json, orders.json, products.json,
    warranty_terms.json, kb_articles.json, kb_embeddings.npy

Embeddings are computed via AZURE_OPENAI_EMBEDDING_DEPLOYMENT (set
AZURE_OPENAI_ENDPOINT first). On systems without AOAI access the script
will skip kb_embeddings.npy and the runtime data_loader will compute it
on first startup instead.
"""

from __future__ import annotations

import argparse
import json
import os
import random
import sys
from pathlib import Path

OUT = Path(__file__).resolve().parent

# Synthesized Zava help-center articles. Small, representative.
KB_ARTICLES = [
    {
        "article_id": "kb-001",
        "title": "Returns and refunds policy",
        "category": "returns",
        "content": (
            "Most Zava products can be returned within 30 days of purchase for a full refund, "
            "provided they are unused and in original packaging. Power tools must include all "
            "accessories, manuals, and the battery (if applicable). To start a return, ask the "
            "support agent or call your local store. Refunds are issued to the original payment "
            "method within 5-7 business days of receipt at the warehouse."
        ),
    },
    {
        "article_id": "kb-002",
        "title": "Shipping times and tracking",
        "category": "shipping",
        "content": (
            "Standard shipping takes 3-5 business days within the contiguous US. Expedited "
            "shipping (2 day) is available at checkout for an additional fee. You can track your "
            "order from your account page or by calling customer service with your order id. "
            "Once a package is handed to the carrier, the tracking link will activate within 24 hours."
        ),
    },
    {
        "article_id": "kb-003",
        "title": "Drill not turning on — troubleshooting",
        "category": "troubleshooting",
        "content": (
            "If your cordless drill does not turn on, check the following in order: 1) Battery is "
            "fully charged and seated correctly. 2) Trigger lock-off button (above the trigger) is "
            "in the unlocked position. 3) Battery contacts are clean (wipe with a dry cloth). 4) The "
            "switch is set forward (not in the center safety position). If none of these resolve the "
            "issue, the tool may be defective and is covered under our 2 year power-tool warranty."
        ),
    },
    {
        "article_id": "kb-004",
        "title": "How to file a warranty claim",
        "category": "warranty",
        "content": (
            "To file a warranty claim, you'll need your order number and a brief description of "
            "the defect. Hand tools have a lifetime warranty against manufacturing defects; power "
            "tools have a 2 year limited warranty; consumables (blades, drill bits) are not "
            "covered. The support agent can start a warranty claim and ship a replacement directly."
        ),
    },
    {
        "article_id": "kb-005",
        "title": "Saw blade replacement",
        "category": "troubleshooting",
        "content": (
            "Always unplug the saw or remove the battery before changing a blade. Use the blade "
            "wrench supplied with the saw. Loosen the arbor bolt counter-clockwise (left-hand "
            "thread on most circular saws — check the arrow on the blade guard). Clean the arbor, "
            "fit the new blade with teeth pointing forward, and tighten firmly."
        ),
    },
    {
        "article_id": "kb-006",
        "title": "Battery care and storage",
        "category": "troubleshooting",
        "content": (
            "Lithium-ion batteries last longest when stored at 30-50% charge in a cool, dry place. "
            "Avoid full discharge. Charge before storing for more than 30 days. Never leave a battery "
            "on the charger long-term. Replace if it no longer holds a charge — most Zava batteries "
            "are warranted for 2 years from purchase."
        ),
    },
    {
        "article_id": "kb-007",
        "title": "Hammer head loose on handle",
        "category": "troubleshooting",
        "content": (
            "If the head of a wood-handled hammer becomes loose, it may need a replacement wedge. "
            "Drive a new metal wedge into the existing slot. For fiberglass-handled hammers a loose "
            "head means the epoxy bond has failed and the hammer should be returned under the "
            "lifetime warranty rather than repaired."
        ),
    },
    {
        "article_id": "kb-008",
        "title": "Wrong item received",
        "category": "returns",
        "content": (
            "If you received a different product than what you ordered, contact support within 30 "
            "days. We'll send a replacement and a prepaid return label for the wrong item — you do "
            "not pay for either. Have your order id ready when you reach out."
        ),
    },
    {
        "article_id": "kb-009",
        "title": "Damaged in shipping",
        "category": "returns",
        "content": (
            "Items that arrive damaged should be reported within 7 days. Take a photo of the box "
            "and the damaged product, and message support. We will ship a replacement immediately "
            "and arrange pickup of the damaged item — no return label needed at your end."
        ),
    },
    {
        "article_id": "kb-010",
        "title": "Saw safety basics",
        "category": "safety",
        "content": (
            "Always wear safety glasses and hearing protection when operating saws. Keep blade "
            "guards in place. Never make freehand cuts — use a fence or guide. Let the blade reach "
            "full speed before contact. Keep both hands on the saw and out of the line of cut. "
            "Disconnect power before any adjustments."
        ),
    },
    {
        "article_id": "kb-011",
        "title": "Order status meanings",
        "category": "shipping",
        "content": (
            "Order statuses: PLACED — we have received your order; PROCESSING — we are picking and "
            "packing; SHIPPED — handed to the carrier (tracking link active within 24h); DELIVERED "
            "— marked delivered by the carrier; CANCELED — order canceled before shipment; "
            "RETURNED — items returned to the warehouse."
        ),
    },
    {
        "article_id": "kb-012",
        "title": "Pricing and price match",
        "category": "billing",
        "content": (
            "Zava matches advertised prices from major competitors on identical SKUs. Send a "
            "screenshot of the competing price along with your order id within 14 days of purchase "
            "and we'll refund the difference. Clearance and bundled items are excluded."
        ),
    },
]

WARRANTY_TERMS = [
    {
        "category": "HAND TOOLS",
        "warranty_months": 999,
        "covered_defects": ["manufacturing defects", "head separation", "handle splitting"],
        "exclusions": ["normal wear", "abuse", "modification"],
    },
    {
        "category": "POWER TOOLS",
        "warranty_months": 24,
        "covered_defects": ["motor failure", "switch failure", "gearbox failure"],
        "exclusions": ["consumables (blades, bits)", "battery (separate 24-month warranty)", "drop damage"],
    },
    {
        "category": "POWER TOOL ACCESSORIES",
        "warranty_months": 12,
        "covered_defects": ["manufacturing defects"],
        "exclusions": ["normal wear", "consumables"],
    },
    {
        "category": "FASTENERS",
        "warranty_months": 12,
        "covered_defects": ["manufacturing defects"],
        "exclusions": ["normal wear"],
    },
]


def trim_customers(src: list[dict], n: int = 50) -> list[dict]:
    return [
        {k: c[k] for k in ("customer_id", "customer_name", "email", "phone", "created_at") if k in c}
        for c in src[:n]
    ]


def trim_orders(src: list[dict], customer_ids: set[int], n: int = 200) -> list[dict]:
    out = []
    for i, o in enumerate(src):
        if o.get("customer_id") not in customer_ids:
            continue
        out.append({
            "order_id": o.get("order_id", i + 1),
            "customer_id": o["customer_id"],
            "store_id": o.get("store_id"),
            "order_date": o.get("order_date"),
            "total_amount": o.get("total_amount"),
            "status": random.choice(["PLACED", "PROCESSING", "SHIPPED", "DELIVERED", "DELIVERED", "DELIVERED"]),
            "items": [
                {k: it[k] for k in ("product_id", "quantity", "unit_price", "discount_percent") if k in it}
                for it in o.get("items", [])
            ],
        })
        if len(out) >= n:
            break
    return out


def trim_products(src: list[dict], n: int = 30) -> list[dict]:
    """Keep ~30 products, drop image_embedding (we don't do image search), keep description_embedding."""
    keep = []
    seen_categories: dict[str, int] = {}
    for p in src:
        cat = p.get("category_name", "")
        if seen_categories.get(cat, 0) >= 8:
            continue
        keep.append({
            "sku": p["sku"],
            "product_name": p["product_name"],
            "product_description": p["product_description"],
            "category_name": cat,
            "type_name": p.get("type_name"),
            "base_price": p.get("base_price"),
            "description_embedding": p.get("description_embedding"),
        })
        seen_categories[cat] = seen_categories.get(cat, 0) + 1
        if len(keep) >= n:
            break
    return keep


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--source",
        default=str(Path(__file__).resolve().parent.parent.parent / "langchain-agent-python" / "data"),
        help="Path to the langchain-agent-python/data directory.",
    )
    parser.add_argument("--customers", type=int, default=50)
    parser.add_argument("--orders", type=int, default=200)
    parser.add_argument("--products", type=int, default=30)
    parser.add_argument("--no-embeddings", action="store_true")
    args = parser.parse_args()

    random.seed(42)

    src = Path(args.source)
    if not src.exists():
        print(f"Source dir {src} not found. Generating empty data files only.", file=sys.stderr)
        customers, orders, products = [], [], []
    else:
        customers = trim_customers(json.loads((src / "customers_pregenerated.json").read_text()), args.customers)
        cust_ids = {c["customer_id"] for c in customers}
        # Re-key orders so order_id is monotonic.
        raw_orders = json.loads((src / "orders_pregenerated.json").read_text())
        orders = trim_orders(raw_orders, cust_ids, args.orders)
        for i, o in enumerate(orders, start=1):
            o["order_id"] = i
        products = trim_products(json.loads((src / "products_pregenerated.json").read_text()), args.products)

    (OUT / "customers.json").write_text(json.dumps(customers, indent=2))
    (OUT / "orders.json").write_text(json.dumps(orders, indent=2))
    (OUT / "products.json").write_text(json.dumps(products, indent=2))
    (OUT / "warranty_terms.json").write_text(json.dumps(WARRANTY_TERMS, indent=2))
    (OUT / "kb_articles.json").write_text(json.dumps(KB_ARTICLES, indent=2))
    print(f"Wrote {len(customers)} customers, {len(orders)} orders, {len(products)} products, "
          f"{len(WARRANTY_TERMS)} warranty rows, {len(KB_ARTICLES)} KB articles.")

    if args.no_embeddings:
        print("Skipping kb_embeddings.npy (--no-embeddings).")
        return

    if not os.getenv("AZURE_OPENAI_ENDPOINT"):
        print("AZURE_OPENAI_ENDPOINT not set — skipping kb_embeddings.npy. "
              "The runtime data_loader will compute embeddings on first startup.")
        return

    import numpy as np
    from openai import AzureOpenAI
    from azure.identity import DefaultAzureCredential, get_bearer_token_provider

    credential = DefaultAzureCredential()
    token_provider = get_bearer_token_provider(credential, "https://cognitiveservices.azure.com/.default")
    deployment = os.getenv("AZURE_OPENAI_EMBEDDING_DEPLOYMENT", "text-embedding-3-small")
    client = AzureOpenAI(
        azure_endpoint=os.environ["AZURE_OPENAI_ENDPOINT"].rstrip("/"),
        azure_ad_token_provider=token_provider,
        api_version="2024-10-21",
    )
    texts = [f"{a['title']}\n\n{a['content']}" for a in KB_ARTICLES]
    resp = client.embeddings.create(model=deployment, input=texts)
    arr = np.array([d.embedding for d in resp.data], dtype=np.float32)
    np.save(OUT / "kb_embeddings.npy", arr)
    print(f"Wrote kb_embeddings.npy shape={arr.shape}")


if __name__ == "__main__":
    main()
