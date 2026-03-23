from __future__ import annotations

from snow_vibe.models import Coordinates, Resort, ResortSpot


BIGWOOD = Resort(
    slug="bigwood",
    name='BigWood ("Большой Вудъявр")',
    provider="met.no",
    address=(
        "Мурманская область, муниципальный округ Кировск, "
        "территория Горнолыжный курорт Большой Вудъявр, "
        "Северный склон горы Айкуайвенчорр, 3"
    ),
    timezone="Europe/Moscow",
    coordinates=Coordinates(lat=67.588147, lon=33.735538),
    spots=(
        ResortSpot(
            slug="resort_base",
            name="Base area",
            coordinates=Coordinates(lat=67.588147, lon=33.735538),
            description="OSM geocoding result for BigWood resort center.",
        ),
        ResortSpot(
            slug="peak",
            name="Aikuaivenchorr peak",
            coordinates=Coordinates(lat=67.608228, lon=33.781744),
            description="OSM geocoding result for Айкуайвенчорр peak.",
        ),
    ),
)

SHEREGESH = Resort(
    slug="sheregesh",
    name="Sheregesh",
    provider="met.no",
    address=(
        "Кемеровская область, Таштагольский муниципальный округ, "
        "город-курорт Шерегеш"
    ),
    timezone="Asia/Novokuznetsk",
    coordinates=Coordinates(lat=52.9518334, lon=87.9583696),
    spots=(
        ResortSpot(
            slug="resort_base",
            name="Base area",
            coordinates=Coordinates(lat=52.9518334, lon=87.9583696),
            description="OSM geocoding result for Sheregesh resort area.",
        ),
        ResortSpot(
            slug="green_mountain_peak",
            name="Green Mountain peak",
            coordinates=Coordinates(lat=52.949338, lon=87.928564),
            description="Public coordinates for Гора Зелёная near Sheregesh.",
        ),
    ),
)

ROSA_KHUTOR = Resort(
    slug="rosa-khutor",
    name="Rosa Khutor",
    provider="met.no",
    address=(
        "Краснодарский край, городской округ Сочи, "
        "Адлерский внутригородской район, Роза Хутор"
    ),
    timezone="Europe/Moscow",
    coordinates=Coordinates(lat=43.6709708, lon=40.2970765),
    spots=(
        ResortSpot(
            slug="rosa-dolina",
            name="Rosa Dolina",
            coordinates=Coordinates(lat=43.6709708, lon=40.2970765),
            description="OSM geocoding result for Rosa Khutor base area.",
        ),
        ResortSpot(
            slug="rosa-peak",
            name="Rosa Peak",
            coordinates=Coordinates(lat=43.6252855, lon=40.3100618),
            description="OSM geocoding result for Роза Пик station.",
        ),
    ),
)

GUBAKHA = Resort(
    slug="gubakha",
    name="Gubakha",
    provider="met.no",
    address="Пермский край, Губаха",
    timezone="Asia/Yekaterinburg",
    coordinates=Coordinates(lat=58.842407, lon=57.555058),
    spots=(
        ResortSpot(
            slug="resort_base",
            name="Base area",
            coordinates=Coordinates(lat=58.842407, lon=57.555058),
            description="OSM geocoding result for Gubakha town area.",
        ),
        ResortSpot(
            slug="krestovaya",
            name="Krestovaya area",
            coordinates=Coordinates(lat=58.8286111, lon=57.585),
            description="OSM point near Гора Крестовая, used as upper mountain point.",
        ),
    ),
)

MANZHEROK = Resort(
    slug="manzherok",
    name="Manzherok",
    provider="met.no",
    address="Республика Алтай, Манжерок",
    timezone="Asia/Barnaul",
    coordinates=Coordinates(lat=51.8296084, lon=85.7792275),
    spots=(
        ResortSpot(
            slug="resort_base",
            name="Base area",
            coordinates=Coordinates(lat=51.8296084, lon=85.7792275),
            description="OSM geocoding result for Manzherok village/base area.",
        ),
        ResortSpot(
            slug="malaya-sinyukha",
            name="Malaya Sinyukha peak",
            coordinates=Coordinates(lat=51.7910497, lon=85.8310884),
            description="OSM geocoding result for Малая Синюха near Manzherok.",
        ),
    ),
)

GUDAURI = Resort(
    slug="gudauri",
    name="Gudauri",
    provider="met.no",
    address="Gudauri, Mtskheta-Mtianeti, Georgia",
    timezone="Asia/Tbilisi",
    coordinates=Coordinates(lat=42.5090776, lon=44.49684),
    spots=(
        ResortSpot(
            slug="resort_base",
            name="Base area",
            coordinates=Coordinates(lat=42.5090776, lon=44.49684),
            description="OSM geocoding result for Gudauri Ski Resort.",
        ),
        ResortSpot(
            slug="sadzeli-peak",
            name="Sadzele peak",
            coordinates=Coordinates(lat=42.5124653, lon=44.512545),
            description="OSM geocoding result for Sadzele peak near Gudauri.",
        ),
    ),
)

AMIRSOY = Resort(
    slug="amirsoy",
    name="Amirsoy",
    provider="met.no",
    address="Bo'stonliq Tumani, Toshkent Viloyati, Oʻzbekiston",
    timezone="Asia/Tashkent",
    coordinates=Coordinates(lat=41.4865236, lon=69.9406929),
    spots=(
        ResortSpot(
            slug="resort_base",
            name="Base area",
            coordinates=Coordinates(lat=41.4865236, lon=69.9406929),
            description="OSM geocoding result for Amirsoy resort area.",
        ),
    ),
)

GORNY_VOZDUKH = Resort(
    slug="gorny-vozdukh",
    name="Gorny Vozdukh",
    provider="met.no",
    address="Южно-Сахалинск, Сахалинская область, Россия",
    timezone="Asia/Sakhalin",
    coordinates=Coordinates(lat=46.9564278, lon=142.7820353),
    spots=(
        ResortSpot(
            slug="resort_base",
            name="Base area",
            coordinates=Coordinates(lat=46.9564278, lon=142.7820353),
            description="OSM geocoding result for Горный воздух area in Yuzhno-Sakhalinsk.",
        ),
    ),
)

DOMBAY = Resort(
    slug="dombay",
    name="Dombay",
    provider="met.no",
    address="Карачаево-Черкесия, Домбай",
    timezone="Europe/Moscow",
    coordinates=Coordinates(lat=43.290498, lon=41.6269204),
    spots=(
        ResortSpot(
            slug="resort_base",
            name="Base area",
            coordinates=Coordinates(lat=43.290498, lon=41.6269204),
            description="OSM geocoding result for Dombay village.",
        ),
        ResortSpot(
            slug="dombay-ulgen",
            name="Dombay-Ulgen peak",
            coordinates=Coordinates(lat=43.2439005, lon=41.7257726),
            description="OSM geocoding result for Домбай-Ульген главная.",
        ),
    ),
)


RESORTS: dict[str, Resort] = {
    BIGWOOD.slug: BIGWOOD,
    SHEREGESH.slug: SHEREGESH,
    ROSA_KHUTOR.slug: ROSA_KHUTOR,
    GUBAKHA.slug: GUBAKHA,
    MANZHEROK.slug: MANZHEROK,
    GUDAURI.slug: GUDAURI,
    AMIRSOY.slug: AMIRSOY,
    GORNY_VOZDUKH.slug: GORNY_VOZDUKH,
    DOMBAY.slug: DOMBAY,
}


def get_resort(slug: str) -> Resort:
    try:
        return RESORTS[slug]
    except KeyError as exc:
        known = ", ".join(sorted(RESORTS))
        raise KeyError(f"Unknown resort '{slug}'. Known resorts: {known}") from exc
