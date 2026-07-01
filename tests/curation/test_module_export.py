"""Tests for slim curated_content.json export."""

from ibrary.curation.schemas import CuratedModule, module_for_json_export


def test_export_omits_empty_enrichment_and_placeholders():
    m = CuratedModule(
        curriculum_unit_id="bio_sss1_theme1_topic1_content0",
        class_name="SSS 1",
        theme="T",
        theme_number=1,
        topic_number=1,
        subtopic="Sub",
        title="Title",
        curated_content="## Hello\n\nWorld.",
        image_placeholders=[{"placeholder_id": "ph1", "intent": "diagram"}],
        formula_placeholders=[],
    )
    d = module_for_json_export(m)
    assert "image_placeholders" not in d
    assert "formula_placeholders" not in d
    assert "content_blocks" not in d
    assert "images" not in d
    assert "formulas" not in d
    assert "assets" not in d
    assert d["curated_content"].startswith("## Hello")
    assert "textbook_grounded" not in d


def test_export_includes_images_when_present():
    from ibrary.curation.schemas import ImageRef

    m = CuratedModule(
        curriculum_unit_id="x",
        class_name="SSS 1",
        theme="T",
        theme_number=1,
        topic_number=1,
        subtopic="Sub",
        title="Title",
        curated_content="text",
        images=[
            ImageRef(image_id="img1", s3_url="s3://b/k.png", caption="c", alt_text="a")
        ],
    )
    d = module_for_json_export(m)
    assert len(d["images"]) == 1
