import os, hashlib, re

keys = [
    "SERVICE_BUS_CONN",
    "AZ_SB_CONN_STR",
    "AZURE_SERVICE_BUS_CONNECTION",
    "AZURE_SERVICE_BUS_CONNECTION_STRING",
    "AZURE_STORAGE_CONNECTION_STRING"
]
for k in keys:
    v = os.getenv(k) or ""
    if not v:
        print(f"{k}: NOT set")
        continue

    flags = {
        "has_newline": ("\n" in v) or ("\r" in v),
        "has_quotes": (v[:1] in "'\"") or (v[-1:] in "'\""),
        "len": len(v)
    }
    
    # Simple hash of the value to verify identity without leaking it
    val_hash = hashlib.sha256(v.encode("utf-8")).hexdigest()[:12]

    print(f"{k}: val_hash={val_hash} flags={flags}")
