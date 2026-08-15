from types import SimpleNamespace

from PyQt6.QtCore import QSettings

from app.player import MPVPlayer


def test_resume_disabled_does_not_create_watch_later_directory(monkeypatch, tmp_path):
    monkeypatch.setenv("APPDATA", str(tmp_path))
    captured = {}

    class FakeMPV:
        def __init__(self, **config):
            captured.update(config)

        def __setattr__(self, name, value):
            object.__setattr__(self, name, value)

        def observe_property(self, *args):
            pass

    monkeypatch.setattr("app.player.mpv.MPV", FakeMPV)
    monkeypatch.setattr(MPVPlayer, "restore_subtitle_settings", lambda self: None)
    monkeypatch.setattr(MPVPlayer, "refresh_audio_devices", lambda self: None)

    player = MPVPlayer.__new__(MPVPlayer)
    # `init_mpv_player()` artık altyazı parçası gözlemcisini de bağlar
    # (güvenli bant HANGİ yoldan parça değişirse değişsin uygulanır);
    # vekil bu sözleşmeyi karşılar.
    player.video_frame = SimpleNamespace(
        winId=lambda: 1, sync_subtitle_safe_band=lambda: None)
    MPVPlayer.init_mpv_player(player)

    assert "watch_later_directory" not in captured
    assert not (tmp_path / "MLC Player" / "watch_later").exists()


def test_resume_disabled_does_not_write_watch_later_config():
    commands = []

    class FakeMPV:
        def command(self, *args):
            commands.append(args)

        def terminate(self):
            commands.append(("terminate",))

    player = MPVPlayer.__new__(MPVPlayer)
    player.settings = QSettings()
    player.volume_slider = SimpleNamespace(value=lambda: 70)
    player.last_dir = ""
    player.timer = SimpleNamespace(stop=lambda: None)
    player.video_frame = SimpleNamespace(is_video_fullscreen=False)
    player.current_file = "video.mkv"
    player.duration = 100
    player.position = 20
    player.mpv_player = FakeMPV()
    player.saveGeometry = lambda: b"geometry"

    event = SimpleNamespace(accept=lambda: None)
    MPVPlayer.closeEvent(player, event)

    assert ("write-watch-later-config",) not in commands
    assert ("terminate",) in commands


def test_resume_setting_is_disabled_in_configuration():
    from app.config import MPV_CONFIG

    assert MPV_CONFIG.get("resume_playback") == "no"
    assert MPV_CONFIG.get("save_position_on_quit") == "no"
