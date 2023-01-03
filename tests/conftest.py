"""Global fixtures for Roborock integration."""
import pytest

pytest_plugins = "pytest_homeassistant_custom_component"

# This fixture enables loading custom integrations in all tests.
# Remove to enable selective use of this fixture
@pytest.fixture(autouse=True)
def auto_enable_custom_integrations(enable_custom_integrations):
    yield
