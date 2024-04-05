from base64 import b64encode, b16decode
from typing import Optional

# from packaging.requirements import Requirement
from ..metadata import fetch_metadata

from . import Distribution


class Candidate:
    filename: str
    url: Optional[str]
    hashes: Optional[dict[str, str]]
    extras: Optional[set[str]]

    def __init__(self, filename, url=None, hashes=None, extras=frozenset({})):
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
    def name(self):
        return self.distribution.name

    @property
    def metadata(self):
        if self._metadata is None:
            self._metadata = fetch_metadata(self)
        return self._metadata
