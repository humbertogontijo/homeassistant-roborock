from roborock import HomeDataDevice, HomeDataProduct


class RoborockDeviceInfo:
    def __init__(self, device: HomeDataDevice, product: HomeDataProduct):
        self.device = device
        self.product = product
