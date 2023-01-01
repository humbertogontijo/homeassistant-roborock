"""Mock data for Roborock tests."""

USER_EMAIL = "user@domain.com"

USER_DATA = {
    "tuyaname": "abc123",
    "tuyapwd": "abc123",
    "uid": 123456,
    "tokentype": "",
    "token": "abcdefghijklmnopqrstuzwxyz",
    "rruid": "rr3d21e46b26c450",
    "region": "us",
    "countrycode": "1",
    "country": "US",
    "nickname": "person",
    "rriot": {
        "u": "abc123",
        "s": "abc123",
        "h": "abc123",
        "k": "abc123",
        "r": {
            "r": "US",
            "a": "https://api-us.roborock.com",
            "m": "ssl://mqtt-us.roborock.com:8883",
            "l": "https://wood-us.roborock.com",
        },
    },
    "tuyaDeviceState": 2,
    "avatarurl": "https://files.roborock.com/iottest/default_avatar.png",
}

MOCK_CONFIG = {
    "username": USER_EMAIL,
    "user_data": USER_DATA,
    "base_url": None,
}
