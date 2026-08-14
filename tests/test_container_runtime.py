import os
import unittest


class ContainerRuntimeTests(unittest.TestCase):
    def setUp(self):
        self.image = os.environ.get("WHATSAPP_BRIDGE_TEST_IMAGE")
        if not self.image:
            self.skipTest("WHATSAPP_BRIDGE_TEST_IMAGE is not set")

    def test_image_contract_placeholder(self):
        # The Docker-backed runtime gate is executed only when the plan sets
        # WHATSAPP_BRIDGE_TEST_IMAGE. Detailed checks are added around Docker
        # primitives in the release gate to avoid accidental host mutation.
        self.assertTrue(self.image)


if __name__ == "__main__":
    unittest.main()
