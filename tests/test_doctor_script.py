from __future__ import annotations

import pytest
import sys
from collections import namedtuple
from scripts import doctor

FakeVersion = namedtuple("FakeVersion", ["major", "minor", "micro", "releaselevel", "serial"])


def test_doctor_main_success(monkeypatch) -> None:
    # Mock system check and imports to succeed
    fake_ver = FakeVersion(3, 11, 0, "final", 0)
    monkeypatch.setattr(sys, "version_info", fake_ver)

    # Mock validations to all return PASS
    monkeypatch.setattr(doctor, "validate_required_files", lambda root: [
        {"name": "file_check", "status": "PASS", "message": "Files OK"}
    ])
    monkeypatch.setattr(doctor, "validate_model_chains", lambda root: [
        {"name": "chain_check", "status": "PASS", "message": "Chains OK"}
    ])
    monkeypatch.setattr(doctor, "validate_env_safety", lambda: [
        {"name": "env_check", "status": "PASS", "message": "Env OK"}
    ])
    monkeypatch.setattr(doctor, "validate_runtime_setup", lambda: [
        {"name": "runtime_check", "status": "PASS", "message": "Runtime OK"}
    ])

    exit_code = doctor.main()
    assert exit_code == 0


def test_doctor_main_warnings(monkeypatch) -> None:
    fake_ver = FakeVersion(3, 11, 0, "final", 0)
    monkeypatch.setattr(sys, "version_info", fake_ver)

    # Mock validations to return WARN
    monkeypatch.setattr(doctor, "validate_required_files", lambda root: [
        {"name": "file_check", "status": "WARN", "message": "File Warn"}
    ])
    monkeypatch.setattr(doctor, "validate_model_chains", lambda root: [
        {"name": "chain_check", "status": "PASS", "message": "Chains OK"}
    ])
    monkeypatch.setattr(doctor, "validate_env_safety", lambda: [
        {"name": "env_check", "status": "PASS", "message": "Env OK"}
    ])
    monkeypatch.setattr(doctor, "validate_runtime_setup", lambda: [
        {"name": "runtime_check", "status": "PASS", "message": "Runtime OK"}
    ])

    exit_code = doctor.main()
    assert exit_code == 0


def test_doctor_main_critical_failure(monkeypatch) -> None:
    fake_ver = FakeVersion(3, 11, 0, "final", 0)
    monkeypatch.setattr(sys, "version_info", fake_ver)

    # Mock validations to return FAIL
    monkeypatch.setattr(doctor, "validate_required_files", lambda root: [
        {"name": "file_check", "status": "FAIL", "message": "File Critical Fail"}
    ])
    monkeypatch.setattr(doctor, "validate_model_chains", lambda root: [
        {"name": "chain_check", "status": "PASS", "message": "Chains OK"}
    ])
    monkeypatch.setattr(doctor, "validate_env_safety", lambda: [
        {"name": "env_check", "status": "PASS", "message": "Env OK"}
    ])
    monkeypatch.setattr(doctor, "validate_runtime_setup", lambda: [
        {"name": "runtime_check", "status": "PASS", "message": "Runtime OK"}
    ])

    exit_code = doctor.main()
    assert exit_code == 1


def test_doctor_python_version_failure(monkeypatch) -> None:
    # Python 3.10 (unsupported)
    fake_ver = FakeVersion(3, 10, 0, "final", 0)
    monkeypatch.setattr(sys, "version_info", fake_ver)

    monkeypatch.setattr(doctor, "validate_required_files", lambda root: [
        {"name": "file_check", "status": "PASS", "message": "Files OK"}
    ])
    monkeypatch.setattr(doctor, "validate_model_chains", lambda root: [
        {"name": "chain_check", "status": "PASS", "message": "Chains OK"}
    ])
    monkeypatch.setattr(doctor, "validate_env_safety", lambda: [
        {"name": "env_check", "status": "PASS", "message": "Env OK"}
    ])
    monkeypatch.setattr(doctor, "validate_runtime_setup", lambda: [
        {"name": "runtime_check", "status": "PASS", "message": "Runtime OK"}
    ])

    exit_code = doctor.main()
    assert exit_code == 1
