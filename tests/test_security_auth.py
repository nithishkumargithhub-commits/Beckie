import unittest
import sys
import os

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if BASE_DIR not in sys.path:
    sys.path.insert(0, BASE_DIR)

import config
from actions.code_agent import inspect_code_safety

class TestSecurityAuth(unittest.TestCase):

    def test_safe_code_ast_inspection(self):
        safe_code = """
x = 10
y = 20
print(f"Sum is: {x + y}")
"""
        self.assertTrue(inspect_code_safety(safe_code))

    def test_unsafe_code_ast_inspection(self):
        unsafe_code_os = "import os\nos.system('dir')"
        unsafe_code_eval = "x = eval('1 + 1')"
        unsafe_code_subclass = "x = (1).__class__.__subclasses__()"

        self.assertFalse(inspect_code_safety(unsafe_code_os))
        self.assertFalse(inspect_code_safety(unsafe_code_eval))
        self.assertFalse(inspect_code_safety(unsafe_code_subclass))

if __name__ == '__main__':
    unittest.main()
