"""A simple asynchronous server."""

import asyncio
import logging
import signal
import sys
import time

import numpy as np

from pymodbus.datastore import ModbusSlaveContext, ModbusServerContext
from pymodbus.device import ModbusDeviceIdentification
from pymodbus.server.async_io import ModbusTcpServer
from pymodbus.version import version

# Set up basic logging
logging.basicConfig()
logging.getLogger().setLevel(logging.DEBUG)
log = logging.getLogger(__name__)


def update_coils(context: ModbusSlaveContext):
    """Updates the coils of slave `context` with new values.

    Args:
        context: Slave context to update.
    """

    # Get epoch time as 64 bits
    now = time.time()
    bstring = f'{np.asarray(now, dtype=np.float64).view(np.uint64):064b}'
    bits = [b == '1' for b in bstring]

    # Update coils from hex address 0 (fx 1 maps to coils)
    fx = 1
    context.setValues(fx, 0, bits)

    # Get sin(t) as 32 bits
    sin = np.sin(now)
    bstring = f'{np.asarray(sin, dtype=np.float32).view(np.uint32):032b}'
    bits = [b == '1' for b in bstring]

    # Update coils from address 2 (fx 1 maps to coils)
    fx = 1
    context.setValues(fx, 64, bits)


async def update_context(context: ModbusServerContext, interval: float = 0.1):
    """Updates the server `context` on a regular interval.

    Args:
        context: Slave context to update.
        interval: Interval in seconds between updates.
    """

    # Update slave context on set interval
    unit = 0x00
    slave = context[unit]
    while True:
        try:
            update_coils(slave)
            await asyncio.sleep(interval)
        except asyncio.CancelledError:
            log.debug('Cancelling context updates')
            break


async def main():
    """Runs the asynchronous server.

    Args:
        context: Slave context to update.
    """

    # Create the store (a Modbus data model) with fully initialized ranges
    store = ModbusSlaveContext()
    context = ModbusServerContext(slaves=store)

    # Initialize server information
    identity = ModbusDeviceIdentification()
    identity.VendorName = 'Pymodbus'
    identity.ProductCode = 'PM'
    identity.VendorUrl = 'http://github.com/riptideio/pymodbus/'
    identity.ProductName = 'Pymodbus Server'
    identity.ModelName = 'Pymodbus Server'
    identity.MajorMinorRevision = version.short()

    # Add coils updater to event loop
    loop = asyncio.get_event_loop()
    task = loop.create_task(update_context(context))

    # Create the TCP Server
    adr = ('', 5020)
    server = ModbusTcpServer(context, address=adr, defer_start=True, loop=loop)

    # Add signal handlers for graceful closure
    for sig in (signal.SIGINT, signal.SIGTERM):
        if sys.platform == 'linux':
            loop.add_signal_handler(sig, task.cancel)
            loop.add_signal_handler(sig, server.server_close)
        elif sys.platform == 'win32':

            def cancel(*args, task=task):
                task.cancel()

            def server_close(*args, server=server):
                server.server_close()

            signal.signal(sig, cancel)
            signal.signal(sig, server_close)

    # Start the server
    try:
        await server.serve_forever()
    except asyncio.CancelledError:
        pass


if __name__ == "__main__":
    asyncio.run(main())
