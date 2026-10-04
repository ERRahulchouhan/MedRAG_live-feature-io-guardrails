from src.core.projects import get_project_definition


def test_get_project_definition_returns_medrag():
    definition = get_project_definition("medrag")

    assert definition.config.name == "medrag"
    assert definition.config.collection_name == "medrag_collection_bge_small"
