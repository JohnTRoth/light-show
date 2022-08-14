import dataclasses
import struct
import sys
import argparse
import datetime

MEMORY_LIMIT = 681

class ValidationError(Exception):
    pass

@dataclasses.dataclass
class ValidationResults:
    frame_count: int
    step_time: int
    duration_s: int
    memory_usage: float

def validate(file):
    """Calculates the memory usage of the provided .fseq file"""
    magic = file.read(4)
    start, minor, major = struct.unpack("<HBB", file.read(4))
    file.seek(10)
    channel_count, frame_count, step_time = struct.unpack("<IIB", file.read(9))
    file.seek(20)
    compression_type, = struct.unpack("<B", file.read(1))

    if (magic != b'PSEQ') or (start < 24) or (frame_count < 1) or (step_time < 15) or (minor != 0) or (major != 2):
        raise ValidationError("Unknown file format, expected FSEQ v2.0")
    if channel_count != 48:
        raise ValidationError(f"Expected 48 channels, got {channel_count}")
    if compression_type != 0:
        raise ValidationError("Expected file format to be V2 Uncompressed")
    duration_s = (frame_count * step_time / 1000)
    if duration_s > 5*60:
        raise ValidationError(f"Expected total duration to be less than 5 minutes, got {datetime.timedelta(seconds=duration_s)}")

    file.seek(start)

    prev_light = None
    prev_ramp = None
    prev_closure_1 = None
    prev_closure_2 = None
    total_light_count = 30
    total_closure_count = 16
    count = 0
    """lights_used = []"""
    lights_used = [0 for b in range(total_light_count)]
    """closures_used = []"""
    closures_used = [0 for b in range(total_closure_count)]

    light_label = ["Left Outer Main Beam","Right Outer Main Beam","Left Inner Main Beam","Right Inner Main Beam","Left Signature","Right Signature","Left Channel 4","Right Channel 4","Left Channel 5","Right Channel 5","Left Channel 6","Right Channel 6","Left Front Turn","Right Front Turn","Left Front Fog","Right Front Fog","Left Aux Park","Right Aux Park","Left Side Marker","Right Side Marker","Left Side Repeater","Right Side Repeater","Left Rear Turn","Right Rear Turn","Brake Lights","Left Tail","Right Tail","Reverse Lights","Rear Fog Lights","License Plate"]
    closure_label = ["Left Falcon Door (X Only)","Right Falcon Door (X Only)","Left Front Door (S Only)","Right Front Door (S Only)","Left Mirror","Right Mirror","Left Front Window","Left Rear Window","Right Front Window","Right Rear Window","Liftgate","Left Front Door Handle (S or X Only)","Left Rear Door Handle (S or X Only)","Right Front Door Handle (S or X Only)","Rear Rear Door Handle (S or X Only)","Charge Port"]

    for current_frame in range(frame_count):
        lights = file.read(30)
        closures = file.read(16)
        file.seek(2, 1)

        for light_count in range(total_light_count):
            if lights[light_count] > 0:
                lights_used[light_count] = 1
        for closure_count in range(total_closure_count):
            if closures[closure_count] > 0:
                closures_used[closure_count] = 1
        light_state = [(b > 127) for b in lights]
        ramp_state = [min((((255 - b) if (b > 127) else (b)) // 13 + 1) // 2, 3) for b in lights[:14]]
        closure_state = [((b // 32 + 1) // 2) for b in closures]
        if light_state != prev_light:
            prev_light = light_state
            count += 1
        if ramp_state != prev_ramp:
            prev_ramp = ramp_state
            count += 1
        if closure_state[:10] != prev_closure_1:
            prev_closure_1 = closure_state[:10]
            count += 1
        if closure_state[10:] != prev_closure_2:
            prev_closure_2 = closure_state[10:]
            count += 1
    for x in range(total_light_count):
        if lights_used[x] == 0:
            print(f"{light_label[x]} is unused")
    for x in range(total_closure_count):
        if closures_used[x] == 0:
            print(f"{closure_label[x]} is unused")

    return ValidationResults(frame_count, step_time, duration_s, count / MEMORY_LIMIT)

if __name__ == "__main__":
    # Expected usage: python3 validator.py lightshow.fseq
    parser = argparse.ArgumentParser(description="Validate .fseq file for Tesla Light Show use")
    parser.add_argument("file")
    args = parser.parse_args()

    with open(args.file, "rb") as file:
        try:
            results = validate(file)
        except ValidationError as e:
            print(e)
            sys.exit(1)

    print(f"Found {results.frame_count} frames, step time of {results.step_time} ms for a total duration of {datetime.timedelta(seconds=results.duration_s)}.")
    print(f"Used {results.memory_usage*100:.2f}% of the available memory")
    if results.memory_usage > 1:
        sys.exit(1)