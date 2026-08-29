from app.services.rag import ParsedPage, split_pages


def test_chunking_preserves_page_and_overlap():
    chunks = split_pages([ParsedPage(3, "word " * 500)], size=200, overlap=20)
    assert len(chunks) > 2
    assert all(chunk.number == 3 for chunk in chunks)
    assert all(chunk.text for chunk in chunks)
