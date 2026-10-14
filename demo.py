"""Demo data: a fictional brand ("PayNova"), generated logos, and a mock set of search results."""
from __future__ import annotations

import json
from pathlib import Path

from PIL import Image, ImageDraw

from .models import BrandProfile, OfficialAsset

DATA_DIR = Path(__file__).resolve().parent.parent / "data"
DATASET = DATA_DIR / "mock_sources.json"


def _official(d: ImageDraw.ImageDraw, bg, ring, core, size=256):
    d.rounded_rectangle((0, 0, size, size), radius=40, fill=bg)
    d.ellipse((48, 48, 208, 208), fill=ring)
    d.ellipse((100, 70, 186, 156), fill=core)
    d.polygon([(60, 190), (110, 190), (190, 90), (140, 90)], fill=bg)


def make_logos(out_dir: Path) -> dict:
    out_dir.mkdir(parents=True, exist_ok=True)
    paths = {}

    def save(name, draw_fn, size=256):
        im = Image.new("RGB", (256, 256), (255, 255, 255))
        draw_fn(ImageDraw.Draw(im))
        if size != 256:
            im = im.resize((size, size), Image.LANCZOS)
        p = out_dir / f"{name}.png"
        im.save(p)
        paths[name] = str(p)

    navy, white, cyan = (18, 32, 74), (255, 255, 255), (0, 200, 200)
    save("official", lambda d: _official(d, navy, white, cyan))
    save("clone_exact", lambda d: _official(d, navy, white, cyan), size=192)
    save("clone_recolor", lambda d: _official(d, (60, 20, 90), (250, 240, 200), (200, 120, 230)))

    def tweak(d):
        _official(d, navy, white, cyan)
        d.ellipse((196, 14, 240, 58), fill=(230, 40, 40))
    save("clone_tweak", tweak)

    def orange(d):
        d.rectangle((0, 0, 256, 256), fill=(240, 120, 30))
        d.polygon([(128, 40), (220, 210), (36, 210)], fill=white)
    save("other_orange", orange)

    def stripes(d):
        d.rectangle((0, 0, 256, 256), fill=(30, 120, 60))
        for x in range(0, 256, 48):
            d.rectangle((x, 0, x + 20, 256), fill=(200, 235, 210))
    save("other_green", stripes)

    def ring(d):
        d.rectangle((0, 0, 256, 256), fill=(20, 20, 20))
        d.ellipse((50, 50, 206, 206), outline=white, width=26)
    save("other_ring", ring)

    def bucket(d):
        d.rectangle((0, 0, 256, 256), fill=(250, 220, 90))
        d.rectangle((70, 90, 190, 200), fill=(200, 60, 60))
        d.rectangle((60, 70, 200, 90), fill=(90, 30, 30))
    save("other_paint", bucket)
    return paths


def build_dataset(L: dict) -> list:
    def s(platform, ident, name, desc="", logo="", **kw):
        return dict(kind="social", platform=platform, identifier=ident, name=name, description=desc,
                    logo_path=L.get(logo, ""), url=f"https://{platform}.example/{ident}", **kw)

    def a(platform, ident, name, publisher, desc="", logo=""):
        return dict(kind="app", platform=platform, identifier=ident, name=name, publisher=publisher,
                    description=desc, logo_path=L.get(logo, ""), url=f"https://store.example/{ident}")

    return [
        # --- Instagram
        s("instagram", "paynova", "PayNova", "Official PayNova account. UPI payments and digital wallet.", "official", followers=482000, account_age_days=2100, verified=True),
        s("instagram", "paynova_support", "PayNova Support Care", "Failed transaction? DM us your card details and OTP for instant refund. Official helpdesk.", "clone_exact",
          links=["https://bit.ly/pn-refund"], followers=340, account_age_days=21),
        s("instagram", "pay.nova.official", "Pay Nova Official", "Lucky draw winners announced daily! Claim your cashback reward now.", "clone_recolor",
          followers=1200, account_age_days=45),
        s("instagram", "paynova_fan_club", "PayNova Fan Club", "Fans of the PayNova app design. Unofficial.", "other_ring", followers=900, account_age_days=500),
        s("instagram", "nova_paint_co", "Nova Paint Co.", "Premium wall paints and colour consulting.", "other_paint", followers=5400, account_age_days=1500),
        s("instagram", "paynow.in", "PayNow", "Utility bill payments made easy.", "other_orange", followers=22000, account_age_days=900),
        # --- X
        s("x", "paynova_in", "PayNova", "Updates from PayNova. UPI, wallet and bill payments.", "official", followers=210000, account_age_days=2000, verified=True),
        s("x", "PayN0va_Help", "PayN0va Help", "Customer care 24x7. Share your OTP on WhatsApp to resolve KYC issues.", "clone_recolor",
          links=["https://paynova-kyc.com/verify"], followers=95, account_age_days=12),
        s("x", "novapay", "NovaPay", "Cross-border remittance for freelancers.", "other_green", followers=7800, account_age_days=700),
        # --- Facebook
        s("facebook", "paynova-rewards-india", "PayNova Rewards India", "Official rewards page. Claim your free cashback now, limited offer!", "clone_tweak",
          account_type="page", followers=2300, account_age_days=60),
        s("facebook", "paynvoa", "Paynvoa", "Digital payments.", "other_orange", followers=120, account_age_days=800, account_type="page"),
        # --- LinkedIn
        s("linkedin", "paynova-careers-hiring", "PayNova Careers Hiring", "Work from home jobs. Pay a registration fee to confirm your job offer.", "clone_exact",
          account_type="page", followers=40, account_age_days=30),
        # --- Google Play
        a("google_play", "com.paynova.app", "PayNova: UPI & Wallet", "PayNova Technologies Pvt Ltd", "Send money, pay bills, recharge and manage your wallet securely with PayNova UPI.", "official"),
        a("google_play", "com.paynova.business", "PayNova Business", "PayNova Technologies Pvt Ltd", "Accept payments for your shop.", "clone_tweak"),
        a("google_play", "com.quickapps.paynovawallet", "PayNova Wallet - Fast Pay", "Quick Apps Studio", "Send money, pay bills, recharge and manage your wallet with PayNova UPI. Free cashback.", "clone_exact"),
        a("google_play", "com.pn0va.pay", "PayN0va Pay", "PayNova Tech Solutions", "Pay bills and recharge with your wallet.", "clone_recolor"),
        a("google_play", "com.paynova.apk.mod", "PayNova Mod APK Unlimited Cashback", "Mod Hub", "Download the mod apk with unlimited cashback.", "other_ring"),
        a("google_play", "com.freecash.novarewards", "Nova Rewards - Free Cash", "Reward Labs", "Earn free cash with PayNova partner offers.", "other_green"),
        a("google_play", "com.paynow.bills", "PayNow Bills", "PayNow Services", "Pay utility bills.", "other_orange"),
        a("google_play", "com.paintnova.colors", "Paint Nova", "Colour Works", "Pick wall colours for your home.", "other_paint"),
        # --- App Store
        a("app_store", "id1100223344", "PayNova", "PayNova Technologies Pvt Ltd", "Send money, pay bills, recharge and manage your wallet securely with PayNova UPI.", "official"),
        a("app_store", "id9988776655", "PayNova Pay - Official Wallet", "Digital Wallet Apps LLC", "Pay bills and manage your PayNova wallet.", "clone_tweak"),
        a("app_store", "id5544332211", "NovaPay Global", "NovaPay Inc", "Cross-border remittance.", "other_green"),
    ]


def demo_brand(L: dict) -> BrandProfile:
    return BrandProfile(
        name="PayNova",
        description="PayNova is a UPI payments app and digital wallet. Send money, pay bills, recharge and manage your wallet securely.",
        publisher="PayNova Technologies Pvt Ltd",
        logo_path=L["official"],
        domains=["paynova.in"],
        aliases=[],
        assets=[
            OfficialAsset("social", "instagram", "paynova", "PayNova"),
            OfficialAsset("social", "x", "paynova_in", "PayNova"),
            OfficialAsset("app", "google_play", "com.paynova.app", "PayNova: UPI & Wallet"),
            OfficialAsset("app", "app_store", "id1100223344", "PayNova"),
        ],
    )


def load_demo() -> BrandProfile:
    """Generate logos and mock data on disk and return the demo brand profile."""
    logos = make_logos(DATA_DIR / "logos")
    DATASET.parent.mkdir(parents=True, exist_ok=True)
    DATASET.write_text(json.dumps(build_dataset(logos), indent=1), encoding="utf-8")
    return demo_brand(logos)
