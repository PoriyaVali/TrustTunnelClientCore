# Remove dns-libs from the client, properly.
#
# Three places, and leaving any one of them breaks a different way:
#   conanfile.py     - the Conan requirement
#   core/CMakeLists  - find_package + two link lines (configure fails without this)
#   dns_proxy_accessor.cpp - the only file that includes the headers
#
# In our configuration the DNS proxy is never constructed: dns_handler returns
# early when dns_upstreams is empty, and Irboard does not emit deep-link tag
# 0x0D. Removing it is a size change, not a behaviour change - and it also
# resolves a version conflict, because dns-libs pins native_libs_common 8.1.48
# while the client asks for 8.1.49.
import io
import os
import re
import sys

root = sys.argv[1] if len(sys.argv) > 1 else "client"


def edit(rel, fn):
    p = os.path.join(root, rel)
    d = io.open(p, encoding="utf-8").read()
    out = fn(d)
    io.open(p, "w", encoding="utf-8", newline="").write(out)
    print("  patched", rel)


def drop_requirement(d):
    out = []
    for line in d.split("\n"):
        # Both the requirement and any options set on it: an option on a
        # package that is no longer required is an error, not a leftover.
        if "dns-libs" in line and ("self.requires" in line or "self.options[" in line):
            indent = line[:len(line) - len(line.lstrip())]
            out.append(indent + "pass  # dropped: the DNS proxy is never constructed here")
        else:
            out.append(line)
    return "\n".join(out)


def drop_cmake(d):
    """Remove the references, not the lines that hold them.

    Commenting out whole lines broke common/CMakeLists.txt: the reference sat
    on the closing line of a multi-line target_link_libraries, so the call lost
    its ")" and CMake reported a parse error at end of file. A line is only safe
    to comment out when it is a complete call by itself.
    """
    out = []
    for line in d.split("\n"):
        if "dns-libs" not in line:
            out.append(line)
            continue
        stripped = line.strip()
        # A self-contained find_package(...) can go entirely.
        if stripped.startswith("find_package(") and stripped.endswith(")"):
            out.append("# " + line + "  # dropped with the DNS proxy")
            continue
        # Otherwise strip just the target and keep the surrounding call intact.
        cleaned = re.sub(r"\s*dns-libs::dns-libs", "", line)
        cleaned = re.sub(r"\s*dns-libs\b", "", cleaned)
        if cleaned.strip() in ("", ")"):
            # The reference was the only thing on the line; keep any closing
            # bracket so the call still terminates.
            out.append(cleaned if cleaned.strip() == ")" else "")
        else:
            out.append(cleaned)
    return "\n".join(out)


# The accessor is replaced rather than deleted: the header is still included by
# dns_handler, and a stub that throws makes a future attempt to use it obvious
# instead of silently doing nothing. Quietly ignoring configured DNS servers is
# the kind of bug that costs weeks.
STUB = '''// Replaced: this build has no dns-libs.
//
// The DNS proxy is only constructed when the subscription supplies
// dns_upstreams (deep-link tag 0x0D), which our panel does not emit, so this
// code never runs here. If that ever changes, this fails loudly rather than
// ignoring the DNS servers someone configured.

#include "vpn/internal/dns_proxy_accessor.h"

#include <stdexcept>

namespace ag {

DnsProxyAccessor::DnsProxyAccessor(Parameters parameters) {
    (void) parameters;
    throw std::runtime_error(
            "this build has no DNS proxy: rebuild with dns-libs to use dns_upstreams");
}

DnsProxyAccessor::~DnsProxyAccessor() = default;

} // namespace ag
'''


def all_cmake_files():
    """Every CMakeLists that mentions the package.

    Patching core/CMakeLists.txt alone left common/CMakeLists.txt:43 asking for
    it, and configure failed the same way one run later. Search rather than
    list: the point is not to know how many there are.
    """
    found = []
    for dirpath, dirnames, filenames in os.walk(root):
        dirnames[:] = [x for x in dirnames if x not in (".git", "third-party", "build")]
        for fn in filenames:
            if fn == "CMakeLists.txt" or fn.endswith(".cmake"):
                p = os.path.join(dirpath, fn)
                try:
                    if "dns-libs" in io.open(p, encoding="utf-8", errors="ignore").read():
                        found.append(os.path.relpath(p, root))
                except OSError:
                    pass
    return found


# common/src/utils.cpp exposes a C API for parsing DNS stamps (sdns:// URLs),
# which is the other place that includes dns-libs headers. Nothing in our
# configuration parses stamps - they describe DNS upstreams, and we do not send
# any - so the functions become stubs that report failure rather than pretending
# to have parsed something.
def stub_dns_stamps(d):
    lines = d.split("\n")

    # Drop the include; without it nothing else in the file needs the package.
    lines = [l for l in lines if "dns/dnsstamp/dns_stamp.h" not in l]

    start = None
    for i, line in enumerate(lines):
        if line.startswith("VpnDnsStamp *vpn_dns_stamp_from_str"):
            start = i
            break
    if start is None:
        return "\n".join(lines)

    # The block runs to the end of the last stamp function; find the closing
    # brace of the one after which a non-stamp function begins.
    end = None
    for i in range(start, len(lines)):
        if lines[i].startswith("void vpn_string_free"):
            end = i
            break
    assert end is not None, "could not find the end of the stamp block"
    while end > start and lines[end - 1].strip() == "":
        end -= 1

    stub = [
        "// DNS stamp parsing needs dns-libs, which this build does not carry.",
        "// Stamps describe DNS upstreams and we never send any, so these report",
        "// failure instead of returning something that was not parsed.",
        "VpnDnsStamp *vpn_dns_stamp_from_str(const char *stamp_str, const char **error) {",
        "    (void) stamp_str;",
        '    if (error != nullptr) {',
        '        *error = marshal_str("DNS stamps are not supported in this build");',
        "    }",
        "    return nullptr;",
        "}",
        "",
        "void vpn_dns_stamp_free(VpnDnsStamp *stamp) {",
        "    (void) stamp;",
        "}",
        "",
        "const char *vpn_dns_stamp_to_str(VpnDnsStamp *c_stamp) {",
        "    (void) c_stamp;",
        "    return nullptr;",
        "}",
        "",
        "const char *vpn_dns_stamp_pretty_url(VpnDnsStamp *c_stamp) {",
        "    (void) c_stamp;",
        "    return nullptr;",
        "}",
        "",
        "const char *vpn_dns_stamp_prettier_url(VpnDnsStamp *c_stamp) {",
        "    (void) c_stamp;",
        "    return nullptr;",
        "}",
        "",
    ]
    lines[start:end] = stub

    # Helpers that only the removed functions called are now orphaned, and the
    # project builds with -Werror, so an unused static function is a build
    # failure. Marked rather than deleted: restoring dns-libs later should not
    # also mean rewriting these.
    for i, line in enumerate(lines):
        s = line.lstrip()
        if s.startswith("static ") and "(" in s and "[[maybe_unused]]" not in line:
            name = s.split("(")[0].split()[-1].lstrip("*&")
            # Count uses outside its own definition.
            uses = sum(1 for l in lines if name in l) - 1
            if uses <= 0:
                indent = line[:len(line) - len(s)]
                lines[i] = indent + "[[maybe_unused]] " + s

    return "\n".join(lines)


def main():
    edit("conanfile.py", drop_requirement)
    edit("common/src/utils.cpp", stub_dns_stamps)
    for rel in all_cmake_files():
        edit(rel, drop_cmake)
    p = os.path.join(root, "core/src/dns_proxy_accessor.cpp")
    io.open(p, "w", encoding="utf-8", newline="").write(STUB)
    print("  stubbed core/src/dns_proxy_accessor.cpp")

    # Prove it: nothing outside the stub should still reference the package.
    bad = []
    for sub in ["conanfile.py"] + all_cmake_files():
        d = io.open(os.path.join(root, sub), encoding="utf-8").read()
        for line in d.split("\n"):
            s = line.strip()
            if "dns-libs" in s and not s.startswith("#"):
                bad.append((sub, s[:70]))
    if bad:
        for f, l in bad:
            print("  STILL REFERENCED:", f, l)
        raise SystemExit(1)
    print("  no live references to dns-libs remain")


main()
