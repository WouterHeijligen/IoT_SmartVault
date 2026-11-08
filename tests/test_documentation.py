from html.parser import HTMLParser
from pathlib import Path
import re
import unittest
from urllib.parse import unquote, urlsplit


ROOT = Path(__file__).resolve().parents[1]
DOCS = ROOT / "docs"
TEXT_DOCS = ROOT / "txt-files" / "docs"
CODE_EXPORTS = {
    "display.txt": "display.py",
    "main.txt": "main.py",
    "mqtt_client.txt": "mqtt_client.py",
    "notificaties.txt": "notificaties.py",
    "pico_2w_code.txt": "pico_2w/code.py",
    "preflight_check.txt": "preflight_check.py",
    "sensors.txt": "sensors.py",
    "vault_lock.txt": "vault_lock.py",
    "vault_state.txt": "vault_state.py",
    "voice.txt": "voice.py",
    "zwaailicht.txt": "zwaailicht.py",
}


def normalized_text(path):
    return path.read_text(encoding="utf-8").replace("\r\n", "\n").rstrip("\n")


class Page(HTMLParser):
    def __init__(self, path):
        super().__init__(convert_charrefs=True)
        self.references = []
        self.ids = set()
        self.has_title = False
        self.language = None
        self.has_viewport = False
        self.feed(path.read_text(encoding="utf-8"))
        self.close()

    def handle_starttag(self, tag, attrs):
        attrs = dict(attrs)
        if "id" in attrs:
            self.ids.add(attrs["id"])
        if tag == "title":
            self.has_title = True
        if tag == "html":
            self.language = attrs.get("lang")
        if tag == "meta" and attrs.get("name") == "viewport":
            self.has_viewport = True
        for attribute in ("href", "src"):
            if attribute in attrs:
                self.references.append(attrs[attribute])


class DocumentationTests(unittest.TestCase):
    def test_site_pages_and_local_references(self):
        self.assertTrue((DOCS / "index.html").is_file())
        pages = {path.resolve(): Page(path) for path in DOCS.rglob("*.html")}
        for path, page in pages.items():
            with self.subTest(page=path.name):
                self.assertTrue(page.has_title, "Missing title")
                expected_language = "nl" if path.parent.name == "nl" else "en"
                self.assertEqual(page.language, expected_language, "Incorrect page language")
                self.assertTrue(page.has_viewport, "Missing mobile viewport")
            for reference in page.references:
                with self.subTest(page=path.name, reference=reference):
                    url = urlsplit(reference)
                    if url.scheme or url.netloc:
                        continue
                    self.assertFalse(url.path.startswith("/"), "Use project-relative URLs")
                    target = (path.parent / unquote(url.path)).resolve() if url.path else path
                    self.assertTrue(target.is_relative_to(DOCS.resolve()), "Link escapes site")
                    self.assertTrue(target.is_file(), "Missing link target")
                    if url.fragment and target in pages:
                        self.assertIn(unquote(url.fragment), pages[target].ids)

    def test_every_english_page_has_a_dutch_counterpart_and_toggle(self):
        for page in DOCS.glob("*.html"):
            dutch_page = DOCS / "nl" / page.name
            with self.subTest(page=page.name):
                self.assertTrue(dutch_page.is_file(), f"Missing Dutch page: {dutch_page.name}")
                self.assertIn(f"nl/{page.name}", Page(page).references)
                self.assertIn(f"../{page.name}", Page(dutch_page).references)

    def test_protocol_walkthroughs_explain_project_links_and_external_sources(self):
        markers = (
            "I2C",
            "SPI0",
            "SPI1",
            "MQTT",
            "Wi-Fi",
            "HTTPS",
            "PWM",
            "mqtt.org",
            "ntfy.sh/publish",
        )
        for page in (DOCS / "code.html", DOCS / "nl" / "code.html"):
            with self.subTest(page=page):
                text = page.read_text(encoding="utf-8")
                for marker in markers:
                    self.assertIn(marker, text)

    def test_code_text_exports_match_current_sources(self):
        for export_name, source_name in CODE_EXPORTS.items():
            with self.subTest(export=export_name):
                export = ROOT / "txt-files" / export_name
                source = ROOT / source_name
                self.assertTrue(export.is_file(), f"Missing export: {export_name}")
                self.assertEqual(normalized_text(export), normalized_text(source))

    def test_documentation_text_exports_exist_for_site_pages(self):
        for page in DOCS.glob("*.html"):
            with self.subTest(page=page.name):
                relative = page.relative_to(DOCS)
                export = TEXT_DOCS / relative.with_suffix(".txt")
                self.assertTrue(export.is_file(), f"Missing export: {export.name}")
                source_path = str(relative).replace("/", "\\")
                self.assertIn(
                    f"Source: docs\\{source_path}",
                    export.read_text(encoding="utf-8"),
                )

    def test_hardware_guide_and_text_export_cover_current_connections(self):
        expected = (
            "GPIO 25",
            "GPIO 3",
            "GPIO 26",
            "MOSI1",
            "GP27 / GP28",
            "8 November 2026",
            "3.3 V supply for the selected LM35 has been verified",
        )
        code_sources = (
            "main.py",
            "sensors.py",
            "display.py",
            "pico_2w/code.py",
            "mqtt_client.py",
            "vault_lock.py",
            "zwaailicht.py",
            "voice.py",
            "notificaties.py",
        )
        for path in (DOCS / "hardware.html", TEXT_DOCS / "hardware.txt"):
            with self.subTest(document=path.name):
                text = path.read_text(encoding="utf-8")
                for marker in expected:
                    self.assertIn(marker, text)
                for source in code_sources:
                    self.assertIn(
                        f"blob/master/{source}",
                        text,
                        f"Missing code reference for {source}",
                    )

    def test_each_hardware_connection_table_links_its_code_reference(self):
        table_sources = {
            "connections-pi5": ("main.py",),
            "connections-bh1750": ("sensors.py",),
            "connections-mcp3008": ("sensors.py",),
            "connections-potentiometer": ("sensors.py", "main.py"),
            "connections-lm35": ("sensors.py", "main.py"),
            "connections-button": ("main.py",),
            "connections-oled": ("display.py", "main.py"),
            "connections-pico-node": ("pico_2w/code.py", "mqtt_client.py"),
            "connections-relay": ("vault_lock.py",),
            "connections-stepper": ("vault_lock.py",),
            "connections-rgb-led": ("zwaailicht.py",),
            "connections-audio": ("voice.py", "notificaties.py"),
        }
        for path in (DOCS / "hardware.html", DOCS / "nl" / "hardware.html"):
            text = path.read_text(encoding="utf-8")
            page = Page(path)
            for table_id, sources in table_sources.items():
                with self.subTest(page=path, table=table_id):
                    self.assertIn(table_id, page.ids)
                    table = re.search(
                        rf'<table id="{re.escape(table_id)}">(.*?)</table>',
                        text,
                        re.DOTALL,
                    )
                    self.assertIsNotNone(table, "Missing component connection table")
                    for source in sources:
                        reference = (
                            "https://github.com/WouterHeijligen/"
                            f"IoT_SmartVault/blob/master/{source}"
                        )
                        self.assertIn(reference, table.group(1))


if __name__ == "__main__":
    unittest.main()
