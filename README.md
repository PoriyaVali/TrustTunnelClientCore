# TrustTunnel Client Core

The Android core for TrustTunnel, built and published by us, the way
`PoriyaVali/mihomo` and the mdns fork already are for the other cores.

This repository exists so the Doctor Mobile app never depends on a binary
somebody else controls. Upstream publishes an AAR to a package registry we do
not own, from a build we cannot reproduce; both of those are fixable, and the
point of this repo is to fix them.

## What the app actually needs

The library is a thin Kotlin wrapper — 20 files — over one native target,
`trusttunnel_android`. The API that matters is `VpnClient`:

```kotlin
class VpnClient(config: String, callbacks: VpnClientListener?)

fun start(vpnTunInterface: ParcelFileDescriptor?): Boolean
fun protectSocket(socket: Int): Boolean
fun stop()
fun notifyNetworkChange(available: Boolean)

DeepLink.decode(uri: String): String   // tt://… -> an [endpoint] TOML section
```

**It takes our TUN file descriptor rather than creating its own.** That matters
more than it looks: our `VpnService` builds the tunnel, with our per-app rules,
and hands the fd over — the same shape as the other three cores. `protectSocket`
covers what the hev bridge does elsewhere. An earlier reading of the Flutter
plugin's convenience wrapper suggested the library owned the VpnService itself;
it does not, and that reading would have cost a redesign for nothing.

So the integration is: subscription `tt://` link → `DeepLink.decode` → TOML →
`VpnClient(toml).start(pfd)`.

## Why upstream's build does not work here

`platform/android/lib` builds the AAR with `./gradlew :lib:assembleRelease`, but
its C++ dependencies come through Conan and seven of the fifteen are
`@adguard/oss` recipes: `dns-libs`, `native_libs_common`, `klib`, `ldns`,
`libevent`, `nghttp2`, `openssl/boring`.

Their CI pulls those from AdGuard's Artifactory. **That server is deactivated** —
`adguard.jfrog.io/artifactory/api/conan/conan/v1/ping` redirects to
`landing.jfrog.com/reactivate-server/adguard`. Not private: gone. Their own
workflow is also gated on the upstream repository name and runs in a private
container image, so it would not run in a fork regardless.

The `@adguard/oss` suffix names *their Conan recipe*, not a proprietary library.
The sources are public:

| dependency | where it comes from |
| --- | --- |
| `dns-libs` | [AdguardTeam/DnsLibs](https://github.com/AdguardTeam/DnsLibs) |
| `native_libs_common` | [AdguardTeam/NativeLibsCommon](https://github.com/AdguardTeam/NativeLibsCommon) |
| `ldns`, `nghttp2`, `libevent`, `klib` | standard OSS, most already on conancenter |
| `openssl/boring` | BoringSSL |

So this is work, not a wall.

## Two ways in, and they are not exclusive

**Consume the published AAR.** Cheapest by far: the artifact exists in upstream's
GitHub Packages and the only thing stopping us is a token scope — our current one
has `gist, repo, workflow` and the registry wants `read:packages`. Vendor the AAR
here, publish it from this repo, and the app has a fourth core.

**Build it from source.** The independence the rest of the stack already has. It
means providing those seven Conan recipes ourselves from the public sources
above. Larger, but it is the only version of this where nobody else can take the
binary away.

Doing the first does not block the second: the app integrates against `VpnClient`
either way, so where the AAR came from stays an implementation detail of this
repo.

## Status

Nothing built yet. The server side is finished and proven — a live node runs
TrustTunnel `v1.0.41-dm.3` under V2bX `v1.4.1`, with the panel emitting `tt://`
subscription links. This is the last piece.
