from entity_exposure_map import (
    THEME_OVERLAY,
    classify_entity_themes,
    map_event_to_exposures,
    validate_theme_overlay,
)


def _overlay(listed):
    return validate_theme_overlay(THEME_OVERLAY, set(listed))


def test_overlay_structure():
    themes = {t["theme"] for t in THEME_OVERLAY}
    assert len(themes) == len(THEME_OVERLAY), "duplicate theme names"
    for entry in THEME_OVERLAY:
        assert entry["listed_peers"], entry["theme"]
        assert entry["sic_codes"] or entry["name_keywords"], entry["theme"]


def test_validate_theme_overlay_drops_unlisted():
    overlay = _overlay(["RKLB", "ASTS"])
    space = next(t for t in overlay["themes"] if t["theme"] == "space_launch_satellites")
    assert space["listed_peers"] == ["RKLB", "ASTS"]
    assert "LUNR" in overlay["dropped_unlisted_peers"]["space_launch_satellites"]


def test_classify_by_sic_and_keyword():
    overlay = _overlay(["RKLB", "NVDA", "IONQ"])
    hits = classify_entity_themes(
        "Generic Holdings Inc", "3760", "Guided Missiles & Space Vehicles",
        overlay["themes"],
    )
    assert {"theme": "space_launch_satellites", "match_basis": "sic:3760"} in hits

    hits = classify_entity_themes(
        "QuantumLeap Computing Corp", None, None, overlay["themes"]
    )
    assert any(h["theme"] == "quantum_computing" for h in hits)

    # word-boundary: 'aerospace' must not fire the ' ai ' keyword,
    # 'Space' must fire space keyword
    hits = classify_entity_themes("Aerospace Dynamics", None, None, overlay["themes"])
    assert all(h["theme"] != "ai_software_platforms" for h in hits)
    assert any(h["theme"] == "space_launch_satellites" for h in hits)


def test_map_event_to_exposures_sic_and_theme():
    overlay = _overlay(["RKLB", "ASTS", "LMT"])
    sic_index = {
        "by_sic": {
            "3760": [
                {"ticker": "LMT", "cik": "1", "name": "L", "sic_description": ""},
                {"ticker": "RKLB", "cik": "2", "name": "R", "sic_description": ""},
            ]
        }
    }
    event = {
        "accession": "a-1",
        "event_class": "ipo_registration",
        "filed_date": "2026-07-01",
        "cik": "0002222222",
        "company_name": "SpaceLaunch Holdings Inc",
    }
    entity = {
        "name": "SpaceLaunch Holdings Inc",
        "sic": "3760",
        "sic_description": "Guided Missiles & Space Vehicles & Parts",
        "is_blank_check": False,
    }
    exposures = map_event_to_exposures(event, entity, sic_index, overlay)
    kinds = {(e["ticker"], e["relation_type"]) for e in exposures}
    assert ("LMT", "sic_peer") in kinds
    assert ("RKLB", "sic_peer") in kinds
    assert ("ASTS", "theme_peer") in kinds
    assert all(e["overlay_version"] == overlay["overlay_version"] for e in exposures)
    # no direction fields anywhere
    assert all("direction" not in e for e in exposures)


def test_blank_check_entities_produce_no_exposures():
    overlay = _overlay(["RKLB"])
    entity = {
        "name": "Arogo Capital Acquisition Corp",
        "sic": "6770",
        "sic_description": "Blank Checks",
        "is_blank_check": True,
    }
    event = {"accession": "a-2", "event_class": "ipo_registration", "cik": "1"}
    assert map_event_to_exposures(event, entity, {"by_sic": {}}, overlay) == []


def test_unknown_entity_falls_back_to_event_name():
    overlay = _overlay(["IONQ", "RGTI"])
    event = {
        "accession": "a-3",
        "event_class": "ipo_registration",
        "filed_date": "2026-07-01",
        "cik": "0009999999",
        "company_name": "Quantum Gate Systems Inc",
    }
    exposures = map_event_to_exposures(event, None, {"by_sic": {}}, overlay)
    assert {e["ticker"] for e in exposures} == {"IONQ", "RGTI"}
    assert all(e["relation_type"] == "theme_peer" for e in exposures)
