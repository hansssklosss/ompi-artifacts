#!/usr/bin/env python3
"""
ompi listing-59 artifact — negative tests (falsifier) for verify_offline.py.

Each case mutates one public document, runs the verifier in offline mode,
and asserts that the run FAILS on the expected check. A verifier that passes
a mutated document is broken in the direction it exists to refuse.

Usage: python3 negatives.py   (offline: no network)
"""
import json
import shutil
import subprocess
import sys
import tempfile

PY = sys.argv[1] if len(sys.argv) > 1 else "/root/1f916/venv/bin/python"
VERIFIER = "verify_offline.py"


def flip_hex(s, pos=None):
    h = "0123456789abcdef"
    i = len(s) - 2 if pos is None else pos
    c = h[(h.index(s[i]) + 1) % 16]
    return s[:i] + c + s[i + 1:]


B64U = "ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz0123456789-_"


def flip_b64u(s, pos=None):
    i = len(s) - 2 if pos is None else pos
    c = B64U[(B64U.index(s[i]) + 1) % 64]
    return s[:i] + c + s[i + 1:]


def mutate_receipt(fn):
    d = json.load(open("raw/receipt.json"))
    fn(d)
    return d


CASES = []


def case(name, expect_substr):
    def deco(fn):
        CASES.append((name, fn, expect_substr))
        return fn
    return deco


@case("T1 proof: flip one hex digit of proof[0]", "exactly one index")
def _t1(d):
    d["inclusion"]["proof"][0]["hash"] = flip_hex(d["inclusion"]["proof"][0]["hash"])


@case("T2 signed_head: flip one signature char", "signed_head ES256")
def _t2(d):
    sig = d["inclusion"]["signed_head"]["signature"]
    d["inclusion"]["signed_head"]["signature"] = flip_b64u(sig, len(sig) // 2)


@case("T3 head payload: swap root for another 64-hex", "signed_head ES256")
def _t3(d):
    import base64
    h, p, s = d["inclusion"]["signed_head"]["signature"].split(".")
    payload = json.loads(base64.urlsafe_b64decode(p + "=" * (-len(p) % 4)))
    payload["root"] = "00" * 32
    pad = lambda x: base64.urlsafe_b64encode(json.dumps(x, separators=(",", ":")).encode()).decode().rstrip("=")
    d["inclusion"]["signed_head"]["signature"] = f"{h}.{pad(payload)}.{s}"


@case("T4 leaf_hash: replace with a valid 64-hex of another leaf", "exactly one index")
def _t4(d):
    d["inclusion"]["leaf_hash"] = "ab" * 32


@case("T5 issued_at: move before not_before", "not_before")
def _t5(d):
    d["issued_at"] = "2026-09-01T00:00:00.000Z"


@case("T6 proof: drop one step (wrong length for index/size)", "exactly one index")
def _t6(d):
    del d["inclusion"]["proof"][3]


def mutate_history(fn):
    d = json.load(open("raw/issuer-history.json"))
    fn(d)
    return d


def mutate_history_entry_hash(d):
    d["entries"][0]["entry_hash"] = flip_hex(d["entries"][0]["entry_hash"])


def mutate_history_sig(d):
    p = d["issuer_signature"]["jws"].split(".")
    p[2] = flip_b64u(p[2], len(p[2]) // 2)
    d["issuer_signature"]["jws"] = ".".join(p)


def mutate_history_window(d):
    d["entries"][0]["not_before"] = "2026-10-18T00:00:00Z"


def mutate_jwks_key(d):
    d["keys"][0]["x"] = flip_b64u(d["keys"][0]["x"])


def mutate_inc_index(d):
    d["leaf_index"] = 29


def mutate_epoch_sig(d):
    p = d["issuer_signature"]["jws"].split(".")
    p[2] = flip_b64u(p[2], len(p[2]) // 2)
    d["issuer_signature"]["jws"] = ".".join(p)


HISTORY_CASES = [
    ("T7 history: flip one entry_hash digit", mutate_history_entry_hash, "entry hash chain"),
    ("T8 history: flip one signature bit", mutate_history_sig, "history sealed-snapshot"),
    ("T9 history: not_after receipt (not_before moves past issued_at)",
     mutate_history_window, "not_before"),
    ("T10 jwks: flip one key-coordinate digit", mutate_jwks_key, "thumbprint"),
    ("T11 inclusion endpoint: leaf_index 30 -> 29", mutate_inc_index, "leaf_index"),
    ("T12 epoch record: flip one signature bit", mutate_epoch_sig, "epoch record issuer JWS"),
]


def main():
    ok = True
    for name, prepare, expect in CASES:
        doc = json.load(open("raw/receipt.json"))
        with tempfile.TemporaryDirectory() as td:
            shutil.copytree("raw", f"{td}/raw")
            prepare(doc)
            with open(f"{td}/raw/receipt.json", "w") as f:
                json.dump(doc, f)
            r = subprocess.run([PY, VERIFIER, f"{td}/raw", "--no-chain"],
                               capture_output=True, text=True)
        hit = any(expect in line for line in r.stdout.splitlines() if line.startswith("FAIL"))
        status = "OK  " if (r.returncode == 1 and hit) else "BAD "
        if not (r.returncode == 1 and hit):
            ok = False
        print(f"{status} {name}")
        if not (r.returncode == 1 and hit):
            for line in r.stdout.splitlines():
                if line.startswith(("FAIL", "== RESULT")):
                    print("       ", line)
    for name, prepare, expect in HISTORY_CASES:
        which = "history" if "history" in name else ("jwks" if "jwks" in name
               else ("inc" if "inclusion" in name else "epoch"))
        src = {"history": "raw/issuer-history.json", "jwks": "raw/jwks.json",
               "inc": "raw/inclusion.json", "epoch": "raw/epoch.json"}[which]
        doc = json.load(open(src))
        with tempfile.TemporaryDirectory() as td:
            shutil.copytree("raw", f"{td}/raw")
            prepare(doc)
            with open(f"{td}/raw/{src.split('/', 1)[1]}", "w") as f:
                json.dump(doc, f)
            r = subprocess.run([PY, VERIFIER, f"{td}/raw", "--no-chain"],
                               capture_output=True, text=True)
        hit = any(expect in line for line in r.stdout.splitlines() if line.startswith("FAIL"))
        status = "OK  " if (r.returncode == 1 and hit) else "BAD "
        if not (r.returncode == 1 and hit):
            ok = False
        print(f"{status} {name}")
        if not (r.returncode == 1 and hit):
            for line in r.stdout.splitlines():
                if line.startswith(("FAIL", "== RESULT")):
                    print("       ", line)
    print()
    print("NEGATIVES:", "ALL FIRE" if ok else "SOME DID NOT FIRE")
    sys.exit(0 if ok else 1)


if __name__ == "__main__":
    main()
