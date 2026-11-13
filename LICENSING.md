# TOPG component licensing and corresponding source

TOPG integrates code from multiple projects. The root Apache-2.0 LICENSE is not a replacement for the GPL or other licenses of bundled components. This document adds no restrictions and does not decide whether particular components form an aggregate or a combined work.

## Components and notices

- COPG/COPG-VD: AlirezaParsi and VD171, Apache-2.0. Preserve its copyright and attribution notices. The packaged Apache license is `webroot/LICENSE`.
- Original TEESimulator: JingMatrix. TEESimulator-RS: Enginex0 and contributors. The engine and modifications to GPL-covered code remain subject to GPLv3. The packaged engine license and notices are `tee/LICENSE` and `tee/NOTICE`.
- Preserve the additional notices listed by the engine, including TrickyStore/TrickyStoreOSS origins, AOSP Apache-2.0 portions, LSPlt LGPLv3, Linux UAPI GPL-2.0 WITH Linux-syscall-note, and the MIT notices for resetprop-rs and Rust libc. Their own license texts and applicable obligations remain in force.
- TOPG integration: wfire06100. New Apache-2.0 integration files do not relicense GPL-covered code or remove GPL obligations applicable to a combined work.

## Corresponding source shipped with the module

The installable ZIP includes `tee/engine-source.tar.gz`. Its `TEESimulator-RS/` directory contains the modified engine tree, tracked submodule sources, original LICENSE and NOTICE, `topg-relocation.json`, a dated `TOPG-MODIFICATIONS.md`, and `TOPG-SOURCE-INVENTORY.json` with file hashes or symlink targets. The archive also includes TOPG build/runtime/WebUI adapters, tests and workflows.

The complete TOPG repository source and build recipe are identified by the release tag and `sourceCommit` in `build-info.json`. Engine version and commit are also recorded there. Do not assume GitHub's automatic TOPG source archive alone includes the external engine. Use the embedded engine archive together with the matching TOPG sources and workflow. Toolchain and package-manager dependencies are described by those build files.

## Modification notices

Build adapters add dated TOPG modification notices while retaining original notices. Dates describe the build-time transformations, not the original authors' creation dates. JSON objects use a `_TOPG_MODIFICATION_NOTICE` metadata entry; other supported text formats use comments. `tee/topg-modified-files.json` records the marked module files.

Sources are selected from Git's tracked-file inventory, recursively including initialized submodules, rather than dropping every directory named `build`, `out` or `target`. Missing tracked files and source-inventory mismatches stop packaging.

These measures improve source distribution and traceability. They are not a legal certification, a complete third-party license audit, or proof that a clean rebuild has been reproduced. Previous releases are not changed retroactively by this document.
