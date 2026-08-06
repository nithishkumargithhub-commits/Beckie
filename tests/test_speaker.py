import unittest
import sys
import os
import time

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if BASE_DIR not in sys.path:
    sys.path.insert(0, BASE_DIR)

from tts.speaker import Speaker

class TestSpeaker(unittest.TestCase):

    def setUp(self):
        self.speaker = Speaker()

    def test_speaker_barge_in_stop(self):
        # Call stop() directly and verify stop_requested becomes True
        self.speaker.stop()
        self.assertTrue(self.speaker.stop_requested)

if __name__ == '__main__':
    unittest.main()
