"""FastAPI server app with embedded Modbus client."""

import asyncio
import datetime
import logging

from typing import Tuple

import numpy as np

from fastapi import Depends, FastAPI, HTTPException
from pymodbus.client.asynchronous.tcp import AsyncModbusTCPClient
from pymodbus.client.asynchronous import schedulers

#: FastAPI application
app = FastAPI()

#: Application log
app_log = logging.getLogger('modbus.d3.app')
app_log.setLevel('INFO')
sh = logging.StreamHandler()
fmt = logging.Formatter('%(asctime)s,%(levelname)s,%(message)s')
datefmt = '%H:%M:%S'
sh.setFormatter(fmt=fmt, datefmt=datefmt)


# Helper
def convert_bits(timeb: list[bool], sinb: list[bool]) -> Tuple[float, float]:
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


# Helper
async def read_coils(client: AsyncModbusTCPClient) -> Tuple[float, float]:
    """Reads Modbus coils using client `protocol`.

    Args:
        protocol: Modbus protocol instance.

    Returns:
        Tuple of `(epoch_time, sin(epoch_time))`.`
    """

    try:
        # Read coils for time bits
        rrt = await client.protocol.read_coils(0, 64)
        time_bits = rrt.bits

        # Read coils for sin(t) bits
        rrs = await client.protocol.read_coils(64, 32)
        sin_bits = rrs.bits

        epoch_time, sin = convert_bits(time_bits, sin_bits)
        return epoch_time, sin
        # log.debug('time: %s\tsin(t): %.6f', dtime, sin)
    except AttributeError as exc:
        assert exc.args[0] in [
            "'NoneType' object has no attribute 'write'",
            "'NoneType' object has no attribute 'read_coils'",
        ]
        # log.debug('AttributeError, rebuilding client and retrying...')
        client = await get_client()
        await asyncio.sleep(1)
    except asyncio.TimeoutError:
        # log.debug('TimeoutError, retrying...')
        await asyncio.sleep(1)


# Dependency
def get_file_logger() -> logging.Logger:
    """Gets the application logger.

    Returns:
        The app logger object.
    """

    if len(app_log.handlers) > 1:
        return app_log

    now = datetime.datetime.now()
    filename = now.strftime('%Y.%m.%d.%H.%M.%S') + '.log'
    fh = logging.FileHandler(filename)
    fh.setFormatter(logging.Formatter(fmt=fmt, datefmt=datefmt))
    app_log.addHandler(fh)
    return app_log


def drop_file_logger() -> logging.Logger:
    """Drops file handler from application logger.

    Returns:
        The app logger object.
    """

    if len(app_log.handlers) == 1:
        return

    shs = [h for h in app_log.handlers if isinstance(h, logging.StreamHandler)]
    app_log.handlers = shs
    return app_log


# Dependency
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


@app.get("/")
async def get_data(
    client=Depends(get_client),
    log=Depends(get_file_logger),
):
    """Gets Modbus data using `client`.

    Args:
        client: Connected Modbus client object.
        log: Logger to support recording data.

    Returns:
        * x : The epoch time
        * y : The sin(epoch time)
    """

    try:
        epoch_time, epoch_sin = await read_coils(client)
    except AttributeError as exc:
        assert exc.args[0] in [
            "'NoneType' object has no attribute 'write'",
            "'NoneType' object has no attribute 'read_coils'",
        ]
        log.warning('AttributeError, rebuilding client and retrying...')
        raise HTTPException(
            status_code=500,
            detail='AsyncModbusTCPClient AttributeError exception raised',
        )
    except asyncio.TimeoutError:
        log.warning('TimeoutError, retrying...')
        raise HTTPException(
            status_code=500,
            detail='asyncio.TimeoutError exception raised',
        )
    return {'x': epoch_time, 'y': epoch_sin}


@app.get("/reset")
def reset_log(log=Depends(drop_file_logger)):
    """Reset app log for new file handler at next '/' GET.

    Args:
        log: Logger stripped of file loggers to prevent file logging.

    Returns:
        Empty dict.
    """

    return {}
