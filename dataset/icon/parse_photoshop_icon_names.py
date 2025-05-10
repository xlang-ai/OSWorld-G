import os
import struct
import re

filepath = "IconResources.idx"
header_magic = b"Photoshop Icon Resource Index 1.0\n"

def is_valid_name(name):
    # Check if name contains only printable ASCII characters
    return bool(re.match(r'^[\x20-\x7E]+$', name))

with open(filepath, "rb") as fp:
    # Check magic header
    magic = fp.read(len(header_magic))
    if magic != header_magic:
        exit("error: wrong magic")
    
    # Read low res and high res lines
    low_res = fp.readline().decode('ascii', errors='replace')
    print(low_res, end='')
    
    high_res = fp.readline().decode('ascii', errors='replace')
    print(high_res, end='')

    # Read low x res and high x res lines
    low_x_res = fp.readline().decode('ascii', errors='replace')
    print(low_x_res, end='')
    
    high_x_res = fp.readline().decode('ascii', errors='replace')
    print(high_x_res, end='')
    
    icon_list = []

    num_bytes_per_entry = 368
    offset_starting_byte = 144

    # count = 0
    
    # Read entries
    while True:
        entry = fp.read(num_bytes_per_entry)
        print(entry.decode('ascii', errors='ignore').strip())
        if len(entry) != num_bytes_per_entry:
            break
        
        # count += 1
        # if count > 10:
        #     break
        
        # Get null-terminated name (first 112 bytes contain the name)
        name_bytes = entry[:offset_starting_byte]
        null_pos = name_bytes.find(b'\0')
        if null_pos != -1:
            name_bytes = name_bytes[:null_pos]
        
        try:
            name = name_bytes.decode('ascii', errors='ignore').strip()
            
            # Skip if name is empty or contains invalid characters
            # if not name or not is_valid_name(name):
            #     continue
            
            icon_list.append(name)
            
            # Get offset (4 bytes at position 112)
            offset_bytes = entry[offset_starting_byte:offset_starting_byte + 4]
            offset = int.from_bytes(offset_bytes, byteorder='little', signed=False)
            hex_offset = offset_bytes.hex()
            
            # if offset > 0:  # Only print non-zero offsets
            print(f"{name} : {offset} 0x{hex_offset}")
            
            # Rename the extracted PNG if it exists
            original = f"./extracted/{offset}.png"
            if os.path.exists(original):
                os.rename(original, f"./extracted/{name}.png")
                
        except Exception as e:
            print(f"Error processing entry: {str(e)}")
            continue 