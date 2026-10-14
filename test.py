import os, sys, tempfile, unittest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from drp import demo, profile
from drp.connectors import build_connectors
from drp.lookalike import analyze_name, generate_variants
from drp.models import BrandProfile, OfficialAsset
from drp.scanner import run_scan
from drp.store import Store


def name_score(brand, text):
    return analyze_name([brand], [text]).score


class LookalikeTests(unittest.TestCase):
    def test_flags_common_variations(self):
        for text in ["PayNova", "Pay Nova", "pay.nova", "PayN0va", "Paynvoa", "Paynova_",
                     "PayNova Support", "paynova_official", "PayNov4 Help", "paynvoa_support", "PAYNOVA"]:
            self.assertGreaterEqual(name_score("PayNova", text), 0.8, text)

    def test_does_not_flag_normal_names(self):
        for text in ["PayNow", "NovaPay", "Nova Paint Co.", "Paypal", "Pay", "Nova", "Innova Motors", "Panova Studio"]:
            self.assertLess(name_score("PayNova", text), 0.5, text)

    def test_unrelated_use_of_brand_is_weak(self):
        self.assertLess(name_score("PayNova", "PayNova Bakery"), 0.6)

    def test_short_brand_names_need_exact_match(self):
        self.assertEqual(name_score("Zed", "Zed Official"), 0.0)
        self.assertEqual(name_score("Zed", "Zeds"), 0.0)

    def test_variant_generator(self):
        v = generate_variants("PayNova")
        self.assertIn("PayNova", v)
        self.assertTrue(any("0" in x or "4" in x for x in v))


class PipelineTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.brand = demo.load_demo()
        cls.store = Store(os.path.join(tempfile.mkdtemp(), "t.db"))
        cls.store.save_brand(cls.brand)
        cls.res = run_scan(cls.brand, build_connectors(str(demo.DATASET), down={"LinkedIn"}), cls.store)
        cls.by_id = {d.candidate.identifier: d for d in cls.res.detections}

    def test_official_assets_are_never_flagged(self):
        for a in self.brand.assets:
            self.assertNotIn(a.identifier, self.by_id)
        self.assertEqual(len(self.res.excluded), 4)

    def test_known_fakes_are_high(self):
        for ident in ["paynova_support", "PayN0va_Help", "com.quickapps.paynovawallet", "com.pn0va.pay", "id9988776655"]:
            self.assertEqual(self.by_id[ident].severity, "High", ident)

    def test_unrelated_accounts_and_apps_are_not_flagged(self):
        for ident in ["novapay", "paynow.in", "nova_paint_co", "com.paynow.bills", "com.paintnova.colors", "id5544332211"]:
            self.assertNotIn(ident, self.by_id)

    def test_same_publisher_app_is_downgraded(self):
        self.assertEqual(self.by_id["com.paynova.business"].severity, "Low")

    def test_name_only_match_never_reaches_high(self):
        self.assertLess(self.by_id["paynvoa"].score, 70)

    def test_unavailable_source_does_not_stop_scan(self):
        li = [s for s in self.res.sources if s.name == "LinkedIn"][0]
        self.assertFalse(li.ok)
        self.assertGreater(len(self.res.detections), 5)

    def test_every_detection_has_reasons_and_category(self):
        for d in self.res.detections:
            self.assertTrue(d.reasons)
            self.assertTrue(d.category)
            self.assertEqual(d.candidate.source_mode, "sample")

    def test_results_round_trip_through_storage(self):
        latest = self.store.latest()
        self.assertEqual(len(latest["detections"]), len(self.res.detections))
        self.store.set_review("instagram", "paynova_support", "confirmed")
        status = {d.candidate.identifier: s for d, s in self.store.latest()["detections"]}
        self.assertEqual(status["paynova_support"], "confirmed")


class ProfileValidationTests(unittest.TestCase):
    def test_demo_profile_is_valid(self):
        errors, _ = profile.validate(demo.load_demo())
        self.assertEqual(errors, [])

    def test_catches_bad_input(self):
        b = BrandProfile(name="X", domains=["not a domain"], assets=[
            OfficialAsset("social", "x", "way_too_long_for_x_handle"),
            OfficialAsset("app", "google_play", "notapackage"),
            OfficialAsset("app", "google_play", "com.ok.app"), OfficialAsset("app", "google_play", "com.ok.app")])
        errors, _ = profile.validate(b)
        self.assertGreaterEqual(len(errors), 5)

    def test_handle_normalisation(self):
        self.assertEqual(profile.normalize_handle("@paynova"), "paynova")
        self.assertEqual(profile.normalize_handle("https://www.instagram.com/paynova/?hl=en"), "paynova")
        self.assertEqual(profile.normalize_domain("https://www.PayNova.in/about"), "paynova.in")

    def test_requires_an_official_asset(self):
        errors, _ = profile.validate(BrandProfile(name="PayNova"))
        self.assertTrue(any("official" in e for e in errors))


if __name__ == "__main__":
    unittest.main(verbosity=2)
