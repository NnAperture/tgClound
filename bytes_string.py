import base64

def to_str(data_bytes):
    return base64.b64encode(data_bytes).decode('ascii')

def to_bytes(encoded_str):
    return base64.b64decode(encoded_str)