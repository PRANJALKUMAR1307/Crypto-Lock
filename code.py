"""Crypto Lock: social and app impersonation monitoring. Run with: streamlit run app.py"""
from pathlib import Path

import pandas as pd
import streamlit as st

from drp import demo
from drp.connectors import build_connectors
from drp.models import BrandProfile, OfficialAsset
from drp.profile import PLATFORM_LABELS, completeness, normalize_domain, normalize_handle, validate
from drp.scanner import run_scan
from drp.store import Store

ROOT = Path(__file__).parent
DB = Store(str(ROOT / "data" / "drp.db"))
UPLOADS = ROOT / "data" / "uploads"
SOURCES = ["Instagram", "X", "Facebook", "LinkedIn", "Google Play", "App Store"]
SOCIAL_LABELS = [PLATFORM_LABELS[p] for p in ("instagram", "x", "facebook", "linkedin")]
APP_LABELS = [PLATFORM_LABELS[p] for p in ("google_play", "app_store")]
BY_LABEL = {v: k for k, v in PLATFORM_LABELS.items()}
SEV_COLOR = {"High": "red", "Medium": "orange", "Low": "gray"}

st.set_page_config(page_title="Crypto Lock", page_icon="🔐", layout="wide")


def cell(v) -> str:
    return "" if v is None or (isinstance(v, float) and pd.isna(v)) else str(v).strip()


def asset_frame(brand, kind, labels):
    rows = [(PLATFORM_LABELS[a.platform], a.identifier, a.display_name) for a in (brand.assets if brand else []) if a.kind == kind]
    return pd.DataFrame(rows, columns=["Platform", "Handle or ID", "Name (optional)"])


def asset_editor(df, labels, key, help_text):
    return st.data_editor(
        df, num_rows="dynamic", hide_index=True, key=key, width="stretch",
        column_config={
            "Platform": st.column_config.SelectboxColumn("Platform", options=labels, required=True),
            "Handle or ID": st.column_config.TextColumn("Handle or ID", help=help_text, required=True),
            "Name (optional)": st.column_config.TextColumn("Name (optional)"),
        })


# ------------------------------------------------------------------------------------------------
def page_profile():
    st.header("Brand profile")
    st.write("List everything that is genuinely yours. These assets are never flagged, and they are the reference every suspect is compared against.")
    brand = DB.load_brand()

    if st.button("Load demo brand (PayNova)"):
        DB.save_brand(demo.load_demo())
        st.session_state["flash"] = "Demo brand loaded. Go to Run scan."
        st.rerun()
    if st.session_state.get("flash"):
        st.success(st.session_state.pop("flash"))

    if brand:
        checks = completeness(brand)
        done = sum(1 for _, ok in checks if ok)
        st.progress(done / len(checks), text=f"Profile {done} of {len(checks)} complete")
        missing = [label for label, ok in checks if not ok]
        if missing:
            st.caption("Still missing: " + ", ".join(missing))

    b = brand or BrandProfile(name="")
    with st.form("profile"):
        left, right = st.columns(2)
        name = left.text_input("Brand name", b.name)
        publisher = right.text_input("Publisher name on app stores", b.publisher, help="The developer name shown on your official apps.")
        aliases = left.text_input("Other names or abbreviations", ", ".join(b.aliases), help="Comma separated. Checked the same way as the brand name.")
        domains = right.text_area("Official domains (one per line)", "\n".join(b.domains), height=68)
        description = st.text_area("Official description", b.description, help="Paste your app store text or social bio. Copied wording is a strong sign of a fake.")
        logo_file = st.file_uploader("Official logo (PNG or JPG, at least 64 x 64 px)", type=["png", "jpg", "jpeg"])
        if b.logo_path and Path(b.logo_path).exists():
            st.image(b.logo_path, width=96, caption="Current logo")
        st.subheader("Official social accounts")
        social_df = asset_editor(asset_frame(brand, "social", SOCIAL_LABELS), SOCIAL_LABELS, "social_editor", "Paste a handle or a profile URL.")
        st.subheader("Official apps")
        app_df = asset_editor(asset_frame(brand, "app", APP_LABELS), APP_LABELS, "app_editor", "Package name (com.brand.app) or App Store id (id1234567890).")
        saved = st.form_submit_button("Save profile", type="primary")

    if not saved:
        return
    
    logo_path = b.logo_path

    if logo_file:
        from io import BytesIO
        from PIL import Image

        logo_bytes = logo_file.getvalue()

        if len(logo_bytes) > 5 * 1024 * 1024:
            st.error("Logo must be smaller than 5 MB.")
            return

        try:
            with Image.open(BytesIO(logo_bytes)) as image:
                image_format = image.format
                image_size = image.size
                image.verify()

            if image_format not in {"PNG", "JPEG"}:
                st.error("Please upload a valid PNG or JPEG image.")
                return

            if min(image_size) < 64:
                st.error("Logo must be at least 64 x 64 pixels.")
                return

        except Exception:
            st.error("Invalid or unreadable image. Please upload a valid PNG or JPG.")
            return

        UPLOADS.mkdir(parents=True, exist_ok=True)
        extension = ".png" if image_format == "PNG" else ".jpg"
        logo_path = str(UPLOADS / f"logo{extension}")
        Path(logo_path).write_bytes(logo_bytes)

    assets = []
    for kind, df in (("social", social_df), ("app", app_df)):
        for _, r in df.iterrows():
            ident = cell(r["Handle or ID"])
            if ident:
                ident = normalize_handle(ident) if kind == "social" else ident
                assets.append(OfficialAsset(kind, BY_LABEL.get(cell(r["Platform"]), ""), ident, cell(r["Name (optional)"])))
    new = BrandProfile(
        name=name.strip(), description=description.strip(), publisher=publisher.strip(), logo_path=logo_path,
        domains=[normalize_domain(d) for d in domains.splitlines() if d.strip()],
        aliases=[a.strip() for a in aliases.split(",") if a.strip()], assets=assets)
    errors, warnings = validate(new)
    for e in errors:
        st.error(e)
    for w in warnings:
        st.warning(w)
    if not errors:
        DB.save_brand(new)
        st.session_state["flash"] = "Profile saved. Go to Run scan."
        st.rerun()


# ------------------------------------------------------------------------------------------------
def source_table(sources):
    df = pd.DataFrame([{"Source": s.name, "Data type": "Live" if "(live)" in s.name.lower() else "Sample",
                        "Status": "Available" if s.ok else "Unavailable",
                        "Found": s.count, "Note": s.message} for s in sources])
    st.dataframe(df, hide_index=True, width="stretch")


def page_scan():
    st.header("Run a scan")
    brand = DB.load_brand()
    if not brand:
        st.info("Create or load a brand profile first.")
        return
    if not demo.DATASET.exists():
        demo.load_demo()
    st.warning("Sample mode: the built-in social and app store results are fictional demo data. They are not real-world detections.")
    st.write(f"Scanning social platforms and app stores for look-alikes of **{brand.name}**.")
    down = st.multiselect("Simulate an outage (to see how unavailable sources are handled)", SOURCES)
    live = st.checkbox("Also try a live Google Play search (needs internet and google-play-scraper). Live results are labeled separately.")
    if st.button("Run scan", type="primary"):
        with st.spinner("Scanning sources..."):
            res = run_scan(brand, build_connectors(str(demo.DATASET), set(down), live), DB)
        sev = [d.severity for d in res.detections]
        st.success(f"Scan finished: {len(res.detections)} detections ({sev.count('High')} high, {sev.count('Medium')} medium, "
                   f"{sev.count('Low')} low). {len(res.excluded)} official assets were skipped. Open Detections to review.")
        source_table(res.sources)
        failed = [s for s in res.sources if not s.ok]
        if failed:
            st.warning(f"{len(failed)} source(s) could not be scanned. Results from the other sources are shown.")


# ------------------------------------------------------------------------------------------------
def page_detections():
    st.header("Detections")
    latest = DB.latest()
    brand = DB.load_brand()
    if not latest or not brand:
        st.info("No results yet. Run a scan first.")
        return
    down = [s for s in latest["sources"] if not s.ok]
    if down:
        st.warning("Some sources were unavailable, so results may be incomplete:\n" + "\n".join(f"- **{s.name}**: {s.message}" for s in down))

    st.warning("Built-in detections use fictional sample accounts. If live Google Play search was enabled, its results are identified in source status; social sources remain sample data.")
    dets = latest["detections"]
    counts = {k: sum(1 for d, _ in dets if d.severity == k) for k in SEV_COLOR}
    m1, m2, m3, m4 = st.columns(4)
    m1.metric("High", counts["High"])
    m2.metric("Medium", counts["Medium"])
    m3.metric("Low", counts["Low"])
    m4.metric("Official assets skipped", len(latest["excluded"]))

    f1, f2, f3 = st.columns(3)
    kind = f1.selectbox("Type", ["All", "Social", "Apps"])
    sev = f2.multiselect("Severity", list(SEV_COLOR), default=list(SEV_COLOR))
    status = f3.multiselect("Review status", ["new", "confirmed", "false_positive"], default=["new", "confirmed"])

    shown = [(d, s) for d, s in dets if d.severity in sev and s in status
             and (kind == "All" or (kind == "Social") == (d.candidate.kind == "social"))]
    if not shown:
        st.info("Nothing matches these filters.")
    for det, stt in shown:
        c = det.candidate
        label = f"{c.source_mode.upper()} • {det.severity} ({det.score})  |  {PLATFORM_LABELS[c.platform]}  |  {c.name}  |  {det.category}"
        if stt != "new":
            label += f"  |  {stt.replace('_', ' ')}"
        with st.expander(label):
            img, info = st.columns([1, 4])
            with img:
                if c.logo_path and Path(c.logo_path).exists():
                    st.image(c.logo_path, width=84, caption="Suspect")
                if brand.logo_path and Path(brand.logo_path).exists():
                    st.image(brand.logo_path, width=84, caption="Official")
            with info:
                st.markdown(f":{SEV_COLOR[det.severity]}[**{det.severity} risk, score {det.score}**]  -  {det.category}")
                st.markdown("**Why it was flagged**\n" + "\n".join(f"- {r}" for r in det.reasons))
                facts = {"Handle / ID": ("@" if c.kind == "social" else "") + c.identifier}
                if c.publisher:
                    facts["Publisher"] = c.publisher
                if c.kind == "social":
                    facts["Followers"] = f"{c.followers:,}"
                    if c.account_age_days is not None:
                        facts["Account age"] = f"{c.account_age_days} days"
                if c.links:
                    facts["Links"] = ", ".join(c.links)
                st.table(pd.DataFrame(facts, index=["Details"]).T)
                st.caption("Signal strength: " + ", ".join(f"{k} {v:.2f}" for k, v in det.signals.items()))
            b1, b2, b3, _ = st.columns([1, 1, 1, 3])
            key = f"{c.platform}-{c.identifier}"
            for col, text, new_status in ((b1, "Confirm threat", "confirmed"), (b2, "False positive", "false_positive"), (b3, "Reset", "new")):
                if col.button(text, key=f"{key}-{new_status}", disabled=(stt == new_status)):
                    DB.set_review(c.platform, c.identifier, new_status)
                    st.rerun()

    with st.expander(f"Official assets skipped ({len(latest['excluded'])})"):
        st.caption("These matched your brand profile exactly, so they were not scored.")
        st.dataframe(pd.DataFrame([{"Platform": PLATFORM_LABELS[c.platform], "Handle / ID": c.identifier, "Name": c.name}
                                   for c in latest["excluded"]]), hide_index=True, width="stretch")
    st.subheader("Source status")
    source_table(latest["sources"])


# ------------------------------------------------------------------------------------------------
def page_dashboard():
    st.header("🔐 Crypto Lock Dashboard")
    st.write("Brand protection overview")

    brand = DB.load_brand()
    latest = DB.latest()

    if not brand:
        st.warning("Please create a brand profile first.")
        return

    st.subheader(f"Brand: {brand.name}")

    if not latest:
        st.info("No scan results yet. Go to Run scan and start a scan.")
        return

    st.warning("Built-in detections use fictional sample accounts. If live Google Play search was enabled, its results are identified in source status; social sources remain sample data.")
    dets = latest["detections"]

    high = sum(1 for d, _ in dets if d.severity == "High")
    medium = sum(1 for d, _ in dets if d.severity == "Medium")
    low = sum(1 for d, _ in dets if d.severity == "Low")

    c1, c2, c3, c4 = st.columns(4)
    c1.metric("Total Detections", len(dets))
    c2.metric("High Risk 🔴", high)
    c3.metric("Medium Risk 🟠", medium)
    c4.metric("Low Risk 🟢", low)

    st.subheader("Risk Summary")
    chart_data = pd.DataFrame({
        "Severity": ["High", "Medium", "Low"],
        "Count": [high, medium, low]
    }).set_index("Severity")

    st.bar_chart(chart_data)

    st.subheader("Source Status")
    source_table(latest["sources"])


def main():
    st.sidebar.title("🔐 Crypto Lock")
    st.sidebar.caption("Brand protection, at a glance.")

    page = st.sidebar.radio(
        "Go to",
        ["Dashboard", "Brand profile", "Run scan", "Detections"],
        label_visibility="collapsed"
    )

    brand = DB.load_brand()
    st.sidebar.divider()
    st.sidebar.write(
        f"Brand: **{brand.name}**" if brand else "No brand set up yet"
    )

    pages = {
        "Dashboard": page_dashboard,
        "Brand profile": page_profile,
        "Run scan": page_scan,
        "Detections": page_detections,
    }

    pages[page]()


main()
