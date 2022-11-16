from typing import List, Literal, Optional, TypedDict


class LocationInfo(TypedDict):
    """Location information from Geocoding API"""

    place_id: int
    licence: str
    lat: float
    lon: float
    display_name: str
    type: str
    importance: float
    icon: str


class _SnapLocaleText(TypedDict):
    """Snap locale text (localized titles)"""

    locale: str
    text: str


class _SnapTitle(TypedDict):
    """Snap title"""

    strings: List[_SnapLocaleText]
    fallback: str


class _SnapStreamingMediaInfo(TypedDict):
    """Snap information for videos"""

    prefixUrl: Optional[str]
    overlayUrl: Optional[str]
    previewUrl: Optional[str]
    previewWithOverlayUrl: Optional[str]
    mediaUrl: Optional[str]


class _SnapPublicImageMediaInfo(TypedDict):
    """Snap information for images"""

    mediaUrl: str


class _SnapPublicMediaInfo(TypedDict):
    """Snap information for images"""

    publicImageMediaInfo: _SnapPublicImageMediaInfo


class _SnapInfo(TypedDict):
    """Snap information"""

    snapMediaType: Optional[
        Literal["SNAP_MEDIA_TYPE_VIDEO", "SNAP_MEDIA_TYPE_VIDEO_NO_SOUND"]
    ]
    title: _SnapTitle
    streamingMediaInfo: _SnapStreamingMediaInfo
    publicMediaInfo: _SnapPublicMediaInfo
    overlayText: Optional[str]


class Snap(TypedDict):
    """Snap from a playlist"""

    id: str
    duration: int
    timestamp: str
    snapInfo: _SnapInfo
