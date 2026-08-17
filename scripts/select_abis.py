# Build only the ABIs we actually ship.
#
# The client declares no abiFilters, so AGP builds all four. That is not just
# waste: each ABI needs its own Rust target installed, and the run that finally
# got past arm64 died on x86 - an ABI no device in our fleet uses. Trimming is
# the product decision and the fix at the same time.
#
# Kept out of the client repo on purpose. The client is upstream's; the choice
# of which ABIs our app ships is ours, and it belongs on our side of the line -
# same reasoning as scripts/drop_dns_libs.py.
import io
import os
import sys

root = sys.argv[1] if len(sys.argv) > 1 else "client"
abis = (sys.argv[2] if len(sys.argv) > 2 else "arm64-v8a,armeabi-v7a").split(",")
abis = [a.strip() for a in abis if a.strip()]

rel = "platform/android/lib/build.gradle.kts"
path = os.path.join(root, rel)
lines = io.open(path, encoding="utf-8").read().split("\n")

if any("abiFilters" in l for l in lines):
    print("  already has abiFilters, leaving it alone")
    raise SystemExit(0)

# Anchor on minSdk: it is inside defaultConfig, appears once, and is plain
# text with nothing to escape. Assert rather than assume - a silent miss here
# would look exactly like success and cost another 25-minute run to discover.
hits = [i for i, l in enumerate(lines) if l.strip().startswith("minSdk")]
assert len(hits) == 1, "expected exactly one minSdk line, found %d" % len(hits)
at = hits[0]

indent = lines[at][: len(lines[at]) - len(lines[at].lstrip())]
quoted = ", ".join('"%s"' % a for a in abis)
block = [
    indent + "// Injected: the ABIs our app ships. Upstream builds all four.",
    indent + "ndk {",
    indent + "    abiFilters += listOf(" + quoted + ")",
    indent + "}",
]
lines[at + 1 : at + 1] = block

io.open(path, "w", encoding="utf-8", newline="").write("\n".join(lines))
print("  patched %s -> %s" % (rel, ", ".join(abis)))

# Prove it landed where it was meant to, not merely that the file changed.
after = io.open(path, encoding="utf-8").read()
assert "abiFilters" in after, "wrote the file but the filter is not in it"
for a in abis:
    assert '"%s"' % a in after, "missing %s" % a
print("  verified")
