"""
Unit tests for Calendar, Tasks, and Spotify REST API endpoints on server.py.
"""

from unittest.mock import patch, MagicMock
from fastapi.testclient import TestClient
import pytest
from server import app

client = TestClient(app)

def test_get_calendar_events_endpoint():
    with patch("actions.google_services.get_structured_calendar_events") as mock_cal:
        mock_cal.return_value = [
            {"id": "ev1", "summary": "Bus to Trichy", "start": "2026-10-01T16:00:00Z"}
        ]
        response = client.get("/api/calendar/events")
        assert response.status_code == 200
        data = response.json()
        assert data["success"] is True
        assert len(data["events"]) == 1
        assert data["events"][0]["summary"] == "Bus to Trichy"

def test_create_calendar_event_endpoint():
    with patch("actions.google_services.add_calendar_event") as mock_add:
        mock_add.return_value = (True, "Event scheduled successfully.")
        response = client.post("/api/calendar/events", json={"title": "Team Sync", "datetime_str": "tomorrow at 10am"})
        assert response.status_code == 200
        data = response.json()
        assert data["success"] is True
        assert "Event scheduled" in data["message"]

def test_get_tasks_endpoint():
    with patch("actions.google_services.get_structured_tasks") as mock_tasks:
        mock_tasks.return_value = [
            {"id": "t1", "title": "Buy groceries", "completed": False, "status": "needsAction"}
        ]
        response = client.get("/api/tasks")
        assert response.status_code == 200
        data = response.json()
        assert data["success"] is True
        assert len(data["tasks"]) == 1
        assert data["tasks"][0]["title"] == "Buy groceries"

def test_toggle_task_endpoint():
    with patch("actions.google_services.set_task_completed") as mock_toggle:
        mock_toggle.return_value = (True, "Task status updated to completed.")
        response = client.post("/api/tasks/toggle", json={"task_id": "t1", "completed": True})
        assert response.status_code == 200
        data = response.json()
        assert data["success"] is True
        assert "completed" in data["message"]

def test_get_spotify_current_endpoint():
    with patch("actions.spotify_integration.get_current_track_data") as mock_sp:
        mock_sp.return_value = {
            "is_active": True,
            "is_playing": True,
            "title": "Starboy",
            "artist": "The Weeknd"
        }
        response = client.get("/api/spotify/current")
        assert response.status_code == 200
        data = response.json()
        assert data["success"] is True
        assert data["track"]["title"] == "Starboy"

def test_spotify_control_endpoint():
    with patch("actions.spotify_integration.pause") as mock_pause:
        mock_pause.return_value = (True, "Playback paused.")
        response = client.post("/api/spotify/control", json={"action": "pause"})
        assert response.status_code == 200
        data = response.json()
        assert data["success"] is True
        assert "paused" in data["message"]

def test_get_spotify_playlists_endpoint():
    with patch("actions.spotify_integration.get_playlists") as mock_pls:
        mock_pls.return_value = [
            {"id": "pl1", "name": "Lo-Fi Focus", "uri": "spotify:playlist:123", "track_count": 25, "curator": "Beckie"}
        ]
        response = client.get("/api/spotify/playlists")
        assert response.status_code == 200
        data = response.json()
        assert data["success"] is True
        assert len(data["playlists"]) == 1
        assert data["playlists"][0]["name"] == "Lo-Fi Focus"

def test_get_spotify_preferences_endpoint():
    with patch("actions.spotify_integration.get_preferences") as mock_prefs:
        mock_prefs.return_value = {
            "favorite_genres": ["Lo-Fi", "Synthwave"],
            "sound_profile": "Bass Boosted"
        }
        response = client.get("/api/spotify/preferences")
        assert response.status_code == 200
        data = response.json()
        assert data["success"] is True
        assert "Lo-Fi" in data["preferences"]["favorite_genres"]

def test_spotify_play_endpoint():
    with patch("actions.spotify_integration.play") as mock_play:
        mock_play.return_value = (True, "Playing 'Starboy' on Spotify.")
        response = client.post("/api/spotify/play", json={"query": "Starboy"})
        assert response.status_code == 200
        data = response.json()
        assert data["success"] is True
        assert "Starboy" in data["message"]

