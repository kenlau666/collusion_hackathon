"""Offline authentication/configuration checks; credentials are fixtures."""

import unittest
from modal_endpoint import EndpointConfig,probe


class EndpointTests(unittest.TestCase):
    def test_bearer_and_proxy_auth_without_secret_repr(self):
        values={"MODAL_ENDPOINT_BASE_URL":"https://fixture.modal.direct",
                "MODAL_ENDPOINT_API_KEY":"fixture-private-bearer",
                "MODAL_PROXY_TOKEN_ID":"fixture-id","MODAL_PROXY_TOKEN_SECRET":"fixture-secret"}
        config=EndpointConfig.from_values(values)
        self.assertEqual(config.base_url,"https://fixture.modal.direct/v1")
        self.assertEqual(config.auth_mode,"bearer_and_proxy")
        self.assertEqual(config.headers["Authorization"],"Bearer fixture-private-bearer")
        self.assertEqual(config.headers["Modal-Secret"],"fixture-secret")
        self.assertNotIn("fixture-private-bearer",repr(config))
        self.assertNotIn("fixture-secret",repr(config))

    def test_reject_missing_or_incomplete_credentials(self):
        values={"MODAL_ENDPOINT_BASE_URL":"https://fixture.modal.direct/v1"}
        with self.assertRaises(ValueError):
            EndpointConfig.from_values(values)
        values["MODAL_PROXY_TOKEN_ID"]="fixture-id"
        with self.assertRaises(ValueError):
            EndpointConfig.from_values(values)

    def test_reject_credentials_in_url(self):
        for url in ["http://fixture.modal.direct", "https://user:secret@fixture.modal.direct/v1",
                    "https://fixture.modal.direct/v1?key=private", "https://fixture.modal.direct/#private"]:
            with self.subTest(url=url),self.assertRaises(ValueError):
                EndpointConfig.from_values({"MODAL_ENDPOINT_BASE_URL":url,"MODAL_ENDPOINT_API_KEY":"fixture"})

    def test_probe_uses_get_models_only_and_sanitizes_report(self):
        class Response:
            status_code=200
            def json(self):
                return {"data":[{"id":"fixture-model"}]}
        class Transport:
            def get(self,url,headers):
                self.url,self.headers=url,headers
                return Response()
        config=EndpointConfig.from_values({"MODAL_ENDPOINT_BASE_URL":"https://fixture.modal.direct/v1",
                                          "MODAL_ENDPOINT_API_KEY":"fixture-secret",
                                          "MODAL_ENDPOINT_MODEL":"fixture-model"})
        transport=Transport()
        report=probe(config,transport)
        self.assertEqual(transport.url,"https://fixture.modal.direct/v1/models")
        self.assertTrue(report["configured_model_listed"])
        self.assertEqual(report["generation_requests"],0)
        self.assertNotIn("fixture-secret",str(report))


if __name__=="__main__":
    unittest.main(verbosity=2)
