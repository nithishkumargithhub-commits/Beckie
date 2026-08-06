import unittest
import sys
import os

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if BASE_DIR not in sys.path:
    sys.path.insert(0, BASE_DIR)

from actions.memory_rag import store_memory, query_memories, init_rag_table

class TestMemoryRAG(unittest.TestCase):

    def setUp(self):
        init_rag_table()

    def test_store_and_query_memory(self):
        store_memory("My favorite programming language is Python.", category="preference")
        memories = query_memories("What is my favorite programming language?")
        self.assertTrue(len(memories) > 0)
        self.assertIn("Python", memories[0])

if __name__ == '__main__':
    unittest.main()
