"""Verify the icon group and its image sizes in the Windows PE executable."""
import struct
import sys
from pathlib import Path
import pefile

def resource_entries(pe, resource_type):
    for entry in pe.DIRECTORY_ENTRY_RESOURCE.entries:
        if entry.id == resource_type:
            return entry.directory.entries
    return []

def resource_data(pe, entry):
    data = entry.directory.entries[0].data.struct
    return pe.get_data(data.OffsetToData, data.Size)

def main():
    executable = Path(sys.argv[1])
    pe = pefile.PE(str(executable))
    groups = resource_entries(pe, 14)
    images = resource_entries(pe, 3)
    if not groups or not images:
        raise SystemExit("Executable does not contain Windows icon resources")
    sizes = set()
    image_ids = {entry.id for entry in images}
    for group in groups:
        data = resource_data(pe, group)
        reserved, kind, count = struct.unpack_from("<HHH", data)
        if reserved != 0 or kind != 1 or len(data) < 6 + 14 * count:
            raise SystemExit("Invalid icon group")
        group_sizes = set()
        for i in range(count):
            w, h, _, _, _, _, length, image_id = struct.unpack_from(
                "<BBBBHHIH", data, 6 + 14 * i
            )
            if image_id not in image_ids or length == 0 or w != h:
                raise SystemExit("Missing or invalid icon image")
            group_sizes.add(w or 256)
        sizes |= group_sizes
    expected = {16, 24, 32, 48, 64, 128, 256}
    if not expected.issubset(sizes):
        raise SystemExit(f"Missing icon sizes: {sorted(expected - sizes)}")
    print(f"Verified Windows PE icon sizes: {sorted(sizes)}")

if __name__ == "__main__":
    main()
