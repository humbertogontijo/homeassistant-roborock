import json
import logging
import sys
from pathlib import Path

from custom_components.roborock import RoborockClient, RoborockMqttClient
from custom_components.roborock.api.containers import UserData, HomeData
from custom_components.roborock.api.typing import RoborockDeviceInfo
from custom_components.roborock.api.util import get_running_loop_or_create_one

_LOGGER = logging.getLogger(__name__)


async def main():
    client = RoborockClient(sys.argv[1])
    user_data_path = Path("user_data.json")
    if user_data_path.is_file():
        with open(user_data_path, 'r') as f:
            user_data = UserData(json.load(f))
    else:
        user_data = await client.pass_login(sys.argv[2])
        with open(user_data_path, 'w') as f:
            f.write(json.dumps(user_data.data))
    home_data_path = Path("home_data.json")
    if home_data_path.is_file():
        with open(home_data_path, 'r') as f:
            home_data = HomeData(json.load(f))
    else:
        home_data = await client.get_home_data(user_data)
        with open(home_data_path, 'w') as f:
            f.write(json.dumps(home_data.data))
    device_map: dict[str, RoborockDeviceInfo] = {}
    for device in home_data.devices + home_data.received_devices:
        product = next(
            (
                product
                for product in home_data.products
                if product.id == device.product_id
            ),
            {},
        )
        device_map[device.duid] = RoborockDeviceInfo(device, product)
    mqtt_client = RoborockMqttClient(user_data, device_map)
    status = await mqtt_client.get_status(home_data.devices[0].duid)
    _LOGGER.info(status.data)
    mqtt_client.__del__()


if __name__ == "__main__":
    logging.basicConfig(level=logging.DEBUG)
    loop = get_running_loop_or_create_one()
    loop.run_until_complete(main())
