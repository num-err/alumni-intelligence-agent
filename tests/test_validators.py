import datetime

from app.services.validators import (
    validate_confidence,
    validate_email,
    validate_graduation_year,
    validate_linkedin,
    validate_location,
)


def test_linkedin_accepts_url_containing_linkedin_com():
    result = validate_linkedin("https://www.linkedin.com/in/janedoe")
    assert result.value == "https://www.linkedin.com/in/janedoe"
    assert result.rejected is False


def test_linkedin_rejects_non_linkedin_url():
    result = validate_linkedin("https://facebook.com/janedoe")
    assert result.value is None
    assert result.rejected is True


def test_linkedin_accepts_none():
    result = validate_linkedin(None)
    assert result.value is None
    assert result.rejected is False


def test_email_accepts_valid_address():
    result = validate_email("jane@example.com")
    assert result.value == "jane@example.com"
    assert result.rejected is False


def test_email_rejects_malformed_address():
    result = validate_email("not-an-email")
    assert result.value is None
    assert result.rejected is True


def test_graduation_year_accepts_reasonable_year():
    result = validate_graduation_year("2020")
    assert result.value == "2020"
    assert result.rejected is False


def test_graduation_year_rejects_non_numeric():
    result = validate_graduation_year("class of 2020")
    assert result.rejected is True


def test_graduation_year_rejects_out_of_range():
    result = validate_graduation_year("1500")
    assert result.rejected is True


def test_graduation_year_rejects_far_future():
    future_year = str(datetime.datetime.now().year + 50)
    result = validate_graduation_year(future_year)
    assert result.rejected is True


def test_location_accepts_reasonable_text():
    result = validate_location("New York, NY")
    assert result.value == "New York, NY"
    assert result.rejected is False


def test_location_rejects_numeric_garbage():
    result = validate_location("12345")
    assert result.rejected is True


def test_location_rejects_overly_long_text():
    result = validate_location("A" * 200)
    assert result.rejected is True


def test_confidence_clamped_to_valid_range():
    assert validate_confidence(150) == 100
    assert validate_confidence(-10) == 0
    assert validate_confidence(50) == 50
