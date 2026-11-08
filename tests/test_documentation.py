from html.parser import HTMLParser
from pathlib import Path
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
        self.has_language = False
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
            self.has_language = bool(attrs.get("lang"))
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
                self.assertTrue(page.has_language, "Missing page language")
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
                export = TEXT_DOCS / f"{page.stem}.txt"
                self.assertTrue(export.is_file(), f"Missing export: {export.name}")
                self.assertIn(f"Source: docs\\{page.name}", export.read_text(encoding="utf-8"))

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
        for path in (DOCS / "hardware.html", TEXT_DOCS / "hardware.txt"):
            with self.subTest(document=path.name):
                text = path.read_text(encoding="utf-8")
                for marker in expected:
                    self.assertIn(marker, text)


if __name__ == "__main__":
    unittest.main()
