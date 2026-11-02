from app.core.constants import PII_MASK
from app.core.security import mask_pii, redact_mapping


def test_mask_phone_id_bank_and_ticket() -> None:
    text = "联系 13812345678 身份证 11010119900307123X 卡号 6222021234567890 工单 TKT1234567"
    masked = mask_pii(text)
    assert "13812345678" not in masked
    assert f"138{PII_MASK}5678" in masked
    assert "11010119900307123X" not in masked
    assert "6222021234567890" not in masked
    assert "TKT1234567" not in masked
    assert f"TKT{PII_MASK}67" in masked


def test_redact_mapping_masks_secrets_and_nested_strings() -> None:
    payload = {
        "api_key": "sk-live-secret",
        "note": "电话 13900001111",
        "nested": {"password": "hunter2", "ticket": "TKT1234567"},
        "count": 3,
    }
    redacted = redact_mapping(payload)
    assert redacted["api_key"] == PII_MASK
    assert "13900001111" not in str(redacted["note"])
    nested = redacted["nested"]
    assert isinstance(nested, dict)
    assert nested["password"] == PII_MASK
    assert "TKT1234567" not in str(nested["ticket"])
    assert redacted["count"] == 3
