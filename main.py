import asyncio
import json
import struct
import bleak
from httpx import AsyncClient
from rich import print
from bleak import BleakClient, BleakScanner
from bleak.backends.characteristic import BleakGATTCharacteristic
from bleak.backends.scanner import AdvertisementData
from bleak.backends.device import BLEDevice
from bleak.args.bluez import BlueZDiscoveryFilters, BlueZScannerArgs

ADDRESS = "80:E1:26:1D:3D:92"
UUID_WRITE = "19ed82ae-ed21-4c9d-4145-228e62fe0000"
UUID_READ = "19ed82ae-ed21-4c9d-4145-228e61fe0000"
FORMAT = "<ffffffBBHH"
## values = [1.1, 2.2, 3.3, 4.4, 5.5, 6.6, 1, 1, 3333, 4444]
sensor_dict = dict()
host = ""
token = ""


def prepare_data(data_dict):
    data = list()
    data.append(float(data_dict["bt"]))
    data.append(float(data_dict["bh"]))
    data.append(float(data_dict["kt"]))
    data.append(float(data_dict["kh"]))
    data.append(float(data_dict["ot"]))
    data.append(float(data_dict["oh"]))
    data.append(1 if data_dict["dh"] == "on" else 0)
    data.append(1 if data_dict["ad"] == "on" else 0)
    data.append(int(data_dict["co"]))
    data.append(int(data_dict["pm"]))

    return data


async def get_sensors(client: AsyncClient):
    r = await client.get(
        f"{host}/api/states",
        headers={"Content-Type": "application/json", "Authorization": f"Bearer {token}"},
    )
    js = r.json()
    return_dict = dict()
    for sensor in js:
        if sensor["entity_id"] in sensor_dict:
            return_dict[sensor_dict[sensor["entity_id"]]] = sensor["state"]

    return prepare_data(return_dict)


async def toggle_entity(client: AsyncClient, entity: str) -> None:
    entity_dict = dict()
    entity_dict["entity_id"] = entity
    await client.post(
        f"{host}/api/services/switch/toggle",
        headers={"Content-Type": "application/json", "Authorization": f"Bearer {token}"},
        json=entity_dict,
    )


def short_to_long_entity(short_entity: str) -> str | None:
    for entity in sensor_dict:
        if sensor_dict[entity] == short_entity:
            return entity

    return None


class Comm:
    def __init__(self) -> None:
        self.client = None
        self.detected = False
        self.connected = False
        self.http_client = AsyncClient()

    async def detection_cb(self, device: BLEDevice, advertisement_data: AdvertisementData):
        # print(device.address, device.name, advertisement_data)
        if device.address == ADDRESS and not self.detected:
            print(f"Detected: {device.address}")
            self.detected = True
            await self.connect(device)

    async def connect(self, device: BLEDevice):
        self.client = BleakClient(device, timeout=10, pair=False)
        await self.client.connect()
        self.connected = True
        print(f"Connected: {self.client.is_connected}")

    async def disconnect(self):
        if not self.connected:
            self.detected = False
            self.connected = False
            await self.client.disconnect()  # type: ignore
            self.client = None

    async def read_cb(self, characteristic: BleakGATTCharacteristic, data: bytearray):
        read_cmds = data.decode("ascii").split("|")
        cmds_dict = dict()
        for cmd in read_cmds:
            kv = cmd.split(":")
            cmds_dict[kv[0]] = kv[1]

        for k in cmds_dict:
            match cmds_dict[k]:
                case "toggle":
                    entity = short_to_long_entity(k)
                    if entity is not None:
                        print(f"Sending command: {entity} | [Toggle]")
                        await toggle_entity(self.http_client, entity)

                case _:
                    print("Not implemented")

    async def write(self) -> None:
        try:
            while self.connected:
                sensors = await get_sensors(self.http_client)
                print(f"Sending: {sensors}")
                buffer = struct.pack(FORMAT, *sensors)
                await self.client.write_gatt_char(UUID_WRITE, buffer, False)  # type: ignore
                print("Sent.")
                await asyncio.sleep(5.0)

        except bleak.exc.BleakError as e:  # type: ignore
            print(e)
            print("Write failed, back to scanning")

        finally:
            await self.disconnect()


async def main(address: str):
    comm = Comm()
    filters = BlueZDiscoveryFilters(Transport="le", DuplicateData=True)
    scanner = BleakScanner(comm.detection_cb, bluez=BlueZScannerArgs(filters=filters))
    while True:
        await scanner.start()
        while not comm.connected:
            await asyncio.sleep(5.0)

        await scanner.stop()
        await comm.client.start_notify(UUID_READ, comm.read_cb)  # type: ignore
        _ = await asyncio.gather(comm.write())


if __name__ == "__main__":
    with open("config.json") as fd:
        json_dict = json.load(fd)

    host = json_dict["host"]
    json_dict.pop("host")
    token = json_dict["token"]
    json_dict.pop("token")
    sensor_dict = json_dict
    asyncio.run(main(ADDRESS))
