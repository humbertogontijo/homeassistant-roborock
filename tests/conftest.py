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
    with  patch(
        "roborock.cloud_api.mqtt"
    ), patch(
            "roborock.RoborockMqttClient.async_connect"
    ), patch(
        "roborock.RoborockMqttClient.send_command"
    ), patch(
        "roborock.RoborockMqttClient.get_prop", return_value=PROP
    ), patch(
        "roborock.RoborockLocalClient.async_connect"
    ), patch(
        "roborock.RoborockLocalClient.send_command"
    ), patch(
        "roborock.RoborockLocalClient.get_prop", return_value=PROP
    ):
        yield
