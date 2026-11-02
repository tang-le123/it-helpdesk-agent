from pathlib import Path

from app.core.enums import DocumentCategory
from app.retrieval.chunking import document_id_from_path
from app.retrieval.ingest import category_for_stem
from app.retrieval.unstructured_parser import list_knowledge_files


def test_knowledge_dir_has_enterprise_scale_corpus() -> None:
    files = list_knowledge_files(Path("knowledge"))
    assert len(files) >= 30
    assert {path.suffix.lower() for path in files} <= {
        ".md",
        ".pdf",
        ".docx",
        ".pptx",
        ".html",
        ".htm",
        ".png",
        ".jpg",
        ".jpeg",
        ".webp",
        ".tiff",
        ".tif",
    }


def test_category_prefix_maps_it_service_desk_domains() -> None:
    assert category_for_stem("account_lifecycle") == DocumentCategory.ACCOUNT
    assert category_for_stem("password_reset") == DocumentCategory.ACCOUNT
    assert category_for_stem("vpn_access") == DocumentCategory.NETWORK
    assert category_for_stem("wifi_access") == DocumentCategory.NETWORK
    assert category_for_stem("device_repair") == DocumentCategory.DEVICE
    assert category_for_stem("asset_query") == DocumentCategory.DEVICE
    assert category_for_stem("software_install") == DocumentCategory.SOFTWARE
    assert category_for_stem("license_request") == DocumentCategory.SOFTWARE
    assert category_for_stem("app_ai_tools") == DocumentCategory.SOFTWARE
    assert category_for_stem("data_classification") == DocumentCategory.SECURITY
    assert category_for_stem("meeting_room") == DocumentCategory.PROCESS
    assert category_for_stem("unknown_topic") == DocumentCategory.FAQ


def test_document_id_is_independent_of_checkout_location(tmp_path: Path) -> None:
    first = tmp_path / "checkout-a" / "knowledge"
    second = tmp_path / "checkout-b" / "knowledge"
    first.mkdir(parents=True)
    second.mkdir(parents=True)
    assert document_id_from_path(first / "vpn_access.md", root=first) == document_id_from_path(
        second / "vpn_access.md", root=second
    )
