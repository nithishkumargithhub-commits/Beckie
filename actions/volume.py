"""
Offline Windows Volume Control Action using pycaw.
Execution latency: ~50ms
"""

from logger import profile, get_logger

logger = get_logger("Jarvis.Actions.Volume")

class VolumeController:
    def __init__(self):
        self._volume_interface = None

    def _get_interface(self):
        if self._volume_interface is None:
            try:
                import comtypes
                comtypes.CoInitialize()
                from pycaw.pycaw import AudioUtilities, IAudioEndpointVolume
                from ctypes import POINTER, cast
                from comtypes import CLSCTX_ALL
                devices = AudioUtilities.GetSpeakers()
                self._volume_interface = cast(
                    devices.Activate(IAudioEndpointVolume._iid_, CLSCTX_ALL, None),
                    POINTER(IAudioEndpointVolume)
                )
            except Exception as e:
                logger.error(f"Failed to initialize pycaw volume interface: {e}")
                self._volume_interface = False
        return self._volume_interface

    @profile
    def set_volume(self, level: int) -> str:
        interface = self._get_interface()
        if not interface:
            return "Volume control interface unavailable."
        level = max(0, min(100, level))
        interface.SetMasterVolumeLevelScalar(level / 100.0, None)
        return f"Volume set to {level} percent."

    @profile
    def mute() -> str:
        interface = self._get_interface()
        if not interface:
            return "Volume control interface unavailable."
        interface.SetMute(1, None)
        return "System volume muted."

    @profile
    def unmute(self) -> str:
        interface = self._get_interface()
        if not interface:
            return "Volume control interface unavailable."
        interface.SetMute(0, None)
        return "System volume unmuted."

volume_controller = VolumeController()
