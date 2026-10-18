"""CMS comparison tests use synthetic CMS-shaped rows and never call the network."""
import json
from unittest.mock import patch

from app.services.price_benchmark import national_average_charge


class FakeResponse:
    def __enter__(self):
        return self

    def __exit__(self, *_):
        return False

    def read(self, _limit):
        return json.dumps([
            {"Rndrng_Prvdr_Geo_Lvl": "National", "HCPCS_Cd": "99214", "Avg_Sbmtd_Chrg": "100.00", "Tot_Srvcs": "10", "Place_Of_Srvc": "O"},
            {"Rndrng_Prvdr_Geo_Lvl": "National", "HCPCS_Cd": "99214", "Avg_Sbmtd_Chrg": "200.00", "Tot_Srvcs": "30", "Place_Of_Srvc": "F"},
            {"Rndrng_Prvdr_Geo_Lvl": "State", "HCPCS_Cd": "99214", "Avg_Sbmtd_Chrg": "999.00", "Tot_Srvcs": "100", "Place_Of_Srvc": "O"},
            {"Rndrng_Prvdr_Geo_Lvl": "National", "HCPCS_Cd": "36415", "Avg_Sbmtd_Chrg": "999.00", "Tot_Srvcs": "100", "Place_Of_Srvc": "O"},
        ]).encode()


def test_cms_lookup_uses_national_matching_code_and_service_weighted_average():
    with patch("app.services.price_benchmark.urlopen", return_value=FakeResponse()) as fetch:
        assert national_average_charge("99214") == (17500, "2024")
    request = fetch.call_args.args[0]
    assert "HCPCS_Cd" in request.full_url and "99214" in request.full_url
    assert "Patient" not in request.full_url


def test_invalid_code_skips_cms_lookup():
    with patch("app.services.price_benchmark.urlopen") as fetch:
        assert national_average_charge("room 12") is None
    fetch.assert_not_called()
