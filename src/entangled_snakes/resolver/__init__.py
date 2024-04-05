import packaging.utils
import packaging.version
from typing import NamedTuple


Identifier = NamedTuple(
    "Identifier",
    [
        ("name", packaging.utils.NormalizedName),
        ("extras", frozenset[packaging.utils.NormalizedName]),
    ],
)


class InvalidDistribution(Exception):
    pass


class UnsupportedFileType(InvalidDistribution):
    def __init__(self, filename):
        self.filename = filename
        super().__init__(f"Unsupported package file: {self.filename}")


class Distribution:
    name: packaging.utils.NormalizedName
    version: packaging.version.Version
    filename: str

    def __init__(self, filename: str) -> None:
        self.filename = filename

        if self.is_wheel:
            (
                self.name,
                self.version,
                self.build,
                self.tags,
            ) = packaging.utils.parse_wheel_filename(filename)
        elif self.is_sdist:
            self.name, self.version = packaging.utils.parse_sdist_filename(filename)
        else:
            raise UnsupportedFileType(self.filename)

    @property
    def is_wheel(self) -> bool:
        return self.filename.endswith(".whl")

    @property
    def is_sdist(self) -> bool:
        return self.filename.endswith(".tar.gz") or self.filename.endswith(".zip")

    @property
    def metadata_path(self) -> str:
        if self.is_wheel:
            distribution = self.filename.split("-")[0]
            return f"{distribution}-{self.version}.dist-info/METADATA"
        else:
            return f"{self.name}-{self.version}/PKG-INFO"
