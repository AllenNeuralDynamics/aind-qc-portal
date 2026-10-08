"""Regression coverage for public API documentation and its route contract."""

import json
import re
import unittest

from tornado.testing import AsyncHTTPTestCase
from tornado.web import Application

from aind_qc_portal import plugin


class TestApiDocs(AsyncHTTPTestCase):
    """Exercise documentation through the same routes used by Panel."""

    def get_app(self):
        """Create the custom endpoint application without backend requests."""
        return Application(plugin.ROUTES)

    def test_docs_and_trailing_slash(self):
        """Both docs URLs serve Swagger UI loading the local specification."""
        for path in ("/docs", "/docs/"):
            with self.subTest(path=path):
                response = self.fetch(path)
                self.assertEqual(response.code, 200)
                self.assertIn("text/html", response.headers["Content-Type"])
                self.assertIn(b"SwaggerUIBundle", response.body)
                self.assertIn(b"/openapi.json", response.body)
                self.assertIn(b"validatorUrl: null", response.body)

    def test_spec_documents_every_handler_method(self):
        """Every custom API method has a matching documented operation."""
        response = self.fetch("/openapi.json")
        self.assertEqual(response.code, 200)
        self.assertIn("application/json", response.headers["Content-Type"])
        spec = json.loads(response.body)
        self.assertEqual(spec["openapi"], "3.0.3")
        for route, handler, _ in plugin.ROUTES:
            if route in (r"/docs/?", r"/openapi\.json"):
                continue
            matching = [path for path in spec["paths"] if re.fullmatch(route, re.sub(r"\{[^}]+\}", "example", path))]
            self.assertTrue(matching, route)
            for path in matching:
                for method in ("get", "post", "delete", "put", "patch"):
                    if method in handler.__dict__:
                        self.assertIn(method, spec["paths"][path], (route, method))
        schemas = spec["components"]["schemas"]
        for name in re.findall(r'"\$ref": "#/components/schemas/([^"/]+)"', json.dumps(spec)):
            self.assertIn(name, schemas)
        submit = spec["paths"]["/api/qc/submit"]["post"]
        self.assertEqual(submit["security"], [{"EntraBearer": []}])
        self.assertIn("allow_tag_failures", schemas["QcSubmit"]["properties"])
        self.assertFalse(schemas["QcSubmit"]["additionalProperties"])
        self.assertEqual(spec["paths"]["/metadata/proposals"]["get"]["security"], [])


if __name__ == "__main__":
    unittest.main()
