import pytest

from broadcast_controller.audio.music_manager import MusicManager

@pytest.fixture
def manager_config():
    return {
        "audio": {
            "audio": {
                "music": {
                    "directory": "media/music",
                    "player": "ffmpeg",
                    "extensions": [
                        ".mp3",
                        ".wav",
                        ".ogg",
                        ".flac",
                    ],
                    "repeat_playlist": True,
                    "track_order": "alphabetical",
                }
            }
        }
    }

def test_playlist_is_alphabetical(tmp_path, manager_config):
    manager = MusicManager(
        manager_config,
        "meetinghouse_broadcast",
        tmp_path
    )

    playlist_dir = tmp_path / "media/music/opening"
    playlist_dir.mkdir(parents=True)

    (playlist_dir / "03-third.wav").touch()
    (playlist_dir / "01-first.wav").touch()
    (playlist_dir / "02-second.wav").touch()

    playlist = manager.get_playlist("opening")

    assert [track.name for track in playlist] == [
        "01-first.wav",
        "02-second.wav",
        "03-third.wav",
    ]

def test_empty_playlist_raises_error(tmp_path, manager_config):
    playlist = tmp_path / "media/music/opening"
    playlist.mkdir(parents=True)

    manager = MusicManager(
        manager_config,
        "meetinghouse_broadcast",
        tmp_path,
    )

    with pytest.raises(RuntimeError):
        manager.get_playlist("opening")

def test_path_traversal_is_rejected(tmp_path, manager_config):
    manager = MusicManager(
        manager_config,
        "meetinghouse_broadcast",
        tmp_path,
    )

    with pytest.raises(ValueError):
        manager.get_playlist("../../outside")

def test_ffmpeg_command_targets_virtual_sink(tmp_path, manager_config):
    manager = MusicManager(
        manager_config,
        "meetinghouse_broadcast",
        tmp_path,
    )

    track = tmp_path / "test.mp3"

    command = manager._build_command(track)

    assert command[0] == "ffmpeg"
    assert "-re" in command
    assert "-i" in command
    assert str(track) in command
    assert "-f" in command
    assert command[command.index("-f") + 1] == "pulse"
    assert "-device" in command
    assert command[command.index("-device") + 1] == "meetinghouse_broadcast"

def test_shuffled_playlist_plays_every_track_once(tmp_path, manager_config, monkeypatch):
    manager = MusicManager(manager_config, "meetinghouse_broadcast", tmp_path)

    tracks = [
        tmp_path / "a.mp3",
        tmp_path / "b.mp3",
        tmp_path / "c.mp3",
        tmp_path / "d.mp3",
    ]

    played = []

    monkeypatch.setattr(
        "broadcast_controller.audio.music_manager.random.shuffle",
        lambda items: items.reverse(),
    )

    monkeypatch.setattr(
        manager,
        "_play_track",
        lambda track: played.append(track) or True,
    )

    manager.current_playlist = "prelude_postlude"
    manager._play_playlist(tracks)

    assert len(played) == len(tracks)
    assert set(played) == set(tracks)
    assert len(played) == len(set(played))

def test_playlist_does_not_repeat_after_completion(tmp_path, manager_config, monkeypatch):
    manager = MusicManager(manager_config, "meetinghouse_broadcast", tmp_path)

    tracks = [
        tmp_path / "a.mp3",
        tmp_path / "b.mp3",
    ]

    played = []

    monkeypatch.setattr(
        "broadcast_controller.audio.music_manager.random.shuffle",
        lambda items: None,
    )

    monkeypatch.setattr(
        manager,
        "_play_track",
        lambda track: played.append(track) or True,
    )

    manager.current_playlist = "prelude_postlude"
    manager._play_playlist(tracks)

    assert played == tracks
    assert len(played) == 2

def test_stopping_playlist_prevents_next_track(tmp_path, manager_config, monkeypatch):
    manager = MusicManager(manager_config, "meetinghouse_broadcast", tmp_path)

    tracks = [
        tmp_path / "a.mp3",
        tmp_path / "b.mp3",
        tmp_path / "c.mp3"
    ]

    played = []

    monkeypatch.setattr(
        "broadcast_controller.audio.music_manager.random.shuffle",
        lambda items: None,
    )

    def fake_play_track(track):
        played.append(track)
        manager.stop_event.set()
        return True

    monkeypatch.setattr(manager, "_play_track", fake_play_track)

    manager.current_playlist = "prelude_postlude"
    manager._play_playlist(tracks)

    assert played == [tracks[0]]

def test_restarting_playlist_shuffles_again(tmp_path, manager_config, monkeypatch):
    manager = MusicManager(manager_config, "meetinghouse_broadcast", tmp_path)

    tracks = [
        tmp_path / "a.mp3",
        tmp_path / "b.mp3",
        tmp_path / "c.mp3"
    ]

    played = []
    shuffle_calls = []

    def fake_shuffle(items):
        shuffle_calls.append(True)

        if len(shuffle_calls) == 1:
            items.reverse()

    monkeypatch.setattr(
        "broadcast_controller.audio.music_manager.random.shuffle",
        fake_shuffle
    )

    monkeypatch.setattr(
        manager,
        "_play_track",
        lambda track: played. append(track) or True
    )

    manager.current_playlist = "prelude_postlude"
    
    manager._play_playlist(tracks)
    first_run = played.copy()

    played.clear()

    manager._play_playlist(tracks)
    second_run = played.copy()
    
    assert len(shuffle_calls) == 2
    assert first_run != second_run
    assert set(first_run) == set(tracks)
    assert set(second_run) == set(tracks)
