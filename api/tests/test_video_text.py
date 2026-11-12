"""Every video segment teaches in text too (#149, FR-3.2, WCAG 1.2): its body is the narration,
shown as the lesson while no video is attached and as the text version below one that is. The
videos aren't recorded yet, so modules 1 and 3 must teach their ideas in text before the
activities that need them."""

from app.seed import FixtureFile, SegmentFixture, read_fixtures

CONTENT: FixtureFile = read_fixtures()
VIDEOS = [s for m in CONTENT.modules for s in m.segments if s.kind == "video"]


def segments_before(segment_id: int) -> list[SegmentFixture]:
    for m in CONTENT.modules:
        ids = [s.id for s in m.segments]
        if segment_id in ids:
            return m.segments[: ids.index(segment_id)]
    raise AssertionError(f"no segment {segment_id}")


def text_before(segment_id: int) -> str:
    return "\n".join(s.body.lower() for s in segments_before(segment_id))


def test_there_are_video_segments() -> None:
    assert len(VIDEOS) >= 6


def test_every_video_segment_has_its_narration_as_text() -> None:
    for s in VIDEOS:
        assert s.body.strip(), s.id
        assert "staff attach" not in s.body.lower(), f"segment {s.id} still points to the script"
        assert "narration-script" not in s.body, s.id
        assert len(s.body.split()) >= 150, f"segment {s.id} is too short to stand in for a video"
        for direction in ("[slide]", "checkpoint", "on screen"):
            assert direction not in s.body.lower(), (s.id, direction)


def test_module_1_defines_its_key_terms_before_the_key_terms_activity() -> None:
    # Segment 104 asks for the key terms (activity 102).
    taught = text_before(104)
    for term in ("**graph**", "**vertex**", "**edge**", "**data structure**", "**algorithm**"):
        assert term in taught, term
    assert "**graph traversal**" in taught


def test_module_1_teaches_directed_graphs_before_the_activity_on_them() -> None:
    # Segment 109 asks "Directed or undirected?" (activity 106).
    taught = text_before(109)
    assert "**directed**" in taught
    assert "**undirected**" in taught


def test_module_3_teaches_the_queue_and_found_rules_before_students_predict_bfs() -> None:
    # Segment 316 has students predict each BFS step in the visualiser.
    taught = text_before(316)
    assert "**breadth-first search**" in taught
    assert "**queue**" in taught
    assert "first in, first out" in taught
    assert "front of the queue" in taught
    assert "back of the queue" in taught
    assert "**found** when it joins the queue" in taught
    assert "**visited** when it leaves the queue" in taught
    assert "alphabetical order" in taught
    assert "a, c, e, b, f, d, g" in taught
