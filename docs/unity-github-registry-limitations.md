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

For reference, here is how a Unity project consumes these packages. You do not need to change this, but it helps to understand what the consumer expects.

### `Packages/manifest.json`

```json
{
  "scopedRegistries": [
    {
      "name": "GitHub - klumhru",
      "url": "https://npm.pkg.github.com",
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

### `.upmconfig.toml` (in user home directory)

```toml
[npmAuth."https://npm.pkg.github.com"]
token = "ghp_XXXXX"
alwaysAuth = true
```

**Critical detail:** The key in `npmAuth` must be an exact URL prefix match with the `url` in `manifest.json`. If these don't match, authentication fails silently and Unity reports invalid credentials.

---

## Summary of Required Changes to the Publishing Pipeline

1. **Remove the `@klumhru/` prefix from the `name` field** in every `package.json` that gets published. The name must be the bare UPM identifier (e.g. `com.klumhru.wrapper.some-package`).

2. **Add a `repository` field** to `package.json` pointing to the GitHub repository. GitHub uses this to determine ownership when the name is unscoped.

3. **Add a `publishConfig` block** to `package.json` with `"registry": "https://npm.pkg.github.com"`, or configure this via `.npmrc`.

4. **Publish with the scope flag**: `npm publish --scope=@klumhru`, or rely on the `repository` field for GitHub to infer ownership.

5. **Ensure the authentication token** used for publishing has `write:packages` scope.

6. **If packages are already published with the scoped name**, they may need to be deleted and republished with the unscoped name. GitHub does not support renaming published packages. Check if the old scoped versions need to be cleaned up.

---

## Verification

After publishing, verify the package is correctly named by querying the registry:

```bash
npm --registry https://npm.pkg.github.com view com.klumhru.wrapper.some-package
```

This should return the package metadata with the unscoped name. If it returns nothing or an error, the package was likely published with the scope in the name and needs to be republished.
