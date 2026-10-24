from app.domain.config_loader import load_formats, load_templates
from app.domain.render_input import AssetInfo, build_render_input, referenced_asset_ids
from app.schema import BrandKitData, PostDocument

TEMPLATE = next(t for t in load_templates() if t.key == "project_announcement")
BRAND = BrandKitData.model_validate(
    {
        "colors": {
            "primary": "#000000",
            "secondary": "#111111",
            "accent": "#222222",
            "textOnDark": "#ffffff",
            "textOnLight": "#000000",
        },
        "fonts": {
            "heading": {"family": "A", "files": [{"assetId": "font-a"}]},
            "body": {"family": "B"},
        },
        "logos": {"logoLight": "logo-1"},
    }
)


def test_referenced_assets_include_content_overrides_logos_and_fonts() -> None:
    document = PostDocument.model_validate(
        {
            "content": {"background_image": "photo-1", "headline": "x"},
            "overrides": {"photo": {"assetId": "photo-2"}},
        }
    )
    assert referenced_asset_ids(TEMPLATE, BRAND, document) == {
        "photo-1",
        "photo-2",
        "logo-1",
        "font-a",
    }


def test_render_input_serializes_camel_case_for_typescript() -> None:
    fmt = load_formats().get("instagram/story")
    asset = AssetInfo("photo-1", "companies/b/assets/photo-1.jpg", "image/jpeg", 4000, 2250)
    result = build_render_input(
        fmt,
        TEMPLATE,
        BRAND,
        PostDocument(),
        [asset],
        lambda a: f"http://render/storage/{a.storage_key}",
    )
    data = result.model_dump(by_alias=True)
    assert data["format"]["safeZone"]["bottom"] == 672
    assert (
        data["assets"]["photo-1"]["src"] == "http://render/storage/companies/b/assets/photo-1.jpg"
    )
    assert data["brand"]["colors"]["textOnDark"] == "#ffffff"
