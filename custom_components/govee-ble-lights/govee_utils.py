import array
import math

def convert_temp_to_RGB(color_temp):
    """
    Converts from K to RGB, algorithm courtesy of
    http://www.tannerhelland.com/4435/convert-temperature-rgb-algorithm-code/
    """
    #range check
    if color_temp < 1000:
        color_temp = 1000
    elif color_temp > 40000:
        color_temp = 40000

    tmp_internal = color_temp / 100.0

    # red
    if tmp_internal <= 66:
        red = 255
    else:
        tmp_red = 329.698727446 * math.pow(tmp_internal - 60, -0.1332047592)
        if tmp_red < 0:
            red = 0
        elif tmp_red > 255:
            red = 255
        else:
            red = math.ceil(tmp_red)

    # green
    if tmp_internal <=66:
        tmp_green = 99.4708025861 * math.log(tmp_internal) - 161.1195681661
        if tmp_green < 0:
            green = 0
        elif tmp_green > 255:
            green = 255
        else:
            green = math.ceil(tmp_green)
    else:
        tmp_green = 288.1221695283 * math.pow(tmp_internal - 60, -0.0755148492)
        if tmp_green < 0:
            green = 0
        elif tmp_green > 255:
            green = 255
        else:
            green = math.ceil(tmp_green)

    # blue
    if tmp_internal >=66:
        blue = 255
    elif tmp_internal <= 19:
        blue = 0
    else:
        tmp_blue = 138.5177312231 * math.log(tmp_internal - 10) - 305.0447927307
        if tmp_blue < 0:
            blue = 0
        elif tmp_blue > 255:
            blue = 255
        else:
            blue = math.ceil(tmp_blue)

    return red, green, blue

def prepareMultiplePacketsData(protocol_type, header_array, data):
    result = []

    # Initialize the initial buffer
    header_length = len(header_array)
    initial_buffer = array.array('B', [0] * 20)
    initial_buffer[0] = protocol_type
    initial_buffer[1] = 0
    initial_buffer[2] = 1
    initial_buffer[4:4+header_length] = header_array

    # Create the additional buffer
    additional_buffer = array.array('B', [0] * 20)
    additional_buffer[0] = protocol_type
    additional_buffer[1] = 255

    remaining_space = 14 - header_length + 1

    if len(data) <= remaining_space:
        initial_buffer[header_length + 4:header_length + 4 + len(data)] = data
    else:
        excess = len(data) - remaining_space
        chunks = excess // 17
        remainder = excess % 17

        if remainder > 0:
            chunks += 1
        else:
            remainder = 17

        initial_buffer[header_length + 4:header_length + 4 + remaining_space] = data[0:remaining_space]
        current_index = remaining_space

        for i in range(1, chunks + 1):
            chunk = array.array('B', [0] * 17)
            chunk_size = remainder if i == chunks else 17
            chunk[0:chunk_size] = data[current_index:current_index + chunk_size]
            current_index += chunk_size

            if i == chunks:
                additional_buffer[2:2 + chunk_size] = chunk[0:chunk_size]
            else:
                chunk_buffer = array.array('B', [0] * 20)
                chunk_buffer[0] = protocol_type
                chunk_buffer[1] = i
                chunk_buffer[2:2+chunk_size] = chunk
                chunk_buffer[19] = sign_payload(chunk_buffer[0:19])
                result.append(chunk_buffer)

    initial_buffer[3] = len(result) + 2
    initial_buffer[19] = sign_payload(initial_buffer[0:19])
    result.insert(0, initial_buffer)

    additional_buffer[19] = sign_payload(additional_buffer[0:19])
    result.append(additional_buffer)

    return result

def sign_payload(data):
    checksum = 0
    for b in data:
        checksum ^= b
    return checksum & 0xFF
