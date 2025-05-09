import os
import struct

def read_chunk(fp):
    # Read length (4 bytes)
    length_bytes = fp.read(4)
    chunk = length_bytes
    length = int.from_bytes(length_bytes, byteorder='big')
    
    # Read chunk name (4 bytes)
    name = fp.read(4)
    chunk += name
    name_str = name.decode('ascii')
    print(f"reading chunk {name_str} with length {length}")
    
    # Read chunk data
    if length > 0:
        data = fp.read(length)
        chunk += data
    
    # Read CRC (4 bytes)
    crc = fp.read(4)
    chunk += crc
    
    return {"name": name_str, "data": chunk}

def read_png_file(fp):
    global png_offset
    pos = fp.tell()
    png_offset = pos
    print(f"Reading PNG @ {pos}")
    
    # Read PNG header
    contents = fp.read(PNG_HEADER_LENGTH)
    
    while True:
        chunk = read_chunk(fp)
        contents += chunk["data"]
        
        if chunk["name"] == "IEND":
            break
    
    return contents

# Constants
PNG_HEADER = bytes([0x89, 0x50, 0x4E, 0x47, 0x0D, 0x0A, 0x1A, 0x0A])
PNG_HEADER_LENGTH = len(PNG_HEADER)
filepath = "PSIconsHighRes.dat"

# Create extracted directory if it doesn't exist
os.makedirs("./extracted", exist_ok=True)

with open(filepath, "rb") as fp:
    count = 0
    png_offset = 0
    
    while True:
        # Read one byte at a time
        char = fp.read(1)
        if not char:  # EOF
            break
            
        # Check for start of PNG magic number
        if char != bytes([0x89]):
            continue
        
        # Backtrack 1 byte
        fp.seek(-1, 1)
        print("checking for full header")
        
        # Check for full PNG header
        search = fp.read(PNG_HEADER_LENGTH)
        if search == PNG_HEADER:
            fp.seek(-PNG_HEADER_LENGTH, 1)
            png_file = read_png_file(fp)
            
            # Write out file
            png_path = f"./extracted/{png_offset}.png"
            # Use 'x' mode for exclusive creation
            try:
                with open(png_path, "xb") as png_fp:
                    png_fp.write(png_file)
                count += 1
            except FileExistsError:
                pass  # Skip if file already exists 