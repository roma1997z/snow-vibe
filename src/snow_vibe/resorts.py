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


RESORTS: dict[str, Resort] = {
    BIGWOOD.slug: BIGWOOD,
    SHEREGESH.slug: SHEREGESH,
    ROSA_KHUTOR.slug: ROSA_KHUTOR,
}


def get_resort(slug: str) -> Resort:
    try:
        return RESORTS[slug]
    except KeyError as exc:
        known = ", ".join(sorted(RESORTS))
        raise KeyError(f"Unknown resort '{slug}'. Known resorts: {known}") from exc
