from __future__ import annotations

import hashlib
import re
import threading
from dataclasses import dataclass, field
from decimal import Decimal, InvalidOperation
from pathlib import Path
from typing import Callable, Iterable

from mutagen import File
from mutagen.id3 import ID3

SUPPORTED_EXTENSIONS = {".mp3", ".wav", ".flac", ".aif", ".aiff", ".m4a", ".aac", ".ogg", ".opus", ".wma"}

GROUPS = {
    "ARQUIVO": ["Filename", "Full Path", "Extension", "File Size", "Duration", "Scan Status"],
    "BÁSICOS": ["Title", "Artist", "Artists", "Album", "Album Artist", "Track", "Disc", "Genre", "Date", "Year"],
    "DJ": ["BPM", "Key", "Initial Key", "Energy", "Energy Raw", "Energy Source", "Energy Conflict", "Comment", "Rating"],
    "AVANÇADOS": ["ISRC", "Composer", "Remixer", "Version", "Label", "Publisher", "Copyright", "Grouping"],
    "TÉCNICOS": ["Codec", "Bitrate", "Sample Rate", "Channels"],
    "EXTRAS": ["Has Artwork", "Artwork Count", "Todas as tags RAW"],
}
DEFAULT_FIELDS = {
    "Filename", "Full Path", "Duration", "Scan Status", "Title", "Artist", "Album", "Genre", "Year", "BPM",
    "Key", "Initial Key", "Energy", "Energy Source", "Comment", "ISRC", "Codec", "Bitrate",
}

# Exact, field-specific whitelist. These are identities, not value guesses.
FIELD_ALIASES = {
    "Title": {"title", "tit2", "©nam", "inam"},
    "Artist": {"artist", "author", "tpe1", "©art"},
    "Artists": {"artists", "artist(s)", "performer", "tpe1"},
    "Album": {"album", "talb", "©alb", "wm/albumtitle"},
    "Album Artist": {"album artist", "albumartist", "aartist", "aart", "tpe2", "wm/albumartist"},
    "Track": {"track", "tracknumber", "trck", "trkn", "partofset", "wm/tracknumber"},
    "Disc": {"disc", "discnumber", "disk", "disknumber"},
    "Genre": {"genre", "tcon", "©gen", "wm/genre"},
    "Date": {"date", "year", "tdrc", "©day", "wm/year"},
    "Year": {"year", "date", "tdrc", "©day", "wm/year"},
    "BPM": {"bpm", "tbpm", "tempo", "tmpo", "wm/beatsperminute"},
    "Key": {"key", "tkey", "©key"},
    "Initial Key": {"initial key", "initialkey", "wm/initialkey"},
    "Comment": {"comment", "comments", "comm", "commentary", "©cmt", "description", "wm/comments"},
    "ISRC": {"isrc", "tsrc", "©isrc", "wm/isrc"},
    "Composer": {"composer", "tcom", "©wrt", "wm/composer"},
    "Remixer": {"remixer", "tpe4"},
    "Version": {"version", "mix", "subtitle", "tit3"},
    "Label": {"label", "organization", "tpbl"},
    "Publisher": {"publisher", "publishing", "tpub", "wm/publisher"},
    "Copyright": {"copyright", "tcop", "cprt"},
    "Grouping": {"grouping", "contentgroup", "©grp", "tit1"},
    "Rating": {"rating", "rtrating", "powm"},
    "Energy": {"energy", "energylevel", "energy level"},
}

BINARY_IDENTITIES = {"apic", "pic", "geob", "priv", "covr", "coverart", "cover art", "metadata_block_picture", "wm/picture"}
TXXX_FIELDS = {"Initial Key", "Energy", "BPM", "Key", "Publisher", "Label", "Rating", "ISRC", "Remixer", "Version"}
TEXTUAL_MP4_ENERGY_TAGS = {
    "----:com.apple.itunes:energylevel",
    "----:com.mixedinkey.mixedinkey:energy",
}


@dataclass(frozen=True)
class RawTag:
    name: str
    value: str
    source: str
    description: str = ""
    language: str = ""
    base_name: str = ""
    is_binary: bool = False

    def __iter__(self):
        yield self.name
        yield self.value
        yield self.source


@dataclass
class ScanResult:
    values: dict[str, object] = field(default_factory=dict)
    raw_tags: list[RawTag] = field(default_factory=list)
    error: tuple[str, str] | None = None


@dataclass
class ScanStats:
    found: int = 0
    supported: int = 0
    ignored_extension: int = 0
    processed: int = 0
    no_tags: int = 0
    read_errors: int = 0
    cancelled: bool = False
    ignored_files: list[Path] = field(default_factory=list)
    ignored_extensions: dict[str, int] = field(default_factory=dict)


def _text(value: object) -> str:
    if getattr(value, "FrameID", None) == "RVA2":
        # ChannelSpec accepts a byte (0..255), but Mutagen's __str__
        # indexes a nine-element channel-name list without checking it.
        return f"channel={value.channel}; gain={value.gain:+.4f} dB; peak={value.peak:.4f}"
    if isinstance(value, (list, tuple)):
        return "; ".join(_text(item) for item in value)
    if isinstance(value, bytes):
        return "[BINARY DATA - %d KB]" % max(1, len(value) // 1024)
    return str(value).strip()


def _binary_size(value: object) -> int:
    if isinstance(value, (bytes, bytearray)):
        return len(value)
    if isinstance(value, (list, tuple)):
        return sum(_binary_size(item) for item in value)
    data = getattr(value, "data", None)
    return len(data) if isinstance(data, (bytes, bytearray)) else 0


def _decode_textual_freeform(value: object) -> str | None:
    items = value if isinstance(value, (list, tuple)) else [value]
    decoded: list[str] = []
    for item in items:
        payload = bytes(item) if isinstance(item, (bytes, bytearray)) else None
        if payload is None:
            return None
        codecs = ["utf-8-sig"]
        if payload.startswith((b"\xff\xfe", b"\xfe\xff")):
            codecs.append("utf-16")
        codecs.append("cp1252")
        text = None
        for codec in codecs:
            try:
                text = payload.decode(codec).strip("\x00\ufeff ")
                break
            except UnicodeDecodeError:
                continue
        if text is None:
            return None
        decoded.append(text)
    return "; ".join(decoded)


def _raw_entries(tags: object) -> list[RawTag]:
    entries: list[RawTag] = []
    if not tags:
        return entries
    for key, frame in tags.items():
        name = str(key)
        base_name = str(getattr(frame, "FrameID", name))
        description = str(getattr(frame, "desc", "") or "")
        language = str(getattr(frame, "lang", "") or "")
        identity = base_name.casefold().strip()
        name_identity = name.casefold().strip()
        binary_size = _binary_size(frame)
        textual_freeform = name_identity in TEXTUAL_MP4_ENERGY_TAGS
        decoded_freeform = _decode_textual_freeform(frame) if textual_freeform else None
        is_binary = (binary_size > 0 and decoded_freeform is None) or identity in BINARY_IDENTITIES or name_identity in BINARY_IDENTITIES
        if any(name_identity.startswith(prefix) for prefix in ("apic:", "geob:", "priv:", "wm/picture")):
            is_binary = True
        if decoded_freeform is not None:
            value = decoded_freeform
        elif is_binary:
            value = f"[BINARY DATA - {max(1, binary_size // 1024)} KB]"
        else:
            payload = getattr(frame, "text", frame)
            value = _text(payload)
        entries.append(RawTag(name, value, type(tags).__name__, description, language, base_name, is_binary))
    return entries


def _freeform_identity(name: str) -> str | None:
    folded = name.casefold().strip()
    if folded.startswith("----:"):
        return folded.rsplit(":", 1)[-1].strip()
    return None


def _tag_matches(tag: RawTag, field_name: str) -> bool:
    if tag.is_binary:
        return False
    aliases = FIELD_ALIASES[field_name]
    base = tag.base_name.casefold().strip()
    name = tag.name.casefold().strip()
    source_is_id3 = base in {"comm", "txxx"} or base.startswith("t") or base in {"apic", "geob", "priv", "popm", "ufid", "uslt", "sylt"}

    if source_is_id3:
        if base == "comm":
            return field_name == "Comment"
        if base == "txxx":
            description = tag.description.casefold().strip()
            if field_name == "Energy":
                return re.sub(r"[\s_-]+", "", description) in {"energy", "energylevel"}
            return field_name in TXXX_FIELDS and description in aliases
        return base in aliases

    freeform = _freeform_identity(name)
    return name in aliases or base in aliases or (freeform is not None and freeform in aliases)


def _find_values(raw: Iterable[RawTag], field_name: str) -> list[str]:
    result: list[str] = []
    for tag in raw:
        if _tag_matches(tag, field_name) and tag.value and tag.value not in result:
            result.append(tag.value)
    return result


def _comment_energy(comments: list[str]) -> str | None:
    patterns = (
        r"\benergy\s*(?:level)?\s*[:=]?\s*([0-9]+(?:\.[0-9]+)?)\b",
        r"\b([0-9]+(?:\.[0-9]+)?)\s+energy\b",
    )
    for comment in comments:
        for pattern in patterns:
            match = re.search(pattern, comment, re.IGNORECASE)
            if match:
                return match.group(1)
    return None


def _energy_numbers(value: str) -> list[str]:
    return re.findall(r"(?<![\d.])[0-9]+(?:\.[0-9]+)?(?![\d.])", value)


def _canonical_number(value: str) -> Decimal | None:
    try:
        return Decimal(value)
    except (InvalidOperation, ValueError):
        return None


def make_file_id(path: Path) -> str:
    stat = path.stat()
    seed = str(path.resolve()).casefold() + "|" + str(stat.st_size)
    return hashlib.sha1(seed.encode("utf-8", "surrogatepass")).hexdigest()[:16]


def _base_values(path: Path, info: object | None) -> dict[str, object]:
    length = getattr(info, "length", None) if info else None
    return {
        "Filename": path.name,
        "Full Path": str(path.resolve()),
        "Extension": path.suffix.lower(),
        "File Size": path.stat().st_size,
        "Duration": f"{length:.2f}" if length is not None else "",
        "Duration Seconds": length if length is not None else "",
        "Codec": type(info).__name__.replace("Info", "") if info else "",
        "Bitrate": round(getattr(info, "bitrate", 0) / 1000) if info and getattr(info, "bitrate", None) else "",
        "Sample Rate": getattr(info, "sample_rate", "") if info else "",
        "Channels": getattr(info, "channels", "") if info else "",
    }


def scan_one(path: Path) -> ScanResult:
    audio = None
    open_error: Exception | None = None
    try:
        audio = File(str(path), easy=False)
    except Exception as exc:
        open_error = exc

    raw = _raw_entries(getattr(audio, "tags", None)) if audio else []
    if path.suffix.casefold() == ".mp3" and not raw:
        try:
            raw = _raw_entries(ID3(str(path)))
        except Exception:
            pass

    info = getattr(audio, "info", None)
    try:
        values = _base_values(path, info)
    except Exception as exc:
        return ScanResult({"Filename": path.name, "Full Path": str(path), "Extension": path.suffix.lower(), "Scan Status": "METADATA_READ_ERROR"}, [], (type(exc).__name__, str(exc)))

    if audio is None and not raw:
        error = open_error or ValueError("Arquivo não pôde ser aberto pelo Mutagen")
        values["Scan Status"] = "METADATA_READ_ERROR"
        return ScanResult(values, [], (type(error).__name__, str(error)))

    comments = _find_values(raw, "Comment")
    for field_name in FIELD_ALIASES:
        if field_name != "Energy":
            values[field_name] = "; ".join(_find_values(raw, field_name))

    explicit_energy_tags: list[tuple[RawTag, list[str]]] = []
    for tag in raw:
        if _tag_matches(tag, "Energy"):
            numbers = _energy_numbers(tag.value)
            if numbers:
                explicit_energy_tags.append((tag, numbers))
    comment_energies = [(comment, energy) for comment in comments if (energy := _comment_energy([comment])) is not None]

    valid_numbers = [_canonical_number(number) for _, numbers in explicit_energy_tags for number in numbers]
    valid_numbers.extend(_canonical_number(number) for _, number in comment_energies)
    distinct_numbers = {number for number in valid_numbers if number is not None}

    if explicit_energy_tags:
        source_tag, source_numbers = explicit_energy_tags[0]
        energy = source_numbers[0]
        values["Energy"] = energy
        values["Energy Raw"] = source_tag.value
        normalized_description = re.sub(r"[\s_-]+", "", source_tag.description.casefold())
        values["Energy Source"] = "TXXX:EnergyLevel" if source_tag.base_name.casefold() == "txxx" and normalized_description == "energylevel" else source_tag.name
    elif comment_energies:
        raw_comment, energy = comment_energies[0]
        values["Energy"] = energy
        values["Energy Raw"] = raw_comment
        values["Energy Source"] = "COMMENT"
    else:
        values["Energy"] = values["Energy Raw"] = values["Energy Source"] = ""
    values["Energy Conflict"] = len(distinct_numbers) > 1
    values["Comment"] = " | ".join(comments)

    artwork_tags = [tag for tag in raw if tag.is_binary and any(marker in tag.name.casefold() for marker in ("apic", "pic", "covr", "cover", "picture"))]
    values["Has Artwork"] = bool(artwork_tags)
    values["Artwork Count"] = len(artwork_tags)

    meaningful = any(values.get(field) for field in ("Title", "Artist", "Album", "Genre", "BPM", "Key", "Initial Key", "Comment", "Energy", "ISRC"))
    if not raw:
        values["Scan Status"] = "NO_TAGS"
    elif meaningful and values.get("Title") and values.get("Artist"):
        values["Scan Status"] = "OK"
    else:
        values["Scan Status"] = "PARTIAL_METADATA"
    return ScanResult(values, raw)


def inventory_files(folder: Path, recursive: bool) -> tuple[list[Path], ScanStats]:
    iterator = folder.rglob("*") if recursive else folder.glob("*")
    all_files = [path for path in iterator if path.is_file()]
    supported = [path for path in all_files if path.suffix.casefold() in SUPPORTED_EXTENSIONS]
    ignored = [path for path in all_files if path.suffix.casefold() not in SUPPORTED_EXTENSIONS]
    ignored_extensions: dict[str, int] = {}
    for path in ignored:
        extension = path.suffix.lower() or "[NO EXTENSION]"
        ignored_extensions[extension] = ignored_extensions.get(extension, 0) + 1
    return supported, ScanStats(found=len(all_files), supported=len(supported), ignored_extension=len(ignored), ignored_files=ignored, ignored_extensions=ignored_extensions)


def iter_audio_files(folder: Path, recursive: bool) -> list[Path]:
    return inventory_files(folder, recursive)[0]


def scan_library(folder: Path, recursive: bool, cancel: threading.Event, progress: Callable[[int, int, Path, int], None] | None = None):
    files, stats = inventory_files(folder, recursive)
    results: list[tuple[Path, ScanResult]] = []
    errors: list[tuple[Path, str, str]] = []
    for index, path in enumerate(files, 1):
        if cancel.is_set():
            break
        try:
            result = scan_one(path)
        except Exception as exc:
            import traceback
            result = ScanResult({"Filename": path.name, "Full Path": str(path), "Scan Status": "METADATA_READ_ERROR"}, [], (type(exc).__name__, traceback.format_exc()))
        results.append((path, result))
        if result.error:
            errors.append((path, result.error[0], result.error[1]))
        if result.values.get("Scan Status") == "NO_TAGS":
            stats.no_tags += 1
        stats.processed += 1
        stats.read_errors = len(errors)
        if progress and (index == 1 or index == len(files) or index % 25 == 0):
            progress(index, len(files), path, len(errors))
    stats.cancelled = cancel.is_set()
    return files, results, errors, stats.cancelled, stats
