# vendor

Where a prebuilt `trusttunnel-client-android` AAR lands until this repo builds
its own. Kept in git deliberately: an artifact the app depends on should not be
something a registry can take away, and the file is small enough that its
history is worth having.

Record the upstream version and where it came from in the commit message, so a
binary here can always be traced to something.
