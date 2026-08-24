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

BLOCKED = ("stash", "reset", "checkout", "restore", "clean")
VALUE = r'(?:"[^"]*"|\'[^\']*\'|\S+)'
GLOBAL_OPTION = (
    r"(?:-c\s+" + VALUE +
    r"|-C\s+" + VALUE +
    r"|--(?:git-dir|work-tree|namespace|super-prefix|config-env)"
    r"(?:=" + VALUE + r"|\s+" + VALUE + r")"
    r"|--[A-Za-z][\w-]*(?:=" + VALUE + r")?"
    r"|-[pP])"
)
COMMAND = re.compile(
    r"\bgit(?:\.exe)?\b(?:\s+" + GLOBAL_OPTION + r")*\s+"
    r"(?P<verb>" + "|".join(BLOCKED) + r"|switch)\b"
    r"(?P<tail>[^;&|\r\n]*)",
    re.IGNORECASE,
)


def blocked_action(command):
    """Return the destructive Git action embedded in *command*, if any."""
    for match in COMMAND.finditer(command):
        verb = match.group("verb").lower()
        if verb in BLOCKED:
            return verb
        tail = match.group("tail")
        if re.search(r"(?:^|\s)(?:-f|--force|--discard-changes)(?:\s|$)",
                     tail, re.IGNORECASE):
            return "switch --discard-changes"
    return None


def main():
    try:
        payload = json.load(sys.stdin)
    except Exception:
        return 0
    command = (payload.get("tool_input") or {}).get("command") or ""
    verb = blocked_action(command)
    if not verb:
        return 0
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
