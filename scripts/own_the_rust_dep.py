# Point the client's Rust dependency at our own fork.
#
# The client pulls trusttunnel-deeplink straight from AdGuard:
#
#   trusttunnel-deeplink = { git = "https://github.com/TrustTunnel/TrustTunnel", tag = "v1.0.33" }
#
# which means every build of "our own core" fetches from a repository we do
# not control, and stops working the day that repository does. The whole point
# of this core is not depending on anybody.
#
# This is safe rather than merely desirable: the deeplink crate is byte-for-byte
# identical between upstream v1.0.33 and our fork's HEAD - 12 files at each end,
# zero changes - so repointing swaps the source and nothing else. Verified with
# `git diff v1.0.33..HEAD -- deeplink` on the fork, against a control that
# proved the same command does report the changes we made elsewhere.
import io
import os
import sys

root = sys.argv[1] if len(sys.argv) > 1 else "client"
fork = sys.argv[2] if len(sys.argv) > 2 else "https://github.com/PoriyaVali/TrustTunnel"
tag = sys.argv[3] if len(sys.argv) > 3 else "v1.0.41-dm.3"

UPSTREAM = "https://github.com/TrustTunnel/TrustTunnel"


def cargo_files():
    """Every Cargo.toml that names upstream - found, not listed.

    Listing them cost a run. I knew about settings/ and deeplink-ffi/, patched
    exactly those, and setup_wizard/ declares the same dependency. The point is
    not that there were three; it is that the number is not mine to know. Same
    shape as searching for the CMake files in drop_dns_libs.py, and as
    exporting every Conan recipe instead of the ones a conanfile happens to
    name - this project has now taught the same lesson three times.
    """
    found = []
    for dirpath, dirnames, filenames in os.walk(root):
        dirnames[:] = [d for d in dirnames if d not in (".git", "target", "build")]
        if "Cargo.toml" not in filenames:
            continue
        p = os.path.join(dirpath, "Cargo.toml")
        if UPSTREAM in io.open(p, encoding="utf-8", errors="ignore").read():
            found.append(os.path.relpath(p, root).replace(os.sep, "/"))
    return sorted(found)


patched = 0
for rel in cargo_files():
    path = os.path.join(root, rel)
    lines = io.open(path, encoding="utf-8").read().split("\n")
    hits = 0
    for i, line in enumerate(lines):
        if UPSTREAM not in line:
            continue
        # Replace the URL, then the tag - the tag only within this line, so a
        # version elsewhere in the file cannot be caught by it.
        new = line.replace(UPSTREAM, fork)
        before, _, after = new.partition("tag = ")
        if after:
            quote = after[0]
            end = after.index(quote, 1)
            new = before + "tag = " + quote + tag + quote + after[end + 1 :]
        lines[i] = new
        hits += 1
    if hits == 0:
        print("  no upstream reference in", rel)
        continue
    io.open(path, "w", encoding="utf-8", newline="").write("\n".join(lines))
    print("  patched %s (%d line%s)" % (rel, hits, "" if hits == 1 else "s"))
    patched += hits

assert patched > 0, "found nothing to repoint - has the client's layout changed?"

# Prove it, over the whole tree rather than the files we happened to edit: a
# reference we did not know about is exactly the one that would survive.
stale = []
for dirpath, dirnames, filenames in os.walk(root):
    dirnames[:] = [d for d in dirnames if d not in (".git", "target", "build")]
    for fn in filenames:
        if fn != "Cargo.toml":
            continue
        p = os.path.join(dirpath, fn)
        for line in io.open(p, encoding="utf-8", errors="ignore").read().split("\n"):
            s = line.strip()
            # `repository = ` is package metadata, not a dependency: it names
            # where the crate came from and pulls nothing.
            if UPSTREAM in s and not s.startswith("repository"):
                stale.append((os.path.relpath(p, root), s[:90]))

if stale:
    for f, l in stale:
        print("  STILL UPSTREAM:", f, l)
    raise SystemExit(1)
print("  the Rust side now builds only from %s @ %s" % (fork, tag))
