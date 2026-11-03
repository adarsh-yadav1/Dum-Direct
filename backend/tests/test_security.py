from argon2 import PasswordHasher

from app.core.security import hash_password, needs_rehash, verify_password


def test_correct_password_verifies():
    assert verify_password("a long demo passphrase", hash_password("a long demo passphrase"))


def test_wrong_password_is_rejected():
    assert not verify_password("wrong", hash_password("right"))


def test_same_password_hashes_differently_each_time():
    assert hash_password("same") != hash_password("same")


def test_hash_does_not_contain_the_password():
    assert "plain-secret" not in hash_password("plain-secret")


def test_malformed_hash_is_a_failure_not_an_exception():
    assert verify_password("anything", "not-a-hash") is False
    assert verify_password("anything", "") is False


def test_fresh_hash_does_not_need_rehashing_but_a_weak_one_does():
    assert not needs_rehash(hash_password("x"))
    weak = PasswordHasher(time_cost=1, memory_cost=8, parallelism=1).hash("x")
    assert needs_rehash(weak)
