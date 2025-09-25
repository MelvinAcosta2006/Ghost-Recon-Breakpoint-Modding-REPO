import crcmod
import pyperclip
import time

def generate_crc64_id(base_string):
    poly = 0x142F0E1EBA9EA3693  # CRC64-ECMA with leading 1
    crc64_func = crcmod.mkCrcFun(poly, initCrc=0x0, rev=False, xorOut=0x0)
    crc = crc64_func(base_string.encode('utf-8'))
    middle = str(crc % 10**8).zfill(7)
    return f"9696{middle}0"

# Use current timestamp as input seed
base_input = str(time.time_ns())  # nanosecond-precision timestamp
generated_id = generate_crc64_id(base_input)

pyperclip.copy(generated_id)
print(f"Generated ID: {generated_id} (copied to clipboard)")
