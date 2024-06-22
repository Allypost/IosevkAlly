import functools
import itertools
import os.path
from copy import deepcopy
from dataclasses import dataclass, field
from enum import StrEnum
from pathlib import Path
from typing import Self

import fontTools.ttLib
import fontTools.unicode

from common.helpers import CssStr, css_stringify, ints_to_unicode_range

FONT_WEIGHT_NAME_TO_VALUE = {
    "thin": 100,
    "extralight": 200,
    "light": 300,
    "normal": 400,
    "regular": 400,
    "italic": 400,
    "medium": 500,
    "semibold": 600,
    "bold": 700,
    "extrabold": 800,
    "black": 900,
    "heavy": 900,
}


class Console:
    _indent_level = 0

    @classmethod
    def log(
        cls,
        *args: object,
        sep: str | None = " ",
        end: str | None = "\n",
        file=None,
        flush: bool = True,
        in_group: bool = True,
        **kwargs,
    ):
        print(
            (" " * cls._indent_level) if in_group else "",
            *args,
            sep=sep,
            end=end,
            file=file,
            flush=flush,
            **kwargs,
        )
        return cls

    @classmethod
    def group(cls, *args: object):
        return cls.log(*args)._add_indent_level(2)

    @classmethod
    def grouped(cls, *console_args: str):
        def decorator(func):
            @functools.wraps(func)
            def wrapper(*args, **kwargs):
                cls.group(*map(lambda x: x.format(*args, **kwargs), console_args))
                ret = func(*args, **kwargs)
                cls.group_end()
                return ret

            return wrapper

        return decorator

    @classmethod
    def group_end(cls):
        return cls._add_indent_level(-2)

    @classmethod
    def _add_indent_level(cls, delta: int):
        cls._indent_level = max(0, cls._indent_level + delta)
        return cls


class Subset(StrEnum):
    Arabic = "arabic"
    Bengali = "bengali"
    Cyrillic = "cyrillic"
    CyrillicExt = "cyrillic-ext"
    Devanagari = "devanagari"
    Georgian = "georgian"
    Greek = "greek"
    GreekExt = "greek-ext"
    Gujarati = "gujarati"
    Gurmukhi = "gurmukhi"
    Hebrew = "hebrew"
    Kannada = "kannada"
    Khmer = "khmer"
    Latin = "latin"
    LatinExt = "latin-ext"
    Malayalam = "malayalam"
    Myanmar = "myanmar"
    Oriya = "oriya"
    Sinhala = "sinhala"
    Tamil = "tamil"
    Telugu = "telugu"
    Thai = "thai"
    Tibetan = "tibetan"
    Vietnamese = "vietnamese"

    def as_unicode_range(self) -> list[str]:
        match self:
            case self.Arabic:
                return [
                    "U+0600-06FF",
                    "U+200C-200E",
                    "U+2010-2011",
                    "U+204F",
                    "U+2E41",
                    "U+FB50-FDFF",
                    "U+FE80-FEFC",
                ]
            case self.Bengali:
                return [
                    "U+0964-0965",
                    "U+0981-09FB",
                    "U+200C-200D",
                    "U+20B9",
                    "U+25CC",
                ]
            case self.Cyrillic:
                return ["U+0400-045F", "U+0490-0491", "U+04B0-04B1", "U+2116"]
            case self.CyrillicExt:
                return [
                    "U+0460-052F",
                    "U+1C80-1C88",
                    "U+20B4",
                    "U+2DE0-2DFF",
                    "U+A640-A69F",
                    "U+FE2E-FE2F",
                ]
            case self.Devanagari:
                return [
                    "U+0900-097F",
                    "U+1CD0-1CF6",
                    "U+1CF8-1CF9",
                    "U+200C-200D",
                    "U+20A8",
                    "U+20B9",
                    "U+25CC",
                    "U+A830-A839",
                    "U+A8E0-A8FB",
                ]
            case self.Georgian:
                return ["U+10A0-10FF"]
            case self.Greek:
                return ["U+0370-03FF"]
            case self.GreekExt:
                return ["U+1F00-1FFF"]
            case self.Gujarati:
                return [
                    "U+0964-0965",
                    "U+0A80-0AFF",
                    "U+200C-200D",
                    "U+20B9",
                    "U+25CC",
                    "U+A830-A839",
                ]
            case self.Gurmukhi:
                return [
                    "U+0964-0965",
                    "U+0A01-0A75",
                    "U+200C-200D",
                    "U+20B9",
                    "U+25CC",
                    "U+262C",
                    "U+A830-A839",
                ]
            case self.Hebrew:
                return ["U+0590-05FF", "U+20AA", "U+25CC", "U+FB1D-FB4F"]
            case self.Kannada:
                return [
                    "U+0964-0965",
                    "U+0C82-0CF2",
                    "U+200C-200D",
                    "U+20B9",
                    "U+25CC",
                ]
            case self.Khmer:
                return ["U+1780-17FF", "U+200C", "U+25CC"]
            case self.Latin:
                return [
                    "U+0000-00FF",
                    "U+0131",
                    "U+0152-0153",
                    "U+02BB-02BC",
                    "U+02C6",
                    "U+02DA",
                    "U+02DC",
                    "U+2000-206F",
                    "U+2074",
                    "U+20AC",
                    "U+2122",
                    "U+2191",
                    "U+2193",
                    "U+2212",
                    "U+2215",
                    "U+FEFF",
                    "U+FFFD",
                ]
            case self.LatinExt:
                return [
                    "U+0100-024F",
                    "U+0259",
                    "U+1E00-1EFF",
                    "U+2020",
                    "U+20A0-20AB",
                    "U+20AD-20CF",
                    "U+2113",
                    "U+2C60-2C7F",
                    "U+A720-A7FF",
                ]
            case self.Malayalam:
                return [
                    "U+0307",
                    "U+0323",
                    "U+0964-0965",
                    "U+0D02-0D7F",
                    "U+200C-200D",
                    "U+20B9",
                    "U+25CC",
                ]
            case self.Myanmar:
                return ["U+1000-109F", "U+200C-200D", "U+25CC"]
            case self.Oriya:
                return [
                    "U+0964-0965",
                    "U+0B01-0B77",
                    "U+200C-200D",
                    "U+20B9",
                    "U+25CC",
                ]
            case self.Sinhala:
                return ["U+0964-0965", "U+0D82-0DF4", "U+200C-200D", "U+25CC"]
            case self.Tamil:
                return [
                    "U+0964-0965",
                    "U+0B82-0BFA",
                    "U+200C-200D",
                    "U+20B9",
                    "U+25CC",
                ]
            case self.Telugu:
                return [
                    "U+0951-0952",
                    "U+0964-0965",
                    "U+0C00-0C7F",
                    "U+1CDA",
                    "U+200C-200D",
                    "U+25CC",
                ]
            case self.Thai:
                return ["U+0E01-0E5B", "U+200C-200D", "U+25CC"]
            case self.Tibetan:
                return ["U+0F00-0FFF", "U+200C-200D", "U+25CC"]
            case self.Vietnamese:
                return ["U+0102-0103", "U+0110-0111", "U+1EA0-1EF9", "U+20AB"]
        return []

    @classmethod
    def all(cls) -> list[Self]:
        return list(cls)

    def __repr__(self):
        return f"{self.__class__.__name__}.{self.name}"


@dataclass(kw_only=True)
class FontFile:
    file_path: Path
    format: str
    relative_to_path: Path | None = None
    _unicodes_available: list[int] | None = None

    @classmethod
    def from_path(cls, path: str | Path, format: str | None = None):
        p = Path(path)
        format = format or p.suffix.strip(".")
        return cls(file_path=p, format=format)

    def with_relative_to_path(self, relative_to_path: str | Path | None):
        if relative_to_path is None:
            return self
        new = deepcopy(self)
        if not os.path.isdir(relative_to_path):
            relative_to_path = os.path.dirname(relative_to_path)
        new.relative_to_path = Path(relative_to_path)
        return new

    @property
    def file_path_relative(self):
        if self.relative_to_path:
            return os.path.relpath(self.file_path, self.relative_to_path)
        return self.file_path

    def dir_name(self):
        return os.path.dirname(self.file_path)

    def file_name(self):
        return os.path.basename(self.file_path)

    def file_name_without_ext(self):
        return os.path.splitext(self.file_name())[0]

    def as_dict(self) -> dict[str, str]:
        return {"url": str(self.file_path_relative), "format": self.format}

    def available_unicode_characters(self) -> list[int]:
        if self._unicodes_available is not None:
            return self._unicodes_available

        with fontTools.ttLib.TTFont(file=self.file_path) as ttf:
            chars = itertools.chain.from_iterable(
                [y for y in x.cmap.keys()]
                for x in ttf["cmap"].tables  # type: ignore
            )
        self._unicodes_available = sorted(set(chars))

        return self._unicodes_available


@dataclass(kw_only=True)
class FontSubset:
    file: FontFile
    unicode_range: list[str] | set[str]


@dataclass(kw_only=True)
class FontVariant:
    """
    A font variant.
    eg. Bold Italic, Black, Condensed Italic, etc.
    """

    file: FontFile
    weight: int
    style: str | CssStr
    stretch: CssStr | None = None
    subsets: list[FontSubset] = field(default_factory=list)

    def to_css_font_faces(
        self,
        *,
        font_family: str | CssStr,
        relative_to_path: str | Path | None = None,
        with_main_font: bool = False,
    ):
        base_props = {
            "font-family": font_family,
            "font-weight": self.weight,
            "font-style": self.style,
            # "font-display": CssStr("swap"),
        }
        if self.stretch:
            base_props["font-stretch"] = self.stretch

        for subset in self.subsets:
            props = {
                **base_props,
                "unicode-range": list(map(CssStr, subset.unicode_range)),
                "src": [
                    # {
                    #     "local": font_family,
                    # },
                    subset.file.with_relative_to_path(relative_to_path).as_dict(),
                ],
            }
            yield self._to_font_face(props)

        if with_main_font:
            props = {
                **base_props,
                "unicode-range": list(
                    map(
                        CssStr,
                        ints_to_unicode_range(self.file.available_unicode_characters()),
                    )
                ),
                "src": [
                    # {
                    #     "local": font_family,
                    # },
                    self.file.with_relative_to_path(relative_to_path).as_dict(),
                ],
            }
            yield self._to_font_face(props)

    @staticmethod
    def _to_font_face(props: dict[str, str]) -> str:
        s = "@font-face{"
        s += ";".join([f"{k}:{css_stringify(v)}" for k, v in props.items()])
        s += "}"
        return s

    def to_css_font_face(
        self,
        *,
        font_family: str | CssStr,
        relative_to_path: str | Path | None = None,
    ):
        props = {
            "font-family": font_family,
            "font-weight": self.weight,
            "font-style": self.style,
            "src": [
                {
                    "local": font_family,
                },
                self.file.with_relative_to_path(relative_to_path).as_dict(),
            ],
        }
        if self.stretch:
            props["font-stretch"] = self.stretch

        return self._to_font_face(props)

    @classmethod
    def from_file_path(cls, font_file_path: str | Path):
        # /a/path/to/My Font Name-BoldItalic.woff2 -> My Font Name-BoldItalic.woff2
        font_file_name = os.path.basename(font_file_path)
        # My Font Name-BoldItalic.woff2 -> My Font Name-BoldItalic -> BoldItalic -> bolditalic
        params = os.path.splitext(font_file_name)[0].split("-")[-1].lower()

        try:
            weight = next(
                (
                    v
                    for k, v in FONT_WEIGHT_NAME_TO_VALUE.items()
                    if params.startswith(k)
                )
            )
        except StopIteration:
            Console.log("=" * 80)
            Console.log(f"WARNING! Unknown weight `{params}` for `{font_file_path}`")
            Console.log("=" * 80)
            weight = FONT_WEIGHT_NAME_TO_VALUE["normal"]

        return cls(
            file=FontFile.from_path(path=font_file_path),
            weight=weight,
            style=CssStr("italic" if "italic" in params else "normal"),
        )


@dataclass(kw_only=True)
class Webfont:
    name: str
    variants: list[FontVariant] = field(default_factory=list)
