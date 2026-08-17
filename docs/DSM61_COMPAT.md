# DSM 6.1 compatibility

Gen8 Photo EXIF Reader targets DSM 6.1 and later within the DSM 6.x package line.

## Minimum version

- Minimum DSM: `6.1-14715`
- Installation-validation SPK architecture: `noarch`

The current validation build contains scripts and web assets only, so `noarch` is used to maximize compatibility during package-format testing. A later build that bundles native Python/ExifTool runtime files may switch back to an architecture-specific package where necessary.

## Packaging compatibility rules

For DSM 6.1 compatibility the SPK builder should:

- write the outer `.spk` as a plain USTAR tar archive;
- write `package.tgz` as gzip-compressed USTAR;
- keep the `INFO` file limited to fields available on DSM 6.1;
- use `os_min_ver="6.1-14715"`;
- avoid declaring a DSM 6.2-only minimum version;
- retain the low-privilege package execution model.

The first purpose of the `0.1.1-0002` build is to verify that DSM can parse and install the package before native runtime dependencies are bundled.
