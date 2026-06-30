from app.services.document_parser import ParsedSection
from app.services.text_splitter import SemanticTextSplitter


def test_splitter_preserves_metadata_and_limits_size():
    section = ParsedSection("第一段。" * 80 + "\n\n" + "第二段。" * 80, page=3, section_title="测试章节")
    chunks = SemanticTextSplitter(chunk_size=200, chunk_overlap=30).split([section])
    assert len(chunks) > 1
    assert all(chunk.page == 3 and chunk.section_title == "测试章节" for chunk in chunks)
    assert all(len(chunk.content) <= 200 for chunk in chunks)


def test_splitter_rejects_invalid_overlap():
    try:
        SemanticTextSplitter(chunk_size=100, chunk_overlap=100)
        assert False, "expected ValueError"
    except ValueError:
        pass
