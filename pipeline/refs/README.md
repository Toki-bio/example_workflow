# Reference bundles

`make_versions.py <bundle_dir>` writes `versions.json`, `SHA256SUMS` and a `README.md` for a dated bundle of the
lookup data used by stage 08 (ClinVar, HPO, PanelApp, ClinGen, G2P, gnomAD constraint, Nirvana data). Versions are
read from the files' own headers or from the downloader's manifest, never from a README. It exits non-zero if a
version cannot be read, so the run that depends on it can refuse to start. `--verify-nirvana-md5` re-hashes the
Nirvana data against the downloader's MD5 list (slow). See the docstring for the expected layout.
