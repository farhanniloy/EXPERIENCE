from django.test import SimpleTestCase
from django.urls import reverse


class HealthEndpointTest(SimpleTestCase):
    def test_health_endpoint(self):
        response = self.client.get(reverse("health-check"))

        self.assertEqual(response.status_code, 200)
        payload = response.json()
        self.assertEqual(payload["status"], "ok")
        self.assertEqual(payload["service"], "along-backend")
