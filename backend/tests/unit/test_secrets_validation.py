from app.core.config import Settings


def _prod_settings(**overrides) -> Settings:
    base = dict(
        environment="production",
        jwt_secret="a-very-long-and-random-production-secret-42",
        encryption_key="x" * 44,
        redis_password="strong-redis-password",
        partner_webhook_secret="a-very-long-webhook-secret-for-partners",
        telegram_bot_token="1:token",
        allow_mock_partners=False,
        allow_sandbox_partners=False,
        debug=False,
        cookie_secure=True,
        cookie_samesite="none",
        _env_file=None,
    )
    base.update(overrides)
    return Settings(**base)


def test_valid_production_config_passes():
    assert _prod_settings().validate_for_production() == []


def test_default_jwt_secret_blocks_production():
    problems = _prod_settings(jwt_secret="insecure-dev-secret").validate_for_production()
    assert any("JWT_SECRET" in p for p in problems)


def test_short_jwt_secret_blocks_production():
    problems = _prod_settings(jwt_secret="short").validate_for_production()
    assert any("JWT_SECRET" in p for p in problems)


def test_missing_encryption_key_blocks_production():
    problems = _prod_settings(encryption_key="").validate_for_production()
    assert any("ENCRYPTION_KEY" in p for p in problems)


def test_missing_redis_password_blocks_production():
    problems = _prod_settings(redis_password="").validate_for_production()
    assert any("REDIS_PASSWORD" in p for p in problems)


def test_missing_webhook_secret_blocks_production():
    problems = _prod_settings(partner_webhook_secret="").validate_for_production()
    assert any("WEBHOOK_SECRET" in p for p in problems)


def test_mock_partners_block_production():
    problems = _prod_settings(allow_mock_partners=True).validate_for_production()
    assert any("MOCK" in p for p in problems)


def test_sandbox_partners_block_production():
    problems = _prod_settings(allow_sandbox_partners=True).validate_for_production()
    assert any("SANDBOX" in p for p in problems)


def test_insecure_cookie_blocks_production():
    problems = _prod_settings(cookie_secure=False).validate_for_production()
    assert any("COOKIE_SECURE" in p for p in problems)


def test_invalid_samesite_blocks_production():
    problems = _prod_settings(cookie_samesite="bogus").validate_for_production()
    assert any("COOKIE_SAMESITE" in p for p in problems)


def test_dev_environment_not_blocked():
    settings = Settings(environment="development", _env_file=None)
    assert settings.validate_for_production() == []
