"""Global fixtures for Roborock integration."""
from unittest.mock import patch

import pytest

from .mock_data import PROP


# This fixture enables loading custom integrations in all tests.
# Remove to enable selective use of this fixture
@pytest.fixture(autouse=True)
def auto_enable_custom_integrations(enable_custom_integrations):
    yield


@pytest.fixture(name="bypass_api_fixture")
def bypass_api_fixture():
    """Skip calls to the API."""
    with patch("custom_components.roborock.RoborockMqttClient.connect"), patch(
        "custom_components.roborock.RoborockMqttClient.send_command"
    ), patch("custom_components.roborock.api.api.mqtt"), patch(
        "custom_components.roborock.RoborockMqttClient.get_prop", return_value=PROP
    ):
        yield
