import pandas as pd
from aTrain_core.backends.common import words_to_segments
from aTrain_core.backends.crisper_transformers import group_word_segments
from aTrain_core.outputs import assign_word_speakers


def diarization(*rows):
    return pd.DataFrame(rows, columns=["start", "end", "speaker"])


def test_word_crossing_boundary_uses_speaker_at_word_start():
    result = {"segments": [{"start": 0.0, "end": 1.2, "words": [{"start": 0.9, "end": 1.2}]}]}

    assign_word_speakers(diarization((0.0, 1.0, "A"), (0.95, 2.0, "B")), result)

    assert result["segments"][0]["words"][0]["speaker"] == "A"
    assert result["segments"][0]["speaker"] == "A"


def test_word_starting_after_boundary_uses_new_speaker():
    result = {"segments": [{"start": 0.0, "end": 1.2, "words": [{"start": 1.01, "end": 1.2}]}]}

    assign_word_speakers(diarization((0.0, 1.0, "A"), (0.95, 2.0, "B")), result)

    assert result["segments"][0]["words"][0]["speaker"] == "B"


def test_overlapping_tracks_have_stable_tie_breaking():
    result = {"segments": [{"start": 0.0, "end": 1.0, "words": [{"start": 0.5, "end": 0.6}]}]}

    assign_word_speakers(diarization((0.0, 1.0, "A"), (0.0, 1.0, "B")), result)

    assert result["segments"][0]["words"][0]["speaker"] == "A"


def test_segment_speaker_comes_from_word_labels():
    result = {
        "segments": [
            {
                "start": 0.0,
                "end": 2.0,
                "words": [{"start": 0.0, "end": 0.4}, {"start": 0.5, "end": 1.9}],
            }
        ]
    }

    assign_word_speakers(diarization((0.0, 0.4, "A"), (0.4, 2.0, "B")), result)

    assert result["segments"][0]["speaker"] == "B"


def test_segment_without_labeled_words_uses_overlap_majority():
    result = {"segments": [{"start": 0.0, "end": 2.0, "words": [{"text": "un-timestamped"}]}]}

    assign_word_speakers(diarization((0.0, 0.1, "A"), (0.1, 2.0, "B")), result)

    assert result["segments"][0]["speaker"] == "B"


def test_empty_diarization_leaves_segment_and_word_unlabeled():
    result = {
        "segments": [
            {
                "start": 0.0,
                "end": 1.0,
                "words": [{"start": 0.1, "end": 0.2}],
            }
        ]
    }

    assign_word_speakers(diarization(), result, fill_nearest=True)

    assert "speaker" not in result["segments"][0]
    assert "speaker" not in result["segments"][0]["words"][0]


def test_one_word_segment_speaker_follows_word_onset():
    result = {"segments": [{"start": 0.9, "end": 1.2, "words": [{"start": 0.9, "end": 1.2}]}]}

    assign_word_speakers(diarization((0.0, 1.0, "A"), (0.95, 2.0, "B")), result)

    assert result["segments"][0]["speaker"] == "A"


def cues(*words):
    """Group (text, start, end[, speaker]) tuples like the transcription pipeline."""
    segments = words_to_segments({"word": w[0], "start": w[1], "end": w[2]} for w in words)
    for segment, w in zip(segments, words, strict=True):
        if len(w) == 4:
            segment["speaker"] = w[3]
    return [(c["text"], c["start"], c["end"]) for c in group_word_segments(segments)]


def test_cue_ends_at_sentence_boundary():
    result = cues((" This", 0.0, 1.0), (" is", 1.0, 2.0), (" long.", 2.0, 3.5), (" Next", 3.6, 4.0))

    assert result == [("This is long.", 0.0, 3.5), ("Next", 3.6, 4.0)]


def test_short_sentences_share_a_cue():
    result = cues((" Yes.", 0.0, 0.5), (" Okay.", 0.6, 1.0), (" Go", 1.1, 1.5))

    assert result == [("Yes. Okay. Go", 0.0, 1.5)]


def test_long_pause_starts_new_cue():
    result = cues((" wait", 0.0, 0.5), (" here", 2.5, 3.0))

    assert result == [("wait", 0.0, 0.5), ("here", 2.5, 3.0)]


def test_short_pause_inside_sentence_keeps_cue():
    result = cues((" wait", 0.0, 0.5), (" here", 1.5, 2.0))

    assert result == [("wait here", 0.0, 2.0)]


def test_unpunctuated_speech_is_capped():
    words = [(" w", float(i), float(i) + 0.9) for i in range(25)]

    result = cues(*words)

    assert [c[1] for c in result] == [0.0, 20.0]


def test_speaker_change_starts_new_cue():
    result = cues((" Right?", 0.0, 0.5, "A"), (" Yes", 0.6, 1.0, "B"))

    assert result == [("Right?", 0.0, 0.5), ("Yes", 0.6, 1.0)]
