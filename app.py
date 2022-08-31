"""FastAPI server app with embedded Modbus client."""

import asyncio
import datetime
import logging
import sys
import time

from typing import Tuple

import numpy as np

from fastapi import Depends, FastAPI, HTTPException, WebSocket
from fastapi.middleware.cors import CORSMiddleware
from pymodbus.client.asynchronous.tcp import AsyncModbusTCPClient
from pymodbus.client.asynchronous import schedulers

# Fix Windows RuntimeError: Event loop is closed on KeyboardInterrupt
if sys.platform.startswith('win'):
    asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())

#: FastAPI application
app = FastAPI()

origins = ['http://127.0.0.1:5173']

app.add_middleware(
    CORSMiddleware,
    allow_origins=origins,
    allow_credentials=True,
    allow_methods=['*'],
    allow_headers=['*'],
)

#: Application log
app_log = logging.getLogger('modbus.d3.app')
app_log.setLevel(logging.INFO)
sh = logging.StreamHandler()
fmt = '%(asctime)s,%(levelname)s,%(message)s'
datefmt = '%H:%M:%S'
sh.setFormatter(logging.Formatter(fmt=fmt, datefmt=datefmt))
app_log.addHandler(sh)


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

    # Read coils for time bits
    rrt = await client.protocol.read_coils(0, 64)
    time_bits = rrt.bits

    # Read coils for sin(t) bits
    rrs = await client.protocol.read_coils(64, 32)
    sin_bits = rrs.bits

    epoch_time, sin = convert_bits(time_bits, sin_bits)
    return epoch_time, sin


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

    shs = [
        h for h in app_log.handlers
        if not isinstance(h, logging.FileHandler)]
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
async def get(
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
    return await get_data(client, log)


async def get_data(
    client: AsyncModbusTCPClient,
    log: logging.Logger,
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
        log.info('%s,%s', epoch_time, epoch_sin)
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

@app.websocket('/ws')
async def websocket_endpoint(websocket: WebSocket):
    await websocket.accept()
    client = await get_client()
    log = get_file_logger()
    while True:
        data = await websocket.receive_json()
        if data['method'] == 'get':
            try:
                resp = await get_data(client, log)
            except HTTPException:
                resp = {'x': time.time(), 'y': 0, 'e': 1}
            await websocket.send_json(resp)
        elif data['method'] == 'reset':
            drop_file_logger()
            log = get_file_logger()
            await websocket.send_json({})
        elif data['method'] == 'close':
            break
    await websocket.close()
