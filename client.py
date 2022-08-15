"""A simple asynchronous client."""

import asyncio
import datetime
import logging
import sys

from typing import List, Tuple

import numpy as np

from pymodbus.client.asynchronous.async_io import ModbusClientProtocol
from pymodbus.client.asynchronous.tcp import AsyncModbusTCPClient
from pymodbus.client.asynchronous import schedulers


# Set up basic logging
logging.basicConfig()
log = logging.getLogger(__name__)
log.setLevel(logging.DEBUG)


def convert_bits(timeb: List[bool], sinb: List[bool]) -> Tuple[float, float]:
    """Converts `timeb` bits and `sinb` bits to time and float.

    Args:
        timeb: 64 bits representing current server time.
        sinb: 32 bits representing current server sin(t).

    Returns:
        Tuple of `(epoch_time, sin(epoch_time))`.`
    """

    # Convert time bits
    bstring = ''.join(['1' if bit else '0' for bit in timeb])
    tyme = np.asarray(int(bstring, 2), dtype=np.uint64).view(np.float64).item()

    # Convert sin(t) bits
    bstring = ''.join(['1' if bit else '0' for bit in sinb])
    sin = np.asarray(int(bstring, 2), dtype=np.uint32).view(np.float32).item()

    return tyme, sin


async def read_coils(
    protocol: ModbusClientProtocol,
) -> Tuple[float, float]:
    """Reads Modbus coils using client `protocol`.

    Args:
        protocol: Modbus protocol instance.

    Returns:
        Tuple of `(epoch_time, sin(epoch_time))`.`
    """

    while True:
        try:
            # Read coils for time bits
            rrt = await protocol.read_coils(0, 64)
            time_bits = rrt.bits

            # Read coils for sin(t) bits
            rrs = await protocol.read_coils(64, 32)
            sin_bits = rrs.bits

            epoch_time, sin = convert_bits(time_bits, sin_bits)
            dtime = datetime.datetime.fromtimestamp(epoch_time)
            log.debug('time: %s\tsin(t): %.6f', dtime, sin)
            await asyncio.sleep(1)
        except AttributeError as exc:
            assert exc.args[0] in [
                "'NoneType' object has no attribute 'write'",
                "'NoneType' object has no attribute 'read_coils'",
            ]
            log.debug('AttributeError, rebuilding client and retrying...')
            client = await get_client()
            protocol = client.protocol
            await asyncio.sleep(1)
        except asyncio.TimeoutError:
            log.debug('TimeoutError, retrying...')
            await asyncio.sleep(1)
        except asyncio.CancelledError:
            break


async def get_client() -> AsyncModbusTCPClient:
    """Gets an AsyncModbusTCPClient.

    Returns:
        The client object.
    """

    loop = asyncio.get_running_loop()

    _, client_task = AsyncModbusTCPClient(
        schedulers.ASYNC_IO,
        port=5020,
        loop=loop,
    )
    client = await client_task
    return client


async def main():
    """Runs the asynchronous client."""

    loop = asyncio.get_running_loop()

    client = await get_client()
    await loop.create_task(read_coils(client.protocol))


if __name__ == '__main__':
    try:
        if sys.platform.startswith('win'):
            asyncio.set_event_loop_policy(
                asyncio.WindowsSelectorEventLoopPolicy(),
            )
        asyncio.run(main())
    except KeyboardInterrupt:
        log.debug('Closing Modbus client and Bokeh server')
        pass
