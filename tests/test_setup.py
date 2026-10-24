import json
from pathlib import Path

from ads_optimizer.credentials import customer_id_configured, resolve_ads_config
from ads_optimizer.envfile import read_env, upsert_env
from ads_optimizer.setup_wizard import fields_to_env, mask_secret, save_setup, setup_status


def test_upsert_env_keeps_other_keys(tmp_path: Path) -> None:
    path = tmp_path / ".env"
    path.write_text("FOO=bar\nGOOGLE_ADS_CUSTOMER_ID=1111111111\n", encoding="utf-8")
    upsert_env({"GOOGLE_ADS_DEVELOPER_TOKEN": "tok_123"}, path=path)
    data = read_env(path)
    assert data["FOO"] == "bar"
    assert data["GOOGLE_ADS_CUSTOMER_ID"] == "1111111111"
    assert data["GOOGLE_ADS_DEVELOPER_TOKEN"] == "tok_123"


def test_fields_to_env_skips_blank_and_formats_ids() -> None:
    updates = fields_to_env(
        {
            "developer_token": " abc ",
            "client_id": "",
            "customer_id": "123-456-7890",
            "ga4_property_id": "properties/999",
        }
    )
    assert updates["GOOGLE_ADS_DEVELOPER_TOKEN"] == "abc"
    assert "GOOGLE_ADS_CLIENT_ID" not in updates
    assert updates["GOOGLE_ADS_CUSTOMER_ID"] == "1234567890"
    assert updates["GA4_PROPERTY_ID"] == "999"


def test_save_setup_status_masks_secrets(tmp_path: Path) -> None:
    path = tmp_path / ".env"
    path.write_text("", encoding="utf-8")
    status = save_setup(
        {
            "developer_token": "devtokenvalue",
            "client_id": "1234567890-abc.apps.googleusercontent.com",
            "client_secret": "secret-value",
            "refresh_token": "1//refresh-token-value",
            "customer_id": "1112223333",
        },
        path=path,
        apply=False,
    )
    assert status["ready"] is True
    assert status["source"] == "env"
    assert status["has_refresh_token"] is True
    assert "refresh-token-value" not in status["developer_token"]
    assert "secret" not in status["client_id"].lower() or status["client_id"].startswith("1234")
    assert status["customer_id"] == "1112223333"
    assert "guide" in status and len(status["guide"]) == 3


def test_resolve_ads_config_prefers_env_over_yaml(tmp_path: Path) -> None:
    from ads_optimizer.config import Settings

    yaml_path = tmp_path / "google-ads.yaml"
    yaml_path.write_text(
        "developer_token: yaml-token\n"
        "client_id: yaml-id\n"
        "client_secret: yaml-secret\n"
        "refresh_token: yaml-refresh\n",
        encoding="utf-8",
    )
    settings = Settings(
        _env_file=None,
        google_ads_developer_token="env-token",
        google_ads_client_id="env-id",
        google_ads_client_secret="env-secret",
        google_ads_refresh_token="env-refresh",
        google_ads_configuration_file_path=yaml_path,
    )
    cfg = resolve_ads_config(settings)
    assert cfg is not None
    assert cfg["source"] == "env"
    assert cfg["developer_token"] == "env-token"


def test_resolve_ads_config_keeps_yaml_login(tmp_path: Path) -> None:
    from ads_optimizer.config import Settings

    yaml_path = tmp_path / "google-ads.yaml"
    yaml_path.write_text("login_customer_id: 9998887777\n", encoding="utf-8")
    settings = Settings(
        _env_file=None,
        google_ads_developer_token="env-token",
        google_ads_client_id="env-id",
        google_ads_client_secret="env-secret",
        google_ads_refresh_token="env-refresh",
        google_ads_login_customer_id="",
        google_ads_configuration_file_path=yaml_path,
    )
    cfg = resolve_ads_config(settings)
    assert cfg is not None
    assert cfg["source"] == "env"
    assert cfg["login_customer_id"] == "9998887777"


def test_setup_status_yaml_only_sets_has_flags(tmp_path: Path) -> None:
    env_path = tmp_path / ".env"
    env_path.write_text("", encoding="utf-8")
    yaml_path = tmp_path / "google-ads.yaml"
    yaml_path.write_text(
        "developer_token: yaml-token-value\n"
        "client_id: yaml-client-id-value\n"
        "client_secret: yaml-secret-value\n"
        "refresh_token: yaml-refresh-value\n",
        encoding="utf-8",
    )
    # Point the default yaml used when path != repo .env? status uses missing yaml
    # unless we write CONFIGURATION_FILE_PATH into the tmp env.
    env_path.write_text(
        f"GOOGLE_ADS_CONFIGURATION_FILE_PATH={yaml_path.as_posix()}\n",
        encoding="utf-8",
    )
    status = setup_status(env_path)
    assert status["ready"] is True
    assert status["source"] == "yaml"
    assert status["has_refresh_token"] is True
    assert "yaml-refresh-value" not in json.dumps(status)


def test_resolve_ads_config_yaml_fallback(tmp_path: Path) -> None:
    from ads_optimizer.config import Settings

    yaml_path = tmp_path / "google-ads.yaml"
    yaml_path.write_text(
        "developer_token: yaml-token\n"
        "client_id: yaml-id\n"
        "client_secret: yaml-secret\n"
        "refresh_token: yaml-refresh\n",
        encoding="utf-8",
    )
    settings = Settings(
        _env_file=None,
        google_ads_developer_token="",
        google_ads_client_id="",
        google_ads_client_secret="",
        google_ads_refresh_token="",
        google_ads_configuration_file_path=yaml_path,
    )
    cfg = resolve_ads_config(settings)
    assert cfg is not None
    assert cfg["source"] == "yaml"
    assert cfg["developer_token"] == "yaml-token"


def test_resolve_ads_config_rejects_placeholders(tmp_path: Path) -> None:
    from ads_optimizer.config import Settings

    settings = Settings(
        _env_file=None,
        google_ads_developer_token="INSERT_DEVELOPER_TOKEN_HERE",
        google_ads_client_id="INSERT_OAUTH2_CLIENT_ID_HERE",
        google_ads_client_secret="INSERT_OAUTH2_CLIENT_SECRET_HERE",
        google_ads_refresh_token="INSERT_REFRESH_TOKEN_HERE",
        google_ads_configuration_file_path=tmp_path / "missing.yaml",
    )
    assert resolve_ads_config(settings) is None


def test_customer_id_configured() -> None:
    assert customer_id_configured("1112223333") is True
    assert customer_id_configured("1234567890") is False
    assert customer_id_configured("") is False


def test_mask_secret() -> None:
    assert mask_secret("") == ""
    assert mask_secret("abcd") == "••••"
    assert mask_secret("abcdefghij") == "abcd…ghij"


def test_setup_status_missing_file(tmp_path: Path) -> None:
    status = setup_status(tmp_path / "nope.env")
    assert status["ready"] is False
    assert status["has_refresh_token"] is False
