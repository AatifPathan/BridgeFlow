"""
Bridge Flow - TCP Wire Protocol

Every message on the TCP connection is framed as:

    [4-byte big-endian length][payload]

For control messages, the payload is UTF-8 JSON. For chunk data
messages, the payload is binary: [4-byte chunk_index][4-byte
chunk_length][raw chunk bytes] - framed the same way, just with a
binary body instead of JSON, so both share one read/write primitive.

Keeping ONE framing function for everything (send_frame/read_frame)
means the rest of the code never has to guess "how much do I read" -
it always reads exactly what the 4-byte length prefix says.
"""

import asyncio
import json
import struct

# --- Control message types -------------------------------------------

MSG_PAIR_REQUEST = "PAIR_REQUEST"
MSG_PAIR_CONFIRM = "PAIR_CONFIRM"
MSG_PAIR_ACCEPTED = "PAIR_ACCEPTED"
MSG_PAIR_REJECTED = "PAIR_REJECTED"

MSG_AUTH = "AUTH"
MSG_AUTH_OK = "AUTH_OK"
MSG_AUTH_REJECT = "AUTH_REJECT"

MSG_TRANSFER_REQUEST = "TRANSFER_REQUEST"
MSG_TRANSFER_ACCEPT = "TRANSFER_ACCEPT"
MSG_TRANSFER_REJECT = "TRANSFER_REJECT"
MSG_RESUME_REQUEST = "RESUME_REQUEST"   # receiver -> sender: "I'm missing these chunks"
MSG_CHUNK_HEADER = "CHUNK_HEADER"       # announces a binary chunk frame follows
MSG_CHUNK_ACK = "CHUNK_ACK"
MSG_TRANSFER_COMPLETE = "TRANSFER_COMPLETE"
MSG_VERIFY_RESULT = "VERIFY_RESULT"

CHUNK_INDEX_STRUCT = struct.Struct(">I")   # 4-byte unsigned int, big-endian
LENGTH_PREFIX_STRUCT = struct.Struct(">I")


async def close_writer(writer: asyncio.StreamWriter):
    """Close a connection and wait for it to finish closing. Skipping the wait
    makes asyncio's Windows (Proactor) loop print harmless-but-alarming
    'connection forcibly closed' tracebacks."""
    try:
        writer.close()
        await writer.wait_closed()
    except (ConnectionError, OSError):
        pass


async def send_json(writer: asyncio.StreamWriter, message: dict):
    payload = json.dumps(message).encode("utf-8")
    writer.write(LENGTH_PREFIX_STRUCT.pack(len(payload)))
    writer.write(payload)
    await writer.drain()


async def read_json(reader: asyncio.StreamReader) -> dict:
    length_bytes = await reader.readexactly(4)
    (length,) = LENGTH_PREFIX_STRUCT.unpack(length_bytes)
    payload = await reader.readexactly(length)
    return json.loads(payload.decode("utf-8"))


async def send_chunk(writer: asyncio.StreamWriter, chunk_index: int, data: bytes):
    """Binary frame: [4-byte total length][4-byte chunk_index][raw bytes]"""
    body = CHUNK_INDEX_STRUCT.pack(chunk_index) + data
    writer.write(LENGTH_PREFIX_STRUCT.pack(len(body)))
    writer.write(body)
    await writer.drain()


async def read_chunk(reader: asyncio.StreamReader) -> tuple[int, bytes]:
    length_bytes = await reader.readexactly(4)
    (length,) = LENGTH_PREFIX_STRUCT.unpack(length_bytes)
    body = await reader.readexactly(length)
    chunk_index = CHUNK_INDEX_STRUCT.unpack(body[:4])[0]
    data = body[4:]
    return chunk_index, data
