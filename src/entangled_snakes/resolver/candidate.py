from base64 import b64encode, b16decode
from typing import Optional

# from packaging.requirements import Requirement
# from .metadata import fetch_metadata

from . import Distribution


class Candidate:
    filename: str
    url: Optional[str]
    hashes: Optional[dict[str, str]]
    extras: Optional[set[str]]

    def __init__(self, filename, url=None, hashes=None, extras=None):
        self.filename = filename
        self.distribution = Distribution(filename)
        self.url = url
        self.hashes = hashes
        self.extras = extras

        self._metadata = None
        self._dependencies = None

    def __repr__(self):
        qualname = self.__class__.__qualname__
        if not self.extras:
            return (
                f"<{qualname}: {self.distribution.name}=={self.distribution.version}>"
            )
        return f"<{qualname}: {self.distribution.name}[{','.join(self.extras)}]=={self.distribution.version}>"

    @property
    def metadata(self):
        # if self._metadata is None:
        #    self._metadata = fetch_metadata(self)
        return self._metadata

    @property
    def requires_python(self):
        pass  # return self.metadata.get("Requires-Python")

    def _get_dependencies(self):
        pass
        # deps = self.metadata.get_all("Requires-Dist", [])
        # extras = self.extras if self.extras else [""]
        # for d in deps:
        #    r = Requirement(d.replace("\n", " "))
        #    if r.marker is None:
        #        yield r
        #    else:
        #        for e in extras:
        #            if r.marker.evaluate({"extra": e}):
        #                yield r

    @property
    def dependencies(self):
        # if self._dependencies is None:
        #    self._dependencies = list(self._get_dependencies())
        return self._dependencies

    def nix_hash(self) -> Optional[str]:
        typ = "sha256"
        if self.hashes and typ in self.hashes:
            nix_hash = b64encode(b16decode(self.hashes[typ].upper())).decode("utf-8")
            return f"{typ}-{nix_hash}"
