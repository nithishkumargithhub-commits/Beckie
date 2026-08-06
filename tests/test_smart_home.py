import unittest
import sys
import os

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if BASE_DIR not in sys.path:
    sys.path.insert(0, BASE_DIR)

from actions.smart_home import control_smart_device, handle_smart_home_command

class TestSmartHome(unittest.TestCase):

    def test_smart_home_simulation(self):
        success, msg = control_smart_device("light.living_room", "turn_on")
        self.assertTrue(success)
        self.assertIn("living_room", msg)

    def test_smart_home_intent_parsing(self):
        success, msg = handle_smart_home_command("turn off the living room light")
        self.assertTrue(success)
        self.assertIn("turn_off", msg)

if __name__ == '__main__':
    unittest.main()
