# TOPG changelog

This file contains reviewed TOPG release highlights. The upstream COPG-VD history remains in CHANGELOG.md.

Before publishing, add user-facing changes under Unreleased (Added, Fixed, Changed, Removed, Security as appropriate). Before preparing the following release, archive the published highlights under their exact version heading and start a fresh Unreleased section. The generator also accepts an exact version heading for a planned release. An unchanged Unreleased section is not repeated when it matches the previous published source revision.

The release generator adds a separate technical audit of TOPG and engine commits since the previous stable published release. Commit messages are not automatically promoted to reviewed feature claims. Initial publication establishes a baseline instead of dumping all repository history. API, provenance and comparison failures stop publication rather than silently dropping changes.

The existing workflow appends corresponding-source notices and then copies the final release description to changelog.md. Do not edit only the GitHub release description after publication: synchronize the description and changelog.md asset together. This change does not repair already published assets.

## [Unreleased]

### Fixed
- Generate release-specific highlights and separate TOPG and engine commit audits instead of publishing only a static feature list.
- Use the same generated notes for the GitHub release description and the manager changelog, including corresponding-source and license notices.

### Changed
- Compare against commits recorded inside the previous stable release ZIP, preserve full commit descriptions in the technical audit, and refuse incomplete or divergent comparisons.
- Reject publication when the version already exists or versionCode does not increase.

## v6.12.0-b21.1

### Added
- TOPG manager update channel with release-hosted update.json and changelog.md.
- Release-time checks for matching module/update metadata and increasing versionCode.
