from app.tools.factory import build_tool_registry


def test_registry_has_ten_service_desk_tools() -> None:
    class _Retriever:
        pass

    registry = build_tool_registry(_Retriever())  # type: ignore[arg-type]
    assert len(registry.names()) == 10
    assert "get_ticket" in registry.names()
    assert "request_access" in registry.names()
    assert "escalate_to_human" in registry.names()
