# Publishing Unity Package Manager Packages to GitHub's npm Registry

## Problem Summary

Unity Package Manager (UPM) packages published to GitHub's npm package registry are not consumable by Unity clients. The root cause is a conflict between GitHub's requirement that all npm packages be scoped (e.g. `@klumhru/com.klumhru.some-package`) and Unity's inability to handle npm scopes. This document describes the constraints on both sides and what the publishing pipeline must do to produce compatible packages.

---

## The Two Conflicting Requirements

### GitHub npm Registry Requires Scoped Packages

GitHub's npm registry mandates that every package name begins with an npm scope matching the GitHub owner (user or organization). For a user named `klumhru`, every package must be named `@klumhru/something`. If you attempt to publish a package without the scope, the registry rejects it.

This scope is set via the `name` field in `package.json`:

```json
{
  "name": "@klumhru/com.klumhru.wrapper.some-package"
}
```

GitHub uses this scope to determine which user/org owns the package.

### Unity Package Manager Does Not Understand npm Scopes

UPM resolves packages by their exact `name` field. When Unity sees a dependency like:

```json
"com.klumhru.wrapper.some-package": "1.0.0"
```

It queries the configured scoped registry for a package with that exact name. However, GitHub's registry returns the package metadata with the full scoped name `@klumhru/com.klumhru.wrapper.some-package`. UPM cannot match these two names, and resolution fails with an error like:

```
Expected to find progress reporting for @klumhru/com.klumhru.wrapper.some-package. No packages loaded.
```

UPM has no mechanism to map scoped npm names to unscoped UPM names. There is no configuration on the Unity side that can fix this.

---

## The Fix: Publish Without the Scope in `package.json`

The solution is to publish packages where the `name` field in `package.json` does **not** include the `@owner/` scope prefix. Instead, the scope is provided at publish time via npm configuration.

### What `package.json` Must Look Like

The `name` field must be the bare UPM package name with no npm scope:

```json
{
  "name": "com.klumhru.wrapper.some-package",
  "version": "1.0.0",
  "displayName": "Some Package Wrapper",
  "unity": "6000.0"
}
```

**Do not put `@klumhru/` in the name field.**

### How to Tell GitHub Which Owner the Package Belongs To

GitHub determines package ownership from the npm scope provided during publishing. This is configured in an `.npmrc` file (either in the project root or the user's home directory):

```
@klumhru:registry=https://npm.pkg.github.com
//npm.pkg.github.com/:_authToken=TOKEN
```

The first line tells npm: "any package published under the `@klumhru` scope should go to GitHub's registry." The second line provides the authentication token.

### The Publish Command

Use the `--scope` flag to attach the scope at publish time without it being in `package.json`:

```bash
npm publish --scope=@klumhru
```

This tells npm to treat the package as belonging to the `@klumhru` scope for registry routing purposes, but the package name stored in the registry metadata will be whatever is in `package.json` — the unscoped UPM name.

### Alternative: Use `publishConfig` in `package.json`

Instead of relying on `.npmrc` and the `--scope` flag, you can add a `publishConfig` block to `package.json`:

```json
{
  "name": "com.klumhru.wrapper.some-package",
  "version": "1.0.0",
  "publishConfig": {
    "registry": "https://npm.pkg.github.com"
  }
}
```

Combined with a repository field that tells GitHub the owner:

```json
{
  "repository": {
    "type": "git",
    "url": "https://github.com/klumhru/your-repo.git"
  }
}
```

GitHub infers the scope from the `repository` field when the package name is not explicitly scoped. This approach may be cleaner for CI/CD pipelines.

---

## What the Unity Consumer Side Looks Like

For reference, here is how a Unity project consumes these packages.

### `Packages/manifest.json`

The registry `url` **must include the owner scope path** (`/@klumhru`), not just
the bare `npm.pkg.github.com` domain. This is because GitHub Packages stores
all packages under a scoped path and only responds to queries at that path;
querying the bare domain for an unscoped package name returns 404.

```json
{
  "scopedRegistries": [
    {
      "name": "GitHub - klumhru",
      "url": "https://npm.pkg.github.com/@klumhru",
      "scopes": [
        "com.klumhru"
      ]
    }
  ],
  "dependencies": {
    "com.klumhru.wrapper.some-package": "1.0.0"
  }
}
```

When UPM resolves `com.klumhru.wrapper.some-package`, it appends the package
name to the registry `url`, producing:
`https://npm.pkg.github.com/@klumhru/com.klumhru.wrapper.some-package` —
which is the exact path where the package lives in GitHub Packages.

### `.upmconfig.toml` (in user home directory)

The token auth entry **must match the registry `url` exactly** (including the
`/@klumhru` path), otherwise authentication fails silently.

```toml
[npmAuth."https://npm.pkg.github.com/@klumhru"]
token = "ghp_XXXXX"
alwaysAuth = true
```

---

## Summary of the Implemented Publishing Strategy

The pipeline uses **direct HTTP PUT** to GitHub Packages instead of the npm
CLI, which allows full control over the request:

1. **`npm pack`** creates the tarball. The `package.json` inside the tarball
   keeps the **unscoped** UPM name (`com.klumhru.wrapper.some-package`), so
   Unity can install and resolve it correctly after download.

2. A **packument** document is constructed with:
   - `name`: scoped name (`@klumhru/com.klumhru.wrapper.some-package`) — required by GitHub for routing
   - `_attachments` key: `@klumhru/com.klumhru.wrapper.some-package-{version}.tgz` — GitHub requires the attachment key to be `{packument.name}-{version}.tgz`

3. The packument is **PUT to** `https://npm.pkg.github.com/@klumhru/com.klumhru.wrapper.some-package`.

4. **Versions must use strict semver** (e.g. `31.1.0`, not `v31.1.0`). The
   pipeline strips any leading `v` automatically.

---

## Verification

After publishing, verify the package is accessible:

```bash
# Requires a valid token with read:packages scope
curl -H "Authorization: Bearer ghp_XXXXX" \
  "https://npm.pkg.github.com/@klumhru/com.klumhru.wrapper.some-package"
```

The response lists available versions. The `name` field in the response will
be the scoped name; the tarball's internal `package.json` contains the unscoped
UPM name.
