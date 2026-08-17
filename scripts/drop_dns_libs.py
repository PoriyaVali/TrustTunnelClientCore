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
    out = []
    for line in d.split("\n"):
        if "dns-libs" in line:
            out.append("# " + line + "  # dropped with the DNS proxy")
        else:
            out.append(line)
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


def main():
    edit("conanfile.py", drop_requirement)
    edit("core/CMakeLists.txt", drop_cmake)
    p = os.path.join(root, "core/src/dns_proxy_accessor.cpp")
    io.open(p, "w", encoding="utf-8", newline="").write(STUB)
    print("  stubbed core/src/dns_proxy_accessor.cpp")

    # Prove it: nothing outside the stub should still reference the package.
    bad = []
    for sub in ("conanfile.py", "core/CMakeLists.txt"):
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
