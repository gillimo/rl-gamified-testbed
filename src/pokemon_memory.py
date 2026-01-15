from dataclasses import dataclass


@dataclass(frozen=True)
class MemoryMap:
    map_id: int
    player_y: int
    player_x: int
    player_direction: int
    in_battle: int


POKEMON_YELLOW = MemoryMap(
    map_id=0xD35E,
    player_y=0xD361,
    player_x=0xD362,
    player_direction=0xD35D,
    in_battle=0xD057,
)
