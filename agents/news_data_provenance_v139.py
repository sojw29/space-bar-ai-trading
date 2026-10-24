"""V139 offline content provenance manifests for news research comparisons.

SHA-256 identifies exact input bytes and explicitly recorded settings. Matching
manifests prove input equality only, NOT historical availability or causality.
"""
import argparse
import hashlib
import json
from pathlib import Path

MAX_BYTES=20_000_000
ROLES=("raw_news","ohlcv_csv","taxonomy","event_study","clusters")
SETTINGS=("topic","observed_at","min_samples","cluster_window_minutes")

def digest(path):
    path=Path(path)
    if not path.is_file():
        raise ValueError("MISSING_INPUT_FILE")
    if path.stat().st_size>MAX_BYTES:
        raise ValueError("INPUT_TOO_LARGE")
    h=hashlib.sha256()
    with path.open("rb") as stream:
        while True:
            chunk=stream.read(65536)
            if not chunk:
                break
            h.update(chunk)
    return {"sha256":h.hexdigest(),"bytes":path.stat().st_size}

def manifest(files,settings):
    if not isinstance(files,dict) or set(files)!=set(ROLES):
        raise ValueError("INVALID_INPUT_ROLES")
    if not isinstance(settings,dict) or set(settings)!=set(SETTINGS):
        raise ValueError("INVALID_SETTINGS")
    if any(not isinstance(settings[k],str) or not settings[k].strip() for k in ("topic","observed_at")):
        raise ValueError("INVALID_SETTINGS")
    if settings["topic"] not in ("BTC","ETH","SOL","MACRO"):
        raise ValueError("INVALID_TOPIC")
    if any(type(settings[k]) is not int or settings[k]<1 for k in ("min_samples","cluster_window_minutes")):
        raise ValueError("INVALID_SETTINGS")
    if settings["cluster_window_minutes"]>1440:
        raise ValueError("INVALID_SETTINGS")
    hashes={role:digest(files[role]) for role in ROLES}
    canonical=json.dumps({"inputs":hashes,"settings":settings},sort_keys=True,
                         separators=(",",":"),ensure_ascii=False).encode("utf-8")
    return {"version":"V139.0","status":"INPUT_BYTES_AND_SETTINGS_MANIFEST",
            "inputs":hashes,"settings":dict(settings),
            "manifest_sha256":hashlib.sha256(canonical).hexdigest(),
            "original_news_publication_verified":False,
            "first_tradable_availability_verified":False,
            "research_only":True,"exchange_connected":False,
            "orders_submitted_to_exchange":0,"live_trading_approved":False,
            "limitations":"Hashes prove exact bytes for explicitly supplied files and equality of declared settings only. No proof of collection time, data authenticity, original publication time, independence, causality or strategy performance."}

def compare(left,right):
    for item in (left,right):
        if not isinstance(item,dict) or item.get("version")!="V139.0":
            raise ValueError("INVALID_MANIFEST")
        if set(item.get("inputs",{}))!=set(ROLES) or set(item.get("settings",{}))!=set(SETTINGS):
            raise ValueError("INVALID_MANIFEST")
        expected=hashlib.sha256(json.dumps({"inputs":item["inputs"],"settings":item["settings"]},
            sort_keys=True,separators=(",",":"),ensure_ascii=False).encode("utf-8")).hexdigest()
        if item.get("manifest_sha256")!=expected:
            raise ValueError("MANIFEST_DIGEST_MISMATCH")
    input_matches={role:left["inputs"][role]==right["inputs"][role] for role in ROLES}
    setting_matches={key:left["settings"][key]==right["settings"][key] for key in SETTINGS}
    return {"version":"V139.0","status":"PROVENANCE_EQUALITY_CHECK",
            "exact_input_and_settings_match":all(input_matches.values()) and all(setting_matches.values()),
            "input_matches":input_matches,"setting_matches":setting_matches,
            "first_tradable_availability_verified":False,"research_only":True,
            "orders_submitted_to_exchange":0,"live_trading_approved":False,
            "limitations":"Matching digests indicate identical supplied bytes/settings, not reliable source timestamps, publication provenance, causal evidence or validated edge."}

def main():
    p=argparse.ArgumentParser(description="V139 offline SHA256 news research input manifest")
    sub=p.add_subparsers(dest="action",required=True)
    create=sub.add_parser("create")
    for role in ROLES:
        create.add_argument("--"+role.replace("_","-"),required=True,type=Path)
    create.add_argument("--topic",choices=["BTC","ETH","SOL","MACRO"],required=True)
    create.add_argument("--observed-at",required=True)
    create.add_argument("--min-samples",type=int,default=5)
    create.add_argument("--cluster-window-minutes",type=int,default=60)
    create.add_argument("--output",required=True,type=Path)
    check=sub.add_parser("compare")
    check.add_argument("left",type=Path)
    check.add_argument("right",type=Path)
    check.add_argument("--output",type=Path)
    args=p.parse_args()
    if args.action=="create":
        result=manifest({role:getattr(args,role) for role in ROLES},
            {key:getattr(args,key) for key in SETTINGS})
    else:
        for path in (args.left,args.right):
            if path.stat().st_size>MAX_BYTES:
                raise ValueError("INPUT_TOO_LARGE")
        result=compare(json.loads(args.left.read_text(encoding="utf-8")),
                       json.loads(args.right.read_text(encoding="utf-8")))
    encoded=json.dumps(result,indent=2,ensure_ascii=False)+"\n"
    if args.output:
        args.output.parent.mkdir(parents=True,exist_ok=True)
        args.output.write_text(encoded,encoding="utf-8")
    else:
        print(encoded,end="")
    return 0

if __name__=="__main__":
    raise SystemExit(main())
