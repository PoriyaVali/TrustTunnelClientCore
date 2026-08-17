# Building our own core

The goal is a core we build, that depends on nobody, and that carries only what
the app uses. Those three are the same job: every dependency removed is one less
thing to reproduce.

## What has to be replaced

Upstream pulls fifteen C++ dependencies through Conan. Seven carry the
`@adguard/oss` namespace, which names *their recipe*, not a proprietary library —
the sources are public. Their Artifactory is deactivated, so all seven have to
come from somewhere else regardless.

| dependency | where it comes from | note |
| --- | --- | --- |
| `dns-libs` | [AdguardTeam/DnsLibs](https://github.com/AdguardTeam/DnsLibs) | **removable — see below** |
| `native_libs_common` | [AdguardTeam/NativeLibsCommon](https://github.com/AdguardTeam/NativeLibsCommon) | needed |
| `openssl/boring` | BoringSSL | needed — TLS is the point |
| `libevent` | conancenter | 12 files use it |
| `nghttp2` | conancenter | HTTP/2 upstream |
| `ldns` | conancenter | DNS records |
| `klib` | public C library | 2 files |
| the rest | conancenter | brotli, cxxopts, http_parser, magic_enum, nlohmann_json, tomlplusplus, zlib |

## The one worth removing first

`dns-libs` is the heaviest dependency and it sits behind the narrowest surface:
**one file**, `core/src/dns_proxy_accessor.cpp`.

And in our configuration it never runs. `dns_handler.cpp` decides:

```cpp
if (m_parameters.dns_upstreams.empty()) {
    log_handler(this, info, "User DNS servers are empty");
    return true;                      // no DnsProxyAccessor is constructed
}
```

`dns_upstreams` arrives from the subscription as deep-link tag `0x0D`, and
Irboard does not emit it. So the DNS proxy is compiled in and never constructed:
removing it is a size change, not a behaviour change.

⚠️ That equivalence holds *only while the panel omits tag `0x0D`*. If we ever
want per-node DNS upstreams, this decision comes back — so the stub should fail
loudly if it is ever asked to construct, rather than quietly doing nothing.
Silently ignoring configured DNS servers is exactly the kind of bug that costs
weeks: everything works, and traffic goes somewhere nobody intended.

## What else is dead weight

- `platform/apple`, `platform/windows`, `platform/testapp` — we build one platform.
- `integration-tests`, `bench` — useful upstream, not in our build.
- ABIs: `arm64-v8a` is what our users run. `armeabi-v7a` only if we still support
  32-bit devices; each ABI is a full copy of the native library in the APK.

## Order of work

1. **Prove the toolchain before porting anything.** Build `trusttunnel_android`
   for `arm64-v8a` with the dependencies stubbed or vendored as far as they go,
   and find out what actually fails. Guessing which of the seven is hard is
   cheaper to answer by trying.
2. **Stub out `dns_proxy_accessor.cpp`** and drop `dns-libs`.
3. **Bring the remaining six** from public sources — conancenter first, recipes
   of our own only where there is no alternative.
4. **CI that produces the AAR**, the way `linux-dm.yml` produces the endpoint.
5. **Publish from this repo**, pinned in the app's `dependencies.properties`
   beside the other three cores.

Step 1 first, and honestly: if the native build cannot be made to work at all,
that is worth knowing before any of the porting effort, and consuming the
published AAR remains a working fallback that does not block trying again later.

## What the app integrates against

Unchanged by any of the above, which is why the two paths do not conflict:

```kotlin
DeepLink.decode(tt_link)            // -> [endpoint] TOML
VpnClient(toml, listener).start(pfd)   // our VpnService owns the TUN
client.protectSocket(fd)
```
