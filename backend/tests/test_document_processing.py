from PIL import Image

from app.services.documents import _extract_pages, _has_searchable_text, _local_embedding, _split_chunks


def test_image_ocr_uses_block_segmentation(monkeypatch, tmp_path):
    image_path = tmp_path / "scan.png"
    Image.new("RGB", (100, 100), "white").save(image_path)
    observed = {}

    def fake_ocr(image, config):
        observed["config"] = config
        return "Recognized document text"

    monkeypatch.setattr("app.services.documents.pytesseract.image_to_string", fake_ocr)

    assert _extract_pages(image_path, "image/png") == ["Recognized document text"]
    assert observed["config"] == "--psm 6"


def test_ocr_noise_is_not_searchable_text():
    assert not _has_searchable_text("> a>, co FS ~ = i-4 | s a")
    assert _has_searchable_text("Contract renewal 2027")


def test_local_embedding_is_normalized_and_deterministic():
    first = _local_embedding("Contract renewal date and pricing")
    second = _local_embedding("Contract renewal date and pricing")

    assert len(first) == 1536
    assert first == second
    assert abs(sum(value * value for value in first) - 1.0) < 1e-9


def test_chunking_preserves_content_and_bounds_chunk_size():
    paragraphs = [f"Section {index}: " + ("useful evidence " * 70) for index in range(9)]
    chunks = _split_chunks("\n\n".join(paragraphs), target_chars=800, overlap_chars=120)

    assert len(chunks) > 1
    assert all(len(chunk) <= 1200 for chunk in chunks)
    assert all(paragraph.split(":")[0] in "\n".join(chunks) for paragraph in paragraphs)


def test_empty_page_produces_no_chunks():
    assert _split_chunks("\n  \n") == []
