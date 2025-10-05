"""Unit tests for zakupai_common.compliance module"""

from libs.zakupai_common.zakupai_common.compliance import ComplianceSettings


def test_reestr_nedobro_enabled():
    """Test that reestr neddbrosovesny is enabled"""
    assert ComplianceSettings.REESTR_NEDOBRO_ENABLED is True, "Reestr should be enabled"


def test_single_source_list_contains_bank_deposits():
    """Test that bank deposits are in single source list"""
    assert "bank_deposits" in ComplianceSettings.SINGLE_SOURCE_LIST, (
        "Bank deposits should be in single source list"
    )


def test_single_source_list_contains_credit_ratings():
    """Test that credit ratings are in single source list"""
    assert "credit_ratings" in ComplianceSettings.SINGLE_SOURCE_LIST, (
        "Credit ratings should be in single source list"
    )


def test_single_source_list_contains_scientific_research():
    """Test that scientific research is in single source list"""
    assert "scientific_research" in ComplianceSettings.SINGLE_SOURCE_LIST, (
        "Scientific research should be in single source list"
    )


def test_single_source_list_contains_national_bank_services():
    """Test that national bank services are in single source list"""
    assert "national_bank_services" in ComplianceSettings.SINGLE_SOURCE_LIST, (
        "National bank services should be in single source list"
    )


def test_anti_dumping_threshold():
    """Test anti-dumping threshold value"""
    assert ComplianceSettings.ANTI_DEMPING_THRESHOLD == 0.15, (
        "Antidumping threshold should be 0.15"
    )


def test_complaint_deadline_days():
    """Test complaint deadline days value"""
    assert ComplianceSettings.COMPLAINT_DEADLINE_DAYS == 3, (
        "Complaint deadline should be 3 days"
    )


def test_excluded_procurements_contains_military_goods():
    """Test that military goods are excluded from procurement"""
    assert "military_goods" in ComplianceSettings.EXCLUDED_PROCUREMENTS, (
        "Military goods should be excluded"
    )


def test_excluded_procurements_contains_labor_contracts():
    """Test that labor contracts are excluded from procurement"""
    assert "labor_contracts" in ComplianceSettings.EXCLUDED_PROCUREMENTS, (
        "Labor contracts should be excluded"
    )


def test_excluded_procurements_contains_international_projects():
    """Test that international projects are excluded from procurement"""
    assert "international_projects" in ComplianceSettings.EXCLUDED_PROCUREMENTS, (
        "International projects should be excluded"
    )


def test_affil_check_enabled():
    """Test that affiliation check is enabled"""
    assert ComplianceSettings.AFFIL_CHECK_ENABLED is True, (
        "Affiliation check should be enabled"
    )


def test_single_source_enabled():
    """Test that single source procurement is enabled"""
    assert ComplianceSettings.SINGLE_SOURCE_ENABLED is True, (
        "Single source should be enabled"
    )


def test_affil_ban_in_single_source():
    """Test that affiliation is banned in single source procurement"""
    assert ComplianceSettings.AFFIL_BAN_IN_SINGLE_SOURCE is True, (
        "Affiliation should be banned in single source"
    )


def test_rating_agency_threshold():
    """Test rating agency threshold value"""
    assert ComplianceSettings.RATING_AGENCY_THRESHOLD == "A-", (
        "Rating agency threshold should be A-"
    )


def test_cancel_procedure_days():
    """Test cancel procedure notification days"""
    assert ComplianceSettings.CANCEL_PROCEDURE_DAYS == 5, (
        "Cancel procedure should require 5 days notification"
    )


def test_turnkey_contest_enabled():
    """Test that turnkey contests are enabled"""
    assert ComplianceSettings.TURNKEY_CONTEST_ENABLED is True, (
        "Turnkey contests should be enabled"
    )
