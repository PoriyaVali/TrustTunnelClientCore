# Lower the AAR's minimum Android version.
#
# Upstream builds at minSdk 26 (Android 8.0). Our app supports 24 (Android
# 7.0), and an AAR declaring 26 fails the manifest merger outright:
#
#   uses-sdk:minSdkVersion 24 cannot be smaller than version 26
#   declared in library [trusttunnel-client.aar]
#
# The alternatives were to raise the whole app to 26 - dropping Android 7
# phones from every core, not just this one - or to force the merge and gate
# the core at runtime. The owner chose to rebuild instead, which is only an
# option because the build is ours now.
#
# ⚠️ This is the one change here that is not merely mechanical: it asks the C++
# to compile against an API level AdGuard never targeted. If the native code
# uses something introduced in 25 or 26, this fails at compile time - which is
# the good outcome, because the alternative is discovering it on a phone.
import io
import os
import sys

root = sys.argv[1] if len(sys.argv) > 1 else "client"
target = sys.argv[2] if len(sys.argv) > 2 else "24"

rel = "platform/android/lib/build.gradle.kts"
path = os.path.join(root, rel)
lines = io.open(path, encoding="utf-8").read().split("\n")

hits = [i for i, l in enumerate(lines) if l.strip().startswith("minSdk")]
assert len(hits) == 1, "expected exactly one minSdk line, found %d" % len(hits)

at = hits[0]
old = lines[at].strip()
indent = lines[at][: len(lines[at]) - len(lines[at].lstrip())]
lines[at] = indent + "minSdk = " + target
io.open(path, "w", encoding="utf-8", newline="").write("\n".join(lines))
print("  %s: %s -> minSdk = %s" % (rel, old, target))

after = io.open(path, encoding="utf-8").read()
assert ("minSdk = " + target) in after, "wrote the file but the value is not in it"
assert after.count("minSdk") == 1, "more than one minSdk after the edit"
print("  verified")
