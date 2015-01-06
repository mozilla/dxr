import struct

with open("some_bytes", "wb") as output:
    # We just have to make sure '\0' is in this data (that's how DXR detects binary)
    output.write(struct.pack("fill", 3.142, 2, 400, 0))
