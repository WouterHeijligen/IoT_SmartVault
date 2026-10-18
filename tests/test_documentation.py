from html.parser import HTMLParser
from pathlib import Path
import unittest
from urllib.parse import unquote, urlsplit


DOCS = Path(__file__).resolve().parents[1] / "docs"


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


if __name__ == "__main__":
    unittest.main()
