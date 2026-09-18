# QPSK Text Chat Scripts

- `textentry_RS.py` — continuous mode, one Reed-Solomon frame per message.
- `textentry_burst.py` — burst mode with preamble, RS or convolutional FEC, can split long messages into multiple frames.

## Requirements

```bash
pip install reedsolo
pip install numpy   # only for textentry_burst.py
```

GNU Radio flowgraph must already be running before you start either script.

## Usage

```bash
python textentry_RS.py --channel 1
python textentry_RS.py --selftest

python textentry_burst.py --channel 1 --fec rs
python textentry_burst.py --selftest
```

Type a message + Enter to send. Type `quit` / `exit` / `q` to stop.

Burst mode extra options: `--fec cc`, `--symrate`, `--burst-sec`, `--repeat`, `--loop --gap`.
