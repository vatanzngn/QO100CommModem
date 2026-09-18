import socket
import struct
import threading
import time
import math
import argparse

try:
    import reedsolo
except ImportError:
    raise SystemExit("reedsolo gerekli:  pip install reedsolo")

RS_NSYM = 32
RS_N    = 255
RS_K    = RS_N - RS_NSYM
RS_T    = RS_NSYM // 2

_rsc = reedsolo.RSCodec(RS_NSYM)

TX_HOST = '127.0.0.1'

CHANNELS = {
    1: {'TX': 5001, 'EVM': 5002, 'RX': [5003, 5004, 5005, 5006]},
    2: {'TX': 5007, 'EVM': 5008, 'RX': [5009, 5010, 5011, 5012]},
    3: {'TX': 5013, 'EVM': 5014, 'RX': [5015, 5016, 5017, 5018]},
    4: {'TX': 5019, 'EVM': 5020, 'RX': [5021, 5022, 5023, 5024]},
}

PORT_NAMES = {0: '0deg', 1: '90deg', 2: '180deg', 3: '270deg'}

SYNC_MAGIC     = bytes([0xAA, 0x55, 0xDE, 0xAD])
SYNC_LEN       = len(SYNC_MAGIC)
MAX_SYNC_ERRS  = 3

INFO_HDR_LEN   = 4
DATA_LEN       = RS_K - INFO_HDR_LEN
WIRE_FRAME_SIZE = SYNC_LEN + RS_N

RX_BUF_MAX     = 8 * WIRE_FRAME_SIZE
SHOW_MAX       = 120

CONSTEL_POINTS = [complex(1, 1), complex(-1, 1), complex(-1, -1), complex(1, -1)]
CONSTEL_RADIUS = math.sqrt(2.0)

EVM_BUFFER_MAX = 4000
ACTIVE_RATIO   = 0.30

sent_texts     = {}
frame_stats    = {}
lock           = threading.Lock()
stop_listeners = False

seen_frames    = {}
DEDUPE_TTL     = 30.0

evm_buffer  = []
evm_lock    = threading.Lock()
latest_evm  = {'evm_pct': None, 'snr_db': None, 'ts': 0.0}
latest_lock = threading.Lock()

_POPCNT = bytes(bin(i).count('1') for i in range(256))


def fmt_snr(v):
    return "--.-" if v is None else f"{v:.1f}"


def bit_diff(a, b):
    return sum(_POPCNT[x ^ y] for x, y in zip(a, b))


def build_frame(text, seq):
    raw = text.encode('utf-8')[:DATA_LEN]
    payload = raw.ljust(DATA_LEN, b'\x00')

    info = struct.pack('>HH', seq & 0xFFFF, len(raw)) + payload
    assert len(info) == RS_K, f"info uzunlugu hatali: {len(info)} != {RS_K}"

    codeword = bytes(_rsc.encode(info))
    assert len(codeword) == RS_N, f"kod sozcugu hatali: {len(codeword)} != {RS_N}"

    return SYNC_MAGIC + codeword


def sanitize(s):
    return ''.join(c if (c.isprintable() or c in ' \t') else '\u00b7' for c in s)


def _extract_text(info):
    seq, text_len = struct.unpack_from('>HH', info, 0)
    payload = info[INFO_HDR_LEN:]
    if text_len > DATA_LEN:
        text_len = None
    raw = payload[:text_len] if text_len is not None else payload.rstrip(b'\x00')
    return seq, raw.decode('utf-8', errors='replace')


def decode_frame(codeword):
    try:
        out         = _rsc.decode(codeword)
        info        = bytes(out[0])
        n_corrected = len(out[2]) if len(out) > 2 else -1
        if len(info) == RS_K:
            seq, text = _extract_text(info)
            return seq, text, n_corrected, 'OK'
    except reedsolo.ReedSolomonError:
        pass

    seq, text = _extract_text(codeword[:RS_K])
    return seq, text, -1, 'BOZUK'


def find_nearest_constel(sym):
    best = CONSTEL_POINTS[0]
    bd = abs(sym - best)
    for p in CONSTEL_POINTS[1:]:
        d = abs(sym - p)
        if d < bd:
            bd, best = d, p
    return best


def compute_evm_snr(samples):
    if not samples or len(samples) < 16:
        return None, None
    max_mag = max(abs(s) for s in samples)
    if max_mag < 1e-4:
        return None, None
    threshold = ACTIVE_RATIO * max_mag
    active = [s for s in samples if abs(s) > threshold]
    if len(active) < 16:
        return None, None
    avg_mag = sum(abs(s) for s in active) / len(active)
    if avg_mag < 1e-6:
        return None, None
    scale = CONSTEL_RADIUS / avg_mag
    norm = [s * scale for s in active]

    best_evm_sq = float('inf')
    for k in range(4):
        ang = k * math.pi / 2.0
        rot = complex(math.cos(ang), math.sin(ang))
        err_sq = ref_sq = 0.0
        for s in norm:
            r = s * rot
            ideal = find_nearest_constel(r)
            err_sq += abs(r - ideal) ** 2
            ref_sq += abs(ideal) ** 2
        if ref_sq > 0:
            v = err_sq / ref_sq
            if v < best_evm_sq:
                best_evm_sq = v

    if best_evm_sq == float('inf') or best_evm_sq < 0:
        return None, None
    evm_rms = math.sqrt(max(best_evm_sq, 1e-12))
    return evm_rms * 100.0, -20.0 * math.log10(evm_rms)


def evm_listener(port):
    global evm_buffer
    sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    sock.settimeout(2.0)
    for _ in range(6):
        try:
            sock.connect((TX_HOST, port))
            break
        except (ConnectionRefusedError, socket.timeout, OSError):
            time.sleep(0.5)
    else:
        return

    buf = bytearray()
    SAMPLE_SIZE = 8
    try:
        while not stop_listeners:
            try:
                chunk = sock.recv(8192)
            except socket.timeout:
                continue
            except Exception:
                break
            if not chunk:
                break
            buf.extend(chunk)
            n = len(buf) // SAMPLE_SIZE
            if n <= 0:
                continue
            new = []
            for i in range(n):
                re, im = struct.unpack_from('<ff', buf, i * SAMPLE_SIZE)
                new.append(complex(re, im))
            del buf[:n * SAMPLE_SIZE]
            with evm_lock:
                evm_buffer.extend(new)
                if len(evm_buffer) > EVM_BUFFER_MAX:
                    del evm_buffer[:len(evm_buffer) - EVM_BUFFER_MAX]
    finally:
        sock.close()


def evm_compute_thread():
    while not stop_listeners:
        time.sleep(0.4)
        with evm_lock:
            samp = list(evm_buffer)
        evm_pct, snr_db = compute_evm_snr(samp)
        if evm_pct is not None:
            with latest_lock:
                latest_evm.update(evm_pct=evm_pct, snr_db=snr_db, ts=time.time())


def get_latest_metrics():
    with latest_lock:
        return latest_evm['evm_pct'], latest_evm['snr_db'], latest_evm['ts']


def find_sync(buf, start):
    limit = len(buf) - SYNC_LEN
    for i in range(start, limit + 1):
        if bit_diff(buf[i:i + SYNC_LEN], SYNC_MAGIC) <= MAX_SYNC_ERRS:
            return i
    return -1


def handle_frame(res, name):
    seq, text, n_corr, status = res
    key = (seq, text)
    now = time.time()

    with lock:
        for k, ts in list(seen_frames.items()):
            if now - ts > DEDUPE_TTL:
                del seen_frames[k]
        duplicate = key in seen_frames
        seen_frames[key] = now
        if not duplicate:
            frame_stats[seq] = {'corrected': n_corr, 'branch': name,
                                'status': status, 'snr_db': latest_evm['snr_db']}

    if duplicate:
        return

    _, snr_now, _ = get_latest_metrics()

    if status == 'OK':
        load = n_corr / RS_T if n_corr >= 0 else 0.0
        ser  = n_corr / RS_N if n_corr >= 0 else 0.0
        warn = "  <-- FEC sinirinda!" if load > 0.75 else ""
        fec  = (f"RS duzeltme: {n_corr}/{RS_T} sembol | SER: {ser:.2e} | "
                f"yuk: {load*100:.0f}%{warn}")
        tag  = "[OK]"
        shown = sanitize(text)
    else:
        fec  = f"RS COZEMEDI (>{RS_T} sembol hata) | metin DUZELTILMEMIS"
        tag  = "[BOZUK]"
        shown = sanitize(text)
        if len(shown) > SHOW_MAX:
            shown = shown[:SHOW_MAX] + f" ...(+{len(text)-SHOW_MAX} karakter)"

    print(f"\n[RX] {tag} Seq: {seq}  (kol: {name})")
    print(f"> {shown}")
    print(f"[Stat] {fec} | SNR: {fmt_snr(snr_now)} dB\n")


def rx_listener(port, name):
    s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    s.settimeout(2.0)
    try:
        s.connect((TX_HOST, port))
    except (ConnectionRefusedError, socket.timeout):
        return

    buf = bytearray()
    try:
        while not stop_listeners:
            try:
                chunk = s.recv(4096)
            except socket.timeout:
                chunk = None
            if chunk is not None:
                if not chunk:
                    break
                buf.extend(chunk)

            pos = 0
            while True:
                idx = find_sync(buf, pos)
                if idx < 0:
                    if len(buf) > SYNC_LEN - 1:
                        del buf[:len(buf) - (SYNC_LEN - 1)]
                    break

                if idx + WIRE_FRAME_SIZE > len(buf):
                    del buf[:idx]
                    break

                cw  = bytes(buf[idx + SYNC_LEN: idx + WIRE_FRAME_SIZE])
                handle_frame(decode_frame(cw), name)
                del buf[:idx + WIRE_FRAME_SIZE]
                pos = 0

            if len(buf) > RX_BUF_MAX:
                del buf[:len(buf) - RX_BUF_MAX]
    finally:
        s.close()


def selftest():
    import random
    random.seed(0)
    print("Self-test: RS(255,223), t =", RS_T, "sembol\n")

    frame = build_frame("TA7WRS test mesaji - QO100 RS FEC", 42)
    print(f"  Wire frame: {len(frame)} byte  (sync {SYNC_LEN} + RS {RS_N})")
    print(f"  Faydali yuk kapasitesi: {DATA_LEN} byte\n")

    ref = "TA7WRS test mesaji - QO100 RS FEC"
    print("  n_err  [OK] tam dogru  [BOZUK]  ortalama okunabilirlik")
    for n_err in (0, 8, 16, 17, 20, 30, 60):
        ok = bozuk = 0
        match_ratio = []
        for _ in range(200):
            b = bytearray(frame)
            for i in random.sample(range(SYNC_LEN, len(frame)), n_err):
                b[i] ^= random.randint(1, 255)
            seq, text, n_corr, status = decode_frame(bytes(b[SYNC_LEN:]))
            if status == 'OK':
                ok += 1
            else:
                bozuk += 1
            same = sum(1 for a, c in zip(text, ref) if a == c)
            match_ratio.append(same / len(ref))
        print(f"  {n_err:4d}   {ok:6d}        {bozuk:5d}    "
              f"{sum(match_ratio)/len(match_ratio)*100:5.1f}% karakter dogru")

    print("\n  Ornek bozuk cikti (30 sembol hatasi):")
    b = bytearray(frame)
    for i in random.sample(range(SYNC_LEN, len(frame)), 30):
        b[i] ^= random.randint(1, 255)
    seq, text, _, status = decode_frame(bytes(b[SYNC_LEN:]))
    print(f"    [{status}] seq={seq}")
    print(f"    > {sanitize(text)[:70]}")

    print("\n  Yanlis faz kolu: SYNC eslesmesi elemeli (RS degil)")
    import os
    hit = sum(1 for _ in range(2000)
              if find_sync(bytearray(os.urandom(WIRE_FRAME_SIZE)), 0) == 0)
    print(f"    2000 rastgele blokta bas tarafta yanlis sync: {hit}")


def main():
    global stop_listeners

    ap = argparse.ArgumentParser(description="Interactive QPSK + Reed-Solomon Chat")
    ap.add_argument('--channel', type=int, choices=[1, 2, 3, 4], default=1)
    ap.add_argument('--selftest', action='store_true', help="GRC olmadan FEC testi")
    args = ap.parse_args()

    if args.selftest:
        selftest()
        return

    cfg = CHANNELS[args.channel]

    print('=' * 78)
    print(f'  QPSK INTERACTIVE CHAT  (Reed-Solomon {RS_N},{RS_K})  -- Kanal: {args.channel}')
    print(f'  Faydali yuk: {DATA_LEN} byte/frame. Uzun mesajlar kesilir.')
    print(f'  Duzeltme kapasitesi: {RS_T} sembol/frame. Kod orani: {RS_K/RS_N:.3f}')
    print(f'  Cikis: "quit" / "exit" / "q"')
    print('=' * 78 + '\n')

    threading.Thread(target=evm_listener, args=(cfg['EVM'],), daemon=True).start()
    threading.Thread(target=evm_compute_thread, daemon=True).start()

    for idx, port in enumerate(cfg['RX']):
        threading.Thread(target=rx_listener, args=(port, PORT_NAMES[idx]),
                         daemon=True).start()

    time.sleep(1.0)

    tx_sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    tx_sock.setsockopt(socket.IPPROTO_TCP, socket.TCP_NODELAY, 1)
    try:
        tx_sock.connect((TX_HOST, cfg['TX']))
    except ConnectionRefusedError:
        print(f"[!] TX portuna ({cfg['TX']}) baglanilamadi. GRC acik mi?")
        return

    seq = 1
    try:
        while True:
            user_input = input("Mesajini yaz > ")
            if user_input.lower() in ('quit', 'exit', 'q'):
                print("[*] Cikis yapiliyor...")
                break
            if not user_input:
                continue

            frame = build_frame(user_input, seq)
            with lock:
                sent_texts[seq] = user_input[:DATA_LEN]

            tx_sock.sendall(frame)
            _, snr_now, _ = get_latest_metrics()
            print(f"[TX] Gonderildi (Seq: {seq}, {len(frame)}B). "
                  f"SNR: {fmt_snr(snr_now)} dB")
            seq += 1
            time.sleep(0.5)

    except KeyboardInterrupt:
        print("\n[*] Ctrl+C ile durduruldu.")
    finally:
        stop_listeners = True
        tx_sock.close()
        print("[*] Baglantilar kapatildi.")


if __name__ == "__main__":
    main()
