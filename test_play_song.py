import os
import sys
import unittest
from unittest.mock import patch, MagicMock

# Add project root to sys.path
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
if BASE_DIR not in sys.path:
    sys.path.insert(0, BASE_DIR)

from intent.classifier import IntentClassifier, IntentEnum
from actions.web_search_play import play_song_or_video

class TestPlaySongIntegration(unittest.TestCase):

    def setUp(self):
        self.classifier = IntentClassifier()

    def test_fallback_rule_based_spotify(self):
        result1 = self.classifier._fallback_rule_based_classifier("play shape of you on spotify")
        self.assertEqual(result1.intent, IntentEnum.PLAY_SONG)
        self.assertEqual(result1.params.get("platform"), "spotify")

        result2 = self.classifier._fallback_rule_based_classifier("play spotify shape of you")
        self.assertEqual(result2.intent, IntentEnum.PLAY_SONG)
        self.assertEqual(result2.params.get("platform"), "spotify")

        result3 = self.classifier._fallback_rule_based_classifier("play song shape of you in spotify")
        self.assertEqual(result3.intent, IntentEnum.PLAY_SONG)
        self.assertEqual(result3.params.get("platform"), "spotify")

    def test_fallback_rule_based_youtube(self):
        result1 = self.classifier._fallback_rule_based_classifier("play shape of you on youtube")
        self.assertEqual(result1.intent, IntentEnum.PLAY_SONG)
        self.assertEqual(result1.params.get("platform"), "youtube")

        result2 = self.classifier._fallback_rule_based_classifier("play shape of you")
        self.assertEqual(result2.intent, IntentEnum.PLAY_SONG)
        self.assertEqual(result2.params.get("platform"), "youtube")

    def test_fallback_rule_based_web(self):
        result1 = self.classifier._fallback_rule_based_classifier("play shape of you on google")
        self.assertEqual(result1.intent, IntentEnum.PLAY_SONG)
        self.assertEqual(result1.params.get("platform"), "web")

    @patch("actions.web_search_play.os.startfile")
    def test_play_song_or_video_spotify_app(self, mock_startfile):
        success, msg = play_song_or_video("play shape of you on spotify", platform="spotify")
        self.assertTrue(success)
        self.assertIn("Spotify", msg)
        mock_startfile.assert_called_once_with("spotify:search:shape%20of%20you")

    @patch("actions.web_search_play.os.startfile", side_effect=OSError("Spotify app not installed"))
    @patch("actions.web_search_play.subprocess.Popen")
    @patch("actions.web_search_play.find_chrome_executable", return_value=r"C:\Program Files\Google\Chrome\Application\chrome.exe")
    def test_play_song_or_video_spotify_fallback_web(self, mock_chrome_path, mock_popen, mock_startfile):
        success, msg = play_song_or_video("play shape of you on spotify", platform="spotify")
        self.assertTrue(success)
        self.assertIn("Spotify", msg)
        mock_popen.assert_called_once()
        cmd = mock_popen.call_args[0][0]
        self.assertIn("https://open.spotify.com/search/shape%20of%20you", cmd[2])

    @patch("actions.web_search_play.subprocess.Popen")
    @patch("actions.web_search_play.find_chrome_executable", return_value=r"C:\Program Files\Google\Chrome\Application\chrome.exe")
    def test_play_song_or_video_youtube(self, mock_chrome_path, mock_popen):
        success, msg = play_song_or_video("play shape of you on youtube", platform="youtube")
        self.assertTrue(success)
        self.assertIn("YouTube", msg)
        mock_popen.assert_called_once()
        cmd = mock_popen.call_args[0][0]
        self.assertIn("https://www.youtube.com/results?search_query=shape+of+you", cmd[2])

if __name__ == "__main__":
    unittest.main()
