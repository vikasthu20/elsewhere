from app.services.operations import document_is_allowed, money, hash_otp, verify_otp

def test_money_uses_two_decimal_places():
    assert str(money("10.235")) == "10.24"

def test_document_allowlist():
    assert document_is_allowed("license.pdf", "application/pdf", 1024)
    assert not document_is_allowed("license.exe", "application/pdf", 1024)
    assert not document_is_allowed("license.pdf", "application/pdf", 20 * 1024 * 1024)

def test_otp_hash_is_verifiable_and_not_plaintext():
    digest = hash_otp("123456", "test-secret")
    assert digest != "123456"
    assert verify_otp("123456", digest, "test-secret")
    assert not verify_otp("000000", digest, "test-secret")
