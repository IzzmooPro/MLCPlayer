"""CLAUDE.md kuralini mekanik bariyere cevirir.

Kural: "Kirli calisma agacini koru; stash, reset, checkout veya kullanici
degisikliklerini geri alan komutlar kullanma."

Bu hook o komutlari PreToolUse asamasinda reddeder. Kural olarak yazili
olmasi yeterli degildi: unutulabilir bir kural, saatlerce suren isi tek
komutla geri alabilir.

Kapsam DAR tutulur: yalniz `git` kelimesinin hemen ardindan (istege bagli
`-c anahtar=deger` ciftlerinden sonra) gelen alt komut denetlenir. Boylece
`git commit -m "reset the band"` gibi masum komutlar engellenmez.
"""
import json
import re
import sys

BLOCKED = ("stash", "reset", "checkout", "restore")

# `git`, sonra istege bagli `-c k=v` ciftleri, sonra ALT KOMUT.
PATTERN = re.compile(
    r"\bgit\b(?:\s+-c\s+\S+)*\s+(" + "|".join(BLOCKED) + r")\b")


def main():
    try:
        payload = json.load(sys.stdin)
    except Exception:
        return 0
    command = (payload.get("tool_input") or {}).get("command") or ""
    match = PATTERN.search(command)
    if not match:
        return 0
    verb = match.group(1)
    reason = (
        f"ENGELLENDI: `git {verb}` calisma agacindaki degisiklikleri geri "
        "alabilir.\n"
        "CLAUDE.md kurali: kirli calisma agacini koru; stash/reset/checkout/"
        "restore kullanma.\n"
        "Gercekten gerekiyorsa kullaniciya sor ve komutu KULLANICI calistirsin."
    )
    json.dump({
        "hookSpecificOutput": {
            "hookEventName": "PreToolUse",
            "permissionDecision": "deny",
            "permissionDecisionReason": reason,
        }
    }, sys.stdout)
    return 0


if __name__ == "__main__":
    sys.exit(main())
