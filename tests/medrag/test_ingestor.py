from pathlib import Path
from types import SimpleNamespace

from src.projects.medrag.ingestor import MedRAGIngestor


class DummyDocument:
    def __init__(self, metadata):
        self.metadata = metadata


def test_enrich_metadata_maps_pubmed_documents():
    ingestor = MedRAGIngestor(config=None)  # type: ignore[arg-type]
    doc = DummyDocument({"source": "pubmed", "query": "hypertension management guideline"})

    enriched = ingestor.enrich_metadata([doc])[0]

    assert enriched.metadata["source_org"] == "PubMed"
    assert enriched.metadata["evidence_type"] == "research_abstract"
    assert enriched.metadata["specialty"] == "cardiology"


def test_enrich_metadata_maps_fda_labels():
    ingestor = MedRAGIngestor(config=None)  # type: ignore[arg-type]
    doc = DummyDocument({"source_file": "FDA_metformin_label.pdf"})

    enriched = ingestor.enrich_metadata([doc])[0]

    assert enriched.metadata["source_org"] == "FDA"
    assert enriched.metadata["evidence_type"] == "drug_label"
    assert enriched.metadata["specialty"] == "endocrinology"


def test_load_guideline_pdfs_respects_zero_limit(monkeypatch, tmp_path: Path):
    guideline_dir = tmp_path / "guidelines"
    guideline_dir.mkdir()
    (guideline_dir / "WHO_BP.pdf").write_bytes(b"fake pdf")
    monkeypatch.setenv("MAX_GUIDELINE_FILES", "0")

    ingestor = MedRAGIngestor(config=SimpleNamespace(data_dir=tmp_path))

    docs = ingestor._load_guideline_pdfs()

    assert docs == []


def test_load_and_parse_includes_bootstrap_documents(monkeypatch, tmp_path: Path):
    monkeypatch.setenv("PUBMED_ENABLED", "false")
    monkeypatch.setenv("MEDRAG_INCLUDE_BOOTSTRAP", "true")

    ingestor = MedRAGIngestor(config=SimpleNamespace(data_dir=tmp_path))

    docs = ingestor.load_and_parse()

    titles = {doc.metadata["title"] for doc in docs}
    assert "Type 2 diabetes first-line therapy overview" in titles
    assert "Why medical guidance should include a disclaimer" in titles
