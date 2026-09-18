import argparse
import math
import os
import socket
import struct
import threading
import time

import numpy as np

POLY1 = 109
POLY2 = 79
K = 7
N_STATES = 1 << (K - 1)

_prev_state = np.zeros((N_STATES, 2), dtype=np.int32)
_inp_bit = np.zeros((N_STATES, 2), dtype=np.int8)
_exp_o0 = np.zeros((N_STATES, 2), dtype=np.int8)
_exp_o1 = np.zeros((N_STATES, 2), dtype=np.int8)

_preds = [[] for _ in range(N_STATES)]
for _st in range(N_STATES):
    for _inp in range(2):
        _new_state = ((_st << 1) | _inp) & 0x7F
        _o0 = bin(_new_state & POLY1).count('1') % 2
        _o1 = bin(_new_state & POLY2).count('1') % 2
        _preds[_new_state & 0x3F].append((_st, _inp, _o0, _o1))

for _ns in range(N_STATES):
    for _b, (_ps, _ip, _o0, _o1) in enumerate(_preds[_ns]):
        _prev_state[_ns, _b] = _ps
        _inp_bit[_ns, _b] = _ip
        _exp_o0[_ns, _b] = _o0
        _exp_o1[_ns, _b] = _o1


def cc_encode(data_bytes):
    bits = np.unpackbits(np.frombuffer(data_bytes, dtype=np.uint8))
    n_bits = len(bits)
    state = 0
    for i in range(6):
        state = (state << 1) | int(bits[n_bits - 6 + i])
    out = np.empty(n_bits * 2, dtype=np.uint8)
    for i, bit in enumerate(bits):
        state = ((state << 1) | int(bit)) & 0x7F
        out[2 * i] = bin(state & POLY1).count('1') % 2
        out[2 * i + 1] = bin(state & POLY2).count('1') % 2
    return np.packbits(out).tobytes()


def _viterbi_core(rx_bits, n_info_bits, init_state=0):
    INF = np.iinfo(np.int32).max // 4
    pm = np.full(N_STATES, INF, dtype=np.int32)
    pm[init_state] = 0
    tb = np.zeros((n_info_bits, N_STATES), dtype=np.int8)

    ps0, ps1 = _prev_state[:, 0], _prev_state[:, 1]
    e00, e10 = _exp_o0[:, 0], _exp_o0[:, 1]
    e01, e11 = _exp_o1[:, 0], _exp_o1[:, 1]

    for t in range(n_info_bits):
        r0, r1 = rx_bits[2 * t], rx_bits[2 * t + 1]
        bm0 = (e00 ^ r0) + (e01 ^ r1)
        bm1 = (e10 ^ r0) + (e11 ^ r1)
        cand0 = pm[ps0] + bm0
        cand1 = pm[ps1] + bm1
        pm = np.minimum(cand0, cand1)
        tb[t] = (cand1 < cand0).astype(np.int8)

    st = int(np.argmin(pm))
    decoded = np.zeros(n_info_bits, dtype=np.int8)
    for t in range(n_info_bits - 1, -1, -1):
        b = tb[t, st]
        decoded[t] = _inp_bit[st, b]
        st = _prev_state[st, b]
    return decoded


def cc_decode(encoded_bytes, n_info_bits, n_passes=2):
    rx_bits = np.unpackbits(np.frombuffer(encoded_bytes, dtype=np.uint8))
    tiled = np.tile(rx_bits, n_passes)
    decoded = _viterbi_core(tiled, n_info_bits * n_passes, 0)
    return np.packbits(decoded[-n_info_bits:].astype(np.uint8)).tobytes()


RS_NSYM = 32
RS_N = 255
RS_K = RS_N - RS_NSYM
RS_T = RS_NSYM // 2

_rsc = None


def _rs():
    global _rsc
    if _rsc is None:
        try:
            import reedsolo
        except ImportError:
            raise SystemExit("reedsolo gerekli:  pip install reedsolo")
        _rsc = reedsolo.RSCodec(RS_NSYM)
    return _rsc


TX_HOST = '127.0.0.1'

CHANNELS = {
    1: {'TX': 5001, 'EVM': 5002, 'RX': [5003, 5004, 5005, 5006]},
    2: {'TX': 5007, 'EVM': 5008, 'RX': [5009, 5010, 5011, 5012]},
    3: {'TX': 5013, 'EVM': 5014, 'RX': [5015, 5016, 5017, 5018]},
    4: {'TX': 5019, 'EVM': 5020, 'RX': [5021, 5022, 5023, 5024]},
}
PORT_NAMES = {0: '0deg', 1: '90deg', 2: '180deg', 3: '270deg'}

CW_BYTE = 0x00
ALT_BYTE = 0x33

ASM = bytes([0x1A, 0xCF, 0xFC, 0x1D, 0xAA, 0x55, 0xDE, 0xAD])
ASM_LEN = len(ASM)
MAX_ASM_ERRS = 6

HDR_LEN = 6

SHOW_MAX = 300
DEDUPE_TTL = 30.0
REASM_TTL = 20.0

_POPCNT = bytes(bin(i).count('1') for i in range(256))

lock = threading.Lock()
stop_listeners = False
reasm = {}
seen_bursts = {}
latest_evm = {'evm_pct': None, 'snr_db': None}
evm_buffer = []
evm_lock = threading.Lock()


def bit_diff(a, b):
    return sum(_POPCNT[x ^ y] for x, y in zip(a, b))


def sanitize(s):
    return ''.join(c if (c.isprintable() or c in ' \t\n') else '\u00b7' for c in s)


def fmt_snr(v):
    return "--.-" if v is None else f"{v:.1f}"


class FecMode:
    def __init__(self, name):
        self.name = name
        if name == 'rs':
            self.info_len = RS_K
            self.cw_len = RS_N
        elif name == 'cc':
            self.info_len = 256
            self.cw_len = 512
        else:
            raise ValueError(name)
        self.payload_len = self.info_len - HDR_LEN
        self.wire_len = ASM_LEN + self.cw_len

    def encode(self, info):
        assert len(info) == self.info_len
        if self.name == 'rs':
            return bytes(_rs().encode(info))
        return cc_encode(info)

    def decode(self, cw):
        if self.name == 'rs':
            import reedsolo
            try:
                out = _rs().decode(cw)
                info = bytes(out[0])
                n_corr = len(out[2]) if len(out) > 2 else -1
                if len(info) == RS_K:
                    return info, n_corr, 'OK'
            except reedsolo.ReedSolomonError:
                pass
            return cw[:RS_K], -1, 'BOZUK'
        else:
            try:
                info = cc_decode(cw, self.info_len * 8, n_passes=2)
                return info, -1, 'OK'
            except Exception:
                return bytes(self.info_len), -1, 'BOZUK'


def build_preamble(cw_syms, alt_syms, pn_syms, seed=0xA5):
    def nbytes(n_syms):
        return max(0, (n_syms + 3) // 4)

    cw = bytes([CW_BYTE]) * nbytes(cw_syms)
    alt = bytes([ALT_BYTE]) * nbytes(alt_syms)

    rng = np.random.default_rng(seed)
    pn = rng.integers(0, 256, nbytes(pn_syms), dtype=np.uint8).tobytes()

    return cw + alt + cw + alt + pn


def build_burst(text, seq, fec, preamble, tail_bytes, max_frames):
    raw = text.encode('utf-8')
    total_len = len(raw)

    chunks = [raw[i:i + fec.payload_len]
              for i in range(0, max(len(raw), 1), fec.payload_len)] or [b'']

    dropped = 0
    if len(chunks) > max_frames:
        dropped = len(chunks) - max_frames
        chunks = chunks[:max_frames]

    frag_tot = len(chunks)
    sent_bytes = sum(len(c) for c in chunks)

    body = bytearray()
    for idx, chunk in enumerate(chunks):
        payload = chunk.ljust(fec.payload_len, b'\x00')
        info = struct.pack('>HBBH', seq & 0xFFFF, idx, frag_tot, len(chunk)) + payload
        body += ASM + fec.encode(bytes(info))

    burst = preamble + bytes(body) + bytes([CW_BYTE]) * tail_bytes
    return burst, frag_tot, sent_bytes, total_len, dropped


def find_asm(buf, start):
    limit = len(buf) - ASM_LEN
    for i in range(start, limit + 1):
        if bit_diff(buf[i:i + ASM_LEN], ASM) <= MAX_ASM_ERRS:
            return i
    return -1


def handle_fragment(info, n_corr, status, branch, fec):
    seq, idx, tot, tlen = struct.unpack_from('>HBBH', info, 0)
    payload = info[HDR_LEN:]

    if tot == 0 or idx >= tot or tlen > fec.payload_len:
        return

    chunk = payload[:tlen]
    now = time.time()

    with lock:
        for k, v in list(reasm.items()):
            if now - v['ts'] > REASM_TTL:
                _flush(k, fec, timeout=True)

        ent = reasm.setdefault(seq, {'tot': tot, 'parts': {}, 'ts': now,
                                     'status': {}, 'branch': branch})
        ent['ts'] = now
        prev_status = ent['status'].get(idx)
        if prev_status != 'OK':
            ent['parts'][idx] = chunk
            ent['status'][idx] = status
            ent['corr'] = n_corr

        complete = len(ent['parts']) == ent['tot']

    if complete:
        _flush(seq, fec)


def _flush(seq, fec, timeout=False):
    ent = reasm.pop(seq, None)
    if ent is None:
        return

    key = (seq, tuple(sorted(ent['parts'].items())))
    now = time.time()
    for k, ts in list(seen_bursts.items()):
        if now - ts > DEDUPE_TTL:
            del seen_bursts[k]
    if key in seen_bursts:
        return
    seen_bursts[key] = now

    pieces = []
    missing = []
    for i in range(ent['tot']):
        if i in ent['parts']:
            pieces.append(ent['parts'][i])
        else:
            missing.append(i)
            pieces.append(b'[...KAYIP PARCA...]')

    text = b''.join(pieces).decode('utf-8', errors='replace')
    n_bozuk = sum(1 for s in ent['status'].values() if s != 'OK')

    tag = "[TAM]" if not missing and n_bozuk == 0 else "[EKSIK]"
    shown = sanitize(text)
    if len(shown) > SHOW_MAX:
        shown = shown[:SHOW_MAX] + f" ...(+{len(text)-SHOW_MAX} karakter)"

    snr = latest_evm['snr_db']
    print(f"\n[RX] {tag} Seq: {seq}  ({len(ent['parts'])}/{ent['tot']} parca, "
          f"kol: {ent['branch']})")
    print(f"> {shown}")
    det = []
    if missing:
        det.append(f"kayip parca: {missing}")
    if n_bozuk:
        det.append(f"FEC cozemedi: {n_bozuk} parca")
    if timeout:
        det.append("zaman asimi ile basildi")
    det.append(f"SNR: {fmt_snr(snr)} dB")
    print(f"[Stat] {' | '.join(det)}\n")


def rx_listener(port, name, fec):
    s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    s.settimeout(2.0)
    try:
        s.connect((TX_HOST, port))
    except (ConnectionRefusedError, socket.timeout):
        return

    buf = bytearray()
    buf_max = 8 * fec.wire_len
    try:
        while not stop_listeners:
            try:
                chunk = s.recv(8192)
            except socket.timeout:
                chunk = None
            if chunk is not None:
                if not chunk:
                    break
                buf.extend(chunk)

            while True:
                idx = find_asm(buf, 0)
                if idx < 0:
                    if len(buf) > ASM_LEN - 1:
                        del buf[:len(buf) - (ASM_LEN - 1)]
                    break
                if idx + fec.wire_len > len(buf):
                    del buf[:idx]
                    break

                cw = bytes(buf[idx + ASM_LEN: idx + fec.wire_len])
                info, n_corr, status = fec.decode(cw)
                handle_fragment(info, n_corr, status, name, fec)
                del buf[:idx + fec.wire_len]

            if len(buf) > buf_max:
                del buf[:len(buf) - buf_max]
    finally:
        s.close()


CONSTEL = [complex(1, 1), complex(-1, 1), complex(-1, -1), complex(1, -1)]
CONSTEL_R = math.sqrt(2.0)


def compute_evm_snr(samples):
    if len(samples) < 16:
        return None, None
    mx = max(abs(s) for s in samples)
    if mx < 1e-4:
        return None, None
    active = [s for s in samples if abs(s) > 0.30 * mx]
    if len(active) < 16:
        return None, None
    avg = sum(abs(s) for s in active) / len(active)
    if avg < 1e-6:
        return None, None
    norm = [s * (CONSTEL_R / avg) for s in active]

    best = float('inf')
    for k in range(4):
        rot = complex(math.cos(k * math.pi / 2), math.sin(k * math.pi / 2))
        err = ref = 0.0
        for s in norm:
            r = s * rot
            ideal = min(CONSTEL, key=lambda p: abs(r - p))
            err += abs(r - ideal) ** 2
            ref += abs(ideal) ** 2
        if ref > 0:
            best = min(best, err / ref)
    if best == float('inf'):
        return None, None
    evm = math.sqrt(max(best, 1e-12))
    return evm * 100.0, -20.0 * math.log10(evm)


def evm_listener(port):
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
            n = len(buf) // 8
            if n <= 0:
                continue
            new = [complex(*struct.unpack_from('<ff', buf, i * 8)) for i in range(n)]
            del buf[:n * 8]
            with evm_lock:
                evm_buffer.extend(new)
                if len(evm_buffer) > 4000:
                    del evm_buffer[:len(evm_buffer) - 4000]
    finally:
        sock.close()


def evm_compute_thread():
    while not stop_listeners:
        time.sleep(0.4)
        with evm_lock:
            samp = list(evm_buffer)
        pct, snr = compute_evm_snr(samp)
        if pct is not None:
            latest_evm.update(evm_pct=pct, snr_db=snr)


def selftest(fec, preamble, tail, max_frames):
    import random
    random.seed(0)
    print(f"Self-test -- FEC: {fec.name.upper()}")
    print(f"  payload/frame : {fec.payload_len} B")
    print(f"  wire/frame    : {fec.wire_len} B  (ASM {ASM_LEN} + cw {fec.cw_len})")
    print(f"  preamble      : {len(preamble)} B")
    print(f"  max frames    : {max_frames}\n")

    for txt, label in [("kisa mesaj", "tek frame"),
                       ("A" * (fec.payload_len * 3 + 10), "cok frame"),
                       ("B" * (fec.payload_len * (max_frames + 5)), "tasan")]:
        burst, nfr, sent, total, dropped = build_burst(
            txt, 7, fec, preamble, tail, max_frames)
        print(f"  {label:10s}: {total:6d} B metin -> {nfr} frame, "
              f"{sent} B gonderildi, {total-sent} B dusuruldu, "
              f"burst {len(burst)} B")

    if fec.name != 'rs':
        print("\n  (hata enjeksiyon testi sadece RS icin)")
        return

    print("\n  RS hata dayanimi (tek frame, 217B metin):")
    ref = "X" * 60
    burst, *_ = build_burst(ref, 1, fec, b'', 0, 1)
    frame = burst[ASM_LEN:]
    for n_err in (0, 8, 16, 17, 25):
        ok = 0
        for _ in range(100):
            b = bytearray(frame)
            for i in random.sample(range(len(b)), n_err):
                b[i] ^= random.randint(1, 255)
            _, _, status = fec.decode(bytes(b))
            ok += (status == 'OK')
        print(f"    {n_err:3d} sembol hatasi -> {ok:3d}/100 cozuldu")

    print("\n  Yanlis faz kolunda sahte ASM:")
    hit = sum(1 for _ in range(2000)
              if find_asm(bytearray(os.urandom(fec.wire_len)), 0) >= 0)
    print(f"    2000 rastgele blokta ASM eslesmesi: {hit}")


def main():
    global stop_listeners

    ap = argparse.ArgumentParser(description="QPSK Burst Chat (RS / CC FEC)")
    ap.add_argument('--channel', type=int, choices=[1, 2, 3, 4], default=1)
    ap.add_argument('--fec', choices=['rs', 'cc'], default='rs')
    ap.add_argument('--symrate', type=float, default=2400,
                    help="QPSK sembol hizi (sym/s). Burst suresi hesabi icin.")
    ap.add_argument('--burst-sec', type=float, default=1.0,
                    help="Bir burst icin ayrilan azami sure (sn).")
    ap.add_argument('--cw-syms', type=int, default=256,
                    help="Preamble'daki modulasyonsuz tasiyici sembol sayisi.")
    ap.add_argument('--alt-syms', type=int, default=256,
                    help="Preamble'daki alternatif (saat) sembol sayisi.")
    ap.add_argument('--pn-syms', type=int, default=128,
                    help="ASM oncesi sozde-rastgele sembol sayisi.")
    ap.add_argument('--tail-syms', type=int, default=64,
                    help="Burst sonundaki bosaltma sembolu sayisi.")
    ap.add_argument('--repeat', type=int, default=1,
                    help="Ayni burst'u kac kez gonderelim (tekrar kazanci).")
    ap.add_argument('--loop', action='store_true',
                    help="Mesaji bir kez yaz, Ctrl+C'ye kadar surekli gonder.")
    ap.add_argument('--gap', type=float, default=0.5,
                    help="Loop modunda burst'ler arasi bekleme (sn).")
    ap.add_argument('--selftest', action='store_true')
    args = ap.parse_args()

    fec = FecMode(args.fec)
    preamble = build_preamble(args.cw_syms, args.alt_syms, args.pn_syms)
    tail = max(0, (args.tail_syms + 3) // 4)

    bytes_per_sec = args.symrate / 4.0
    budget = int(args.burst_sec * bytes_per_sec) - len(preamble) - tail
    max_frames = max(1, budget // fec.wire_len)

    pre_sec = (len(preamble) * 4) / args.symrate

    if args.selftest:
        selftest(fec, preamble, tail, max_frames)
        return

    cfg = CHANNELS[args.channel]

    print('=' * 78)
    print(f'  QPSK BURST CHAT  --  FEC: {fec.name.upper()}  Kanal: {args.channel}')
    print(f'  Preamble : {len(preamble)} B  ({len(preamble)*4} sembol, '
          f'~{pre_sec*1000:.0f} ms @ {args.symrate:.0f} sym/s)')
    print(f'  Frame    : {fec.payload_len} B faydali yuk / {fec.wire_len} B wire')
    print(f'  Burst    : en fazla {max_frames} frame '
          f'= {max_frames*fec.payload_len} B metin ({args.burst_sec:.1f} sn butce)')
    if args.repeat > 1:
        print(f'  Tekrar   : her mesaj {args.repeat} kez gonderilecek')
    print(f'  Cikis    : "quit" / "exit" / "q"')
    print('=' * 78 + '\n')

    threading.Thread(target=evm_listener, args=(cfg['EVM'],), daemon=True).start()
    threading.Thread(target=evm_compute_thread, daemon=True).start()
    for i, port in enumerate(cfg['RX']):
        threading.Thread(target=rx_listener, args=(port, PORT_NAMES[i], fec),
                         daemon=True).start()

    time.sleep(1.0)

    tx = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    tx.setsockopt(socket.IPPROTO_TCP, socket.TCP_NODELAY, 1)
    try:
        tx.connect((TX_HOST, cfg['TX']))
    except ConnectionRefusedError:
        print(f"[!] TX portuna ({cfg['TX']}) baglanilamadi. GRC acik mi?")
        return

    seq = 1
    try:
        while True:
            text = input("Mesajini yaz > ")
            if text.lower() in ('quit', 'exit', 'q'):
                break
            if not text:
                continue

            burst, nfr, sent, total, dropped = build_burst(
                text, seq, fec, preamble, tail, max_frames)
            dur = (len(burst) * 4) / args.symrate

            if dropped:
                print(f"[i] Metin {total} B, kapasite {sent} B. "
                      f"Ilk {sent} B alindi, gerisi atildi, sonu 0x00 dolgulu.")

            if not args.loop:
                for r in range(args.repeat):
                    tx.sendall(burst)
                    if r + 1 < args.repeat:
                        time.sleep(0.2)
                print(f"[TX] Seq {seq}: {nfr} frame, {sent} B, "
                      f"burst {len(burst)} B (~{dur:.2f} sn) | "
                      f"SNR: {fmt_snr(latest_evm['snr_db'])} dB")
                seq += 1
                time.sleep(0.3)
                continue

            print(f"[TX] LOOP basladi: {nfr} frame, {sent} B, "
                  f"burst {len(burst)} B (~{dur:.2f} sn), "
                  f"arada {args.gap:.1f} sn. Durdurmak icin Ctrl+C.")
            n = 0
            try:
                while True:
                    burst, *_ = build_burst(text, seq, fec, preamble,
                                            tail, max_frames)
                    tx.sendall(burst)
                    n += 1
                    seq = (seq + 1) & 0xFFFF
                    print(f"\r[TX] burst #{n}  seq {seq}  "
                          f"SNR: {fmt_snr(latest_evm['snr_db'])} dB   ",
                          end='', flush=True)
                    time.sleep(args.gap)
            except KeyboardInterrupt:
                print(f"\n[*] LOOP durduruldu. Toplam {n} burst gonderildi.\n")
                continue

    except KeyboardInterrupt:
        print("\n[*] Ctrl+C.")
    finally:
        stop_listeners = True
        tx.close()
        print("[*] Kapatildi.")


if __name__ == "__main__":
    main()
