"""Draws studio.ico (rounded blue tile, white play mark, a cut line). Pure Python, no extra packages."""
import struct
import zlib
from pathlib import Path


def render(n):
    ss = 4  # supersampling for smooth edges
    N = n * ss
    r = N * 0.22
    px = bytearray()
    tri = [(N * 0.38, N * 0.28), (N * 0.38, N * 0.72), (N * 0.74, N * 0.50)]

    def in_round_rect(x, y):
        cx, cy = min(max(x, r), N - r), min(max(y, r), N - r)
        return (x - cx) ** 2 + (y - cy) ** 2 <= r * r

    def in_tri(x, y):
        (x1, y1), (x2, y2), (x3, y3) = tri
        d = (y2 - y3) * (x1 - x3) + (x3 - x2) * (y1 - y3)
        a = ((y2 - y3) * (x - x3) + (x3 - x2) * (y - y3)) / d
        b = ((y3 - y1) * (x - x3) + (x1 - x3) * (y - y3)) / d
        return a >= 0 and b >= 0 and 1 - a - b >= 0

    for py in range(n):
        px.append(0)  # PNG filter byte
        for pxl in range(n):
            acc = [0, 0, 0, 0]
            for sy in range(ss):
                for sx in range(ss):
                    x, y = pxl * ss + sx + .5, py * ss + sy + .5
                    if not in_round_rect(x, y):
                        continue
                    t = (x + y) / (2 * N)  # diagonal gradient
                    col = (int(0 + 30 * t), int(95 + 60 * t), int(184 + 50 * t))
                    if in_tri(x, y):
                        col = (255, 255, 255)
                    elif abs((y - N * 0.80) - 0) < N * 0.025 and N * 0.22 < x < N * 0.78:
                        col = (190, 230, 255)
                    acc[0] += col[0]; acc[1] += col[1]; acc[2] += col[2]; acc[3] += 255
            k = ss * ss
            if acc[3]:
                cov = acc[3] / 255
                px += bytes([int(acc[0] / cov), int(acc[1] / cov), int(acc[2] / cov), int(acc[3] / k)])
            else:
                px += b"\0\0\0\0"

    def chunk(t, d):
        return struct.pack(">I", len(d)) + t + d + struct.pack(">I", zlib.crc32(t + d) & 0xffffffff)
    return (b"\x89PNG\r\n\x1a\n" + chunk(b"IHDR", struct.pack(">IIBBBBB", n, n, 8, 6, 0, 0, 0))
            + chunk(b"IDAT", zlib.compress(bytes(px), 9)) + chunk(b"IEND", b""))


def main():
    sizes = [16, 24, 32, 48, 64, 128, 256]
    pngs = [render(s) for s in sizes]
    head = struct.pack("<HHH", 0, 1, len(sizes))
    off = 6 + 16 * len(sizes)
    entries = b""
    for s, p in zip(sizes, pngs):
        entries += struct.pack("<BBBBHHII", s % 256, s % 256, 0, 0, 1, 32, len(p), off)
        off += len(p)
    out = Path(__file__).with_name("studio.ico")
    out.write_bytes(head + entries + b"".join(pngs))
    Path(__file__).with_name("studio.png").write_bytes(pngs[-1])
    print(out)


if __name__ == "__main__":
    main()
