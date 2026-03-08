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

GitHub Packages always returns scoped names in packument responses (e.g.
`@klumhru/com.foo.bar`).  UPM validates the `name` field in the packument
and fails with:

```
Expected to find progress reporting for @klumhru/com.foo.bar. No packages loaded.
```

To work around this, the pipeline additionally generates a **static npm
registry** deployed to GitHub Pages.  The Pages registry serves packuments
with the correct unscoped names; tarballs are still downloaded from GitHub
Packages.

### `Packages/manifest.json`

Point the scoped registry at the GitHub Pages URL, **not** at
`npm.pkg.github.com`:

```json
{
  "scopedRegistries": [
    {
      "name": "klumhru packages",
      "url": "https://klumhru.github.io/package-wrappers-unity",
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

The GitHub Pages URL is `https://{owner}.github.io/{repo}`.  UPM appends
the package name to produce
`https://klumhru.github.io/package-wrappers-unity/com.klumhru.wrapper.some-package`,
which serves a static JSON packument with the unscoped name.

### `.upmconfig.toml` (in user home directory)

Auth is needed for the **tarball download** (which comes from GitHub Packages).
The key must match the base GitHub Packages domain so it covers all tarball
URLs:

```toml
[npmAuth."https://npm.pkg.github.com"]
token = "ghp_XXXXX"
alwaysAuth = true
```

No auth entry is needed for the GitHub Pages URL — it is a public static site.

---

## Summary of the Implemented Publishing Strategy

1. **`npm pack`** creates the tarball.  The `package.json` inside the tarball
   keeps the **unscoped** UPM name (`com.klumhru.wrapper.some-package`).

2. A **packument** (scoped name in body, scoped PUT URL) is sent directly to
   GitHub Packages via HTTP PUT.  This is required for GitHub routing — the
   npm CLI cannot be used because it always derives the PUT URL from the
   unscoped `name` field, which GitHub rejects with 404.

3. After a successful publish, a **static packument JSON** is written to
   `dist/registry/{package_name}.json` with:
   - `name`: **unscoped** (e.g. `com.klumhru.wrapper.some-package`)
   - `dist.tarball`: pointing to the GitHub Packages tarball URL

4. The CI workflow deploys `dist/registry/` to **GitHub Pages** via
   `actions/deploy-pages`.

5. **Versions must use strict semver** (e.g. `31.1.0`, not `v31.1.0`).  The
   pipeline strips any leading `v` from git tag–style versions automatically.

> **Enable GitHub Pages** in repository Settings → Pages → Source: GitHub
> Actions, before the first deployment.

---

## Verification

```bash
# 1. Check that the static packument (unscoped name) is served by GitHub Pages
curl "https://klumhru.github.io/package-wrappers-unity/com.klumhru.wrapper.some-package"

# 2. Check that the tarball is accessible (requires GitHub token)
curl -H "Authorization: Bearer ghp_XXXXX" \
  "https://npm.pkg.github.com/@klumhru/com.klumhru.wrapper.some-package/-/@klumhru/com.klumhru.wrapper.some-package-1.0.0.tgz" \
  --head
```
