from app.export_openapi import OUT, render


def test_nfr_m2_committed_openapi_schema_is_current() -> None:
    assert OUT.read_text(encoding="utf-8") == render(), (
        "web/src/api/openapi.json is out of date. Run scripts/gen-api.sh and commit."
    )
