"""Tests for PagesPublisher."""

import json
from pathlib import Path

import pytest

from unity_wrapper.utils.pages_publisher import PagesPublisher


@pytest.fixture
def registry_dir(tmp_path: Path) -> Path:
    return tmp_path / "registry"


@pytest.fixture
def publisher() -> PagesPublisher:
    return PagesPublisher()


_VERSION_META = {
    "name": "@owner/com.foo.bar",
    "_id": "@owner/com.foo.bar@1.0.0",
    "description": "A test package",
    "version": "1.0.0",
    "unity": "2019.4",
}


def _write_version(
    publisher: PagesPublisher,
    registry_dir: Path,
    version: str = "1.0.0",
    name: str = "com.foo.bar",
) -> Path:
    return publisher.update_registry(
        registry_dir=registry_dir,
        unscoped_name=name,
        version=version,
        version_meta=dict(_VERSION_META),
        tarball_url=(
            f"https://npm.pkg.github.com/@owner/{name}/-/{name}-{version}.tgz"
        ),
        shasum="abc123",
        integrity="sha512-xxx==",
        description="A test package",
    )


class TestPagesPublisherCreate:
    """Creates a new packument file on first call."""

    def test_creates_registry_dir(
        self,
        publisher: PagesPublisher,
        tmp_path: Path,
    ) -> None:
        nested = tmp_path / "a" / "b" / "registry"
        _write_version(publisher, nested)
        assert nested.exists()

    def test_creates_packument_file(
        self,
        publisher: PagesPublisher,
        registry_dir: Path,
    ) -> None:
        path = _write_version(publisher, registry_dir)
        assert path.exists()
        assert path.name == "com.foo.bar"

    def test_packument_has_unscoped_name(
        self,
        publisher: PagesPublisher,
        registry_dir: Path,
    ) -> None:
        _write_version(publisher, registry_dir)
        doc = json.loads((registry_dir / "com.foo.bar").read_text())
        assert doc["name"] == "com.foo.bar"

    def test_packument_dist_tags_latest(
        self,
        publisher: PagesPublisher,
        registry_dir: Path,
    ) -> None:
        _write_version(publisher, registry_dir, version="2.0.0")
        doc = json.loads((registry_dir / "com.foo.bar").read_text())
        assert doc["dist-tags"]["latest"] == "2.0.0"

    def test_version_entry_has_dist(
        self,
        publisher: PagesPublisher,
        registry_dir: Path,
    ) -> None:
        _write_version(publisher, registry_dir, version="1.0.0")
        doc = json.loads((registry_dir / "com.foo.bar").read_text())
        dist = doc["versions"]["1.0.0"]["dist"]
        assert dist["shasum"] == "abc123"
        assert dist["integrity"] == "sha512-xxx=="
        assert "tarball" in dist

    def test_version_entry_name_is_unscoped(
        self,
        publisher: PagesPublisher,
        registry_dir: Path,
    ) -> None:
        """Even if version_meta has scoped name, output must be unscoped."""
        _write_version(publisher, registry_dir)
        doc = json.loads((registry_dir / "com.foo.bar").read_text())
        assert doc["versions"]["1.0.0"]["name"] == "com.foo.bar"

    def test_version_entry_id_removed(
        self,
        publisher: PagesPublisher,
        registry_dir: Path,
    ) -> None:
        """_id from version_meta (scoped) should not appear in output."""
        _write_version(publisher, registry_dir)
        doc = json.loads((registry_dir / "com.foo.bar").read_text())
        assert "_id" not in doc["versions"]["1.0.0"]


class TestPagesPublisherUpdate:
    """Merges new versions into an existing packument file."""

    def test_accumulates_versions(
        self,
        publisher: PagesPublisher,
        registry_dir: Path,
    ) -> None:
        _write_version(publisher, registry_dir, version="1.0.0")
        _write_version(publisher, registry_dir, version="1.1.0")
        doc = json.loads((registry_dir / "com.foo.bar").read_text())
        assert "1.0.0" in doc["versions"]
        assert "1.1.0" in doc["versions"]

    def test_latest_tag_updated_to_newest(
        self,
        publisher: PagesPublisher,
        registry_dir: Path,
    ) -> None:
        _write_version(publisher, registry_dir, version="1.0.0")
        _write_version(publisher, registry_dir, version="1.1.0")
        doc = json.loads((registry_dir / "com.foo.bar").read_text())
        assert doc["dist-tags"]["latest"] == "1.1.0"

    def test_fixes_scoped_name_in_existing_file(
        self,
        publisher: PagesPublisher,
        registry_dir: Path,
    ) -> None:
        """If an older file has a scoped name, it gets corrected on update."""
        registry_dir.mkdir(parents=True)
        bad = {
            "name": "@owner/com.foo.bar",
            "dist-tags": {"latest": "0.9.0"},
            "versions": {"0.9.0": {"name": "@owner/com.foo.bar"}},
        }
        (registry_dir / "com.foo.bar").write_text(json.dumps(bad))

        _write_version(publisher, registry_dir, version="1.0.0")

        doc = json.loads((registry_dir / "com.foo.bar").read_text())
        assert doc["name"] == "com.foo.bar"
        assert "0.9.0" in doc["versions"]  # old version preserved
        assert "1.0.0" in doc["versions"]  # new version added


class TestPagesPublisherTarballUrl:
    """Tarball URL is stored verbatim in the static packument."""

    def test_tarball_url_preserved(
        self,
        publisher: PagesPublisher,
        registry_dir: Path,
    ) -> None:
        expected = (
            "https://npm.pkg.github.com/@owner/com.foo.bar"
            "/-/@owner/com.foo.bar-1.0.0.tgz"
        )
        publisher.update_registry(
            registry_dir=registry_dir,
            unscoped_name="com.foo.bar",
            version="1.0.0",
            version_meta=dict(_VERSION_META),
            tarball_url=expected,
            shasum="deadbeef",
            integrity="sha512-yyy==",
        )
        doc = json.loads((registry_dir / "com.foo.bar").read_text())
        assert doc["versions"]["1.0.0"]["dist"]["tarball"] == expected


class TestPagesPublisherTarballStorage:
    """When tarball_data + pages_base_url are provided, the tarball is
    saved to the registry dir and the packument uses the Pages URL."""

    def test_tarball_file_written(
        self,
        publisher: PagesPublisher,
        registry_dir: Path,
    ) -> None:
        publisher.update_registry(
            registry_dir=registry_dir,
            unscoped_name="com.foo.bar",
            version="1.0.0",
            version_meta=dict(_VERSION_META),
            tarball_url="https://fallback/",
            shasum="abc",
            integrity="sha512-x==",
            tarball_data=b"tarball-bytes",
            pages_base_url="https://owner.github.io/repo",
        )
        tarball_path = registry_dir / "com.foo.bar-1.0.0.tgz"
        assert tarball_path.exists()
        assert tarball_path.read_bytes() == b"tarball-bytes"

    def test_packument_url_points_to_pages(
        self,
        publisher: PagesPublisher,
        registry_dir: Path,
    ) -> None:
        publisher.update_registry(
            registry_dir=registry_dir,
            unscoped_name="com.foo.bar",
            version="1.0.0",
            version_meta=dict(_VERSION_META),
            tarball_url="https://fallback/",
            shasum="abc",
            integrity="sha512-x==",
            tarball_data=b"tarball-bytes",
            pages_base_url="https://owner.github.io/repo",
        )
        doc = json.loads((registry_dir / "com.foo.bar").read_text())
        expected = "https://owner.github.io/repo/com.foo.bar-1.0.0.tgz"
        assert doc["versions"]["1.0.0"]["dist"]["tarball"] == expected

    def test_pages_base_url_trailing_slash_stripped(
        self,
        publisher: PagesPublisher,
        registry_dir: Path,
    ) -> None:
        publisher.update_registry(
            registry_dir=registry_dir,
            unscoped_name="com.foo.bar",
            version="2.0.0",
            version_meta=dict(_VERSION_META),
            tarball_url="https://fallback/",
            shasum="abc",
            integrity="sha512-x==",
            tarball_data=b"data",
            pages_base_url="https://owner.github.io/repo/",
        )
        doc = json.loads((registry_dir / "com.foo.bar").read_text())
        url = doc["versions"]["2.0.0"]["dist"]["tarball"]
        assert not url.startswith(
            "https://owner.github.io/repo//"
        ), "double slash in URL"
        assert url == "https://owner.github.io/repo/com.foo.bar-2.0.0.tgz"

    def test_fallback_url_used_when_no_tarball_data(
        self,
        publisher: PagesPublisher,
        registry_dir: Path,
    ) -> None:
        fallback = "https://npm.pkg.github.com/download/x"
        publisher.update_registry(
            registry_dir=registry_dir,
            unscoped_name="com.foo.bar",
            version="1.0.0",
            version_meta=dict(_VERSION_META),
            tarball_url=fallback,
            shasum="abc",
            integrity="sha512-x==",
            pages_base_url="https://owner.github.io/repo",
            # tarball_data intentionally omitted
        )
        doc = json.loads((registry_dir / "com.foo.bar").read_text())
        assert doc["versions"]["1.0.0"]["dist"]["tarball"] == fallback

    def test_raises_when_tarball_data_without_pages_base_url(
        self,
        publisher: PagesPublisher,
        registry_dir: Path,
    ) -> None:
        """Providing tarball_data without a valid pages_base_url raises."""
        with pytest.raises(ValueError, match="pages_base_url is required"):
            publisher.update_registry(
                registry_dir=registry_dir,
                unscoped_name="com.foo.bar",
                version="1.0.0",
                version_meta=dict(_VERSION_META),
                tarball_url="https://fallback/",
                shasum="abc",
                integrity="sha512-x==",
                tarball_data=b"data",
                pages_base_url=None,
            )

    def test_raises_when_tarball_data_with_blank_pages_base_url(
        self,
        publisher: PagesPublisher,
        registry_dir: Path,
    ) -> None:
        """Blank pages_base_url with tarball_data raises; no silent bad URL."""
        with pytest.raises(ValueError, match="pages_base_url is required"):
            publisher.update_registry(
                registry_dir=registry_dir,
                unscoped_name="com.foo.bar",
                version="1.0.0",
                version_meta=dict(_VERSION_META),
                tarball_url="https://fallback/",
                shasum="abc",
                integrity="sha512-x==",
                tarball_data=b"data",
                pages_base_url="   ",
            )
