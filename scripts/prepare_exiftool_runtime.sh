#!/usr/bin/env bash
set -euo pipefail

ROOT="$(CDPATH= cd -- "$(dirname -- "$0")/.." && pwd)"
cd "$ROOT"

rm -rf vendor /tmp/exiftool-src /tmp/exiftool.tar.gz
mkdir -p vendor/perl/bin vendor/perl/lib vendor/perl/share vendor/musl /tmp/exiftool-src

HOST_UID="$(id -u)"
HOST_GID="$(id -g)"

# Do not compile Perl against a musl compatibility toolchain on the Ubuntu host.
# Instead, take one coherent Perl + musl userspace from Alpine and relocate it
# into the SPK. The wrapper below explicitly invokes the bundled musl loader,
# so DSM 6.1 does not need a compatible system Perl, glibc or musl loader.
docker run --rm \
  -e HOST_UID="$HOST_UID" \
  -e HOST_GID="$HOST_GID" \
  -v "$ROOT:/work" \
  alpine:3.21 \
  sh -euxc '
    apk add --no-cache perl

    mkdir -p /work/vendor/perl/bin /work/vendor/perl/lib /work/vendor/perl/share /work/vendor/musl
    cp -L /usr/bin/perl /work/vendor/perl/bin/perl
    cp -a /usr/lib/perl5 /work/vendor/perl/lib/
    cp -a /usr/share/perl5 /work/vendor/perl/share/

    # Keep the Alpine musl loader/libc and any direct shared-library
    # dependencies used by Perl/core XS modules together in one directory.
    cp -a /lib/. /work/vendor/musl/
    find /usr/lib -maxdepth 1 \( -type f -o -type l \) -name "*.so*" \
      -exec cp -a "{}" /work/vendor/musl/ \;

    # Alpine packages libperl beside Perl CORE instead of /usr/lib. Copy it
    # into the same bundled library directory used by our explicit loader.
    find /usr/lib/perl5 -type f -name "libperl.so*" \
      -exec cp -a "{}" /work/vendor/musl/ \;
    test -e /work/vendor/musl/libperl.so

    # Docker writes bind-mounted files as root by default. Return ownership to
    # the GitHub Actions runner so the remaining build can chmod/package them.
    chown -R "$HOST_UID:$HOST_GID" /work/vendor
  '

chmod 755 vendor/perl/bin/perl
LOADER="vendor/musl/ld-musl-x86_64.so.1"
test -e "$LOADER"
chmod 755 "$LOADER" || true

# Build PERL5LIB for the relocated Alpine tree. Alpine splits core Perl modules
# between /usr/lib/perl5 and /usr/share/perl5, so both trees are required.
PERL5LIB_PATH=""
for base in \
  "$ROOT/vendor/perl/lib/perl5/core_perl" \
  "$ROOT/vendor/perl/lib/perl5/vendor_perl" \
  "$ROOT/vendor/perl/lib/perl5/site_perl" \
  "$ROOT/vendor/perl/share/perl5/core_perl" \
  "$ROOT/vendor/perl/share/perl5/vendor_perl" \
  "$ROOT/vendor/perl/share/perl5/site_perl"
do
  [ -d "$base" ] || continue
  if [ -z "$PERL5LIB_PATH" ]; then PERL5LIB_PATH="$base"; else PERL5LIB_PATH="$PERL5LIB_PATH:$base"; fi
  for d in "$base"/*; do
    [ -d "$d" ] || continue
    PERL5LIB_PATH="$PERL5LIB_PATH:$d"
  done
done

test -n "$PERL5LIB_PATH"
PERL5LIB="$PERL5LIB_PATH" \
  "$ROOT/$LOADER" --library-path "$ROOT/vendor/musl" "$ROOT/vendor/perl/bin/perl" \
  -e 'use strict; use warnings; use Encode; use File::Basename; use File::Spec; use POSIX; print qq(bundled perl ok: $^V\n)'

# Pin the latest production ExifTool release to CPAN. Development releases on
# exiftool.org are rotated out and old direct URLs may return 404.
curl -fL --retry 3 --retry-delay 2 \
  https://www.cpan.org/modules/by-module/File/EXIFTOOL/Image-ExifTool-13.55.tar.gz \
  -o /tmp/exiftool.tar.gz
tar -xzf /tmp/exiftool.tar.gz -C /tmp/exiftool-src --strip-components=1
mkdir -p vendor/exiftool
cp /tmp/exiftool-src/exiftool vendor/exiftool/exiftool.pl
cp -a /tmp/exiftool-src/lib vendor/exiftool/lib

cat > vendor/exiftool/exiftool <<'SH'
#!/bin/sh
HERE="$(CDPATH= cd -- "$(dirname -- "$0")" && pwd)"
VENDOR_ROOT="$(CDPATH= cd -- "$HERE/.." && pwd)"
PERL_ROOT="$VENDOR_ROOT/perl"
LOADER="$VENDOR_ROOT/musl/ld-musl-x86_64.so.1"

PERL5LIB="$HERE/lib"
for base in \
  "$PERL_ROOT/lib/perl5/core_perl" \
  "$PERL_ROOT/lib/perl5/vendor_perl" \
  "$PERL_ROOT/lib/perl5/site_perl" \
  "$PERL_ROOT/share/perl5/core_perl" \
  "$PERL_ROOT/share/perl5/vendor_perl" \
  "$PERL_ROOT/share/perl5/site_perl"
do
  [ -d "$base" ] || continue
  PERL5LIB="$PERL5LIB:$base"
  for d in "$base"/*; do
    [ -d "$d" ] && PERL5LIB="$PERL5LIB:$d"
  done
done
export PERL5LIB

exec "$LOADER" \
  --library-path "$VENDOR_ROOT/musl" \
  "$PERL_ROOT/bin/perl" \
  "$HERE/exiftool.pl" "$@"
SH
chmod 755 vendor/exiftool/exiftool

cat > vendor/exiftool/RUNTIME_SOURCE.txt <<'EOF'
ExifTool 13.55 production release from CPAN
Perl + musl userspace staged from Alpine 3.21
The bundled musl loader is invoked explicitly; DSM system Perl/glibc is not required.
EOF

# CI/runtime smoke tests. These exercise XS modules as well as ExifTool itself.
vendor/exiftool/exiftool -ver | grep -qx '13.55'
printf '\377\330\377\331' > /tmp/minimal.jpg
vendor/exiftool/exiftool -json -n -SourceFile -FileType /tmp/minimal.jpg \
  | tee /tmp/exiftool-test.json
grep -q 'SourceFile' /tmp/exiftool-test.json

printf 'Bundled ExifTool runtime OK\n'
