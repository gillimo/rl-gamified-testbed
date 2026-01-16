"""Pokemon Yellow Memory Addresses - From pokeyellow disassembly"""

# Party Pokemon (each is 44 bytes, party_struct)
PARTY_COUNT = 0xD162  # wPartyCount
PARTY_SPECIES = 0xD163  # 7 bytes (count + 6 species + terminator)
PARTY_MON_1 = 0xD16A
PARTY_STRUCT_SIZE = 44

# Party struct offsets (add to PARTY_MON_N base)
MON_SPECIES = 0
MON_HP = 1  # 2 bytes
MON_LEVEL_BOX = 3
MON_STATUS = 4
MON_TYPE1 = 5
MON_TYPE2 = 6
MON_MOVE_1 = 8
MON_MOVE_2 = 9
MON_MOVE_3 = 10
MON_MOVE_4 = 11
MON_EXP = 14  # 3 bytes
MON_DVS = 27  # 2 bytes (Attack/Defense, Speed/Special)
MON_PP_1 = 29
MON_PP_2 = 30
MON_PP_3 = 31
MON_PP_4 = 32
MON_LEVEL = 33
MON_MAX_HP = 34  # 2 bytes
MON_ATTACK = 36  # 2 bytes
MON_DEFENSE = 38  # 2 bytes
MON_SPEED = 40  # 2 bytes
MON_SPECIAL = 42  # 2 bytes

# Player data
PLAYER_MONEY = 0xD346  # 3 bytes BCD
PLAYER_ID = 0xD359  # 2 bytes (Red D35A -> Yellow D359?)
Y_COORD = 0xD361
X_COORD = 0xD360
CUR_MAP = 0xD35D  # wCurMapTileset? No wCurMap is D35E (Red) -> D35D (Yellow)

# Pokedex
POKEDEX_OWNED = 0xD2F6  # 19 bytes (151 bits)
POKEDEX_SEEN = 0xD30A   # 19 bytes

# Items
NUM_BAG_ITEMS = 0xD31C
BAG_ITEMS = 0xD31D  # Item pairs (ID, qty) up to 20 items

# Badges
OBTAINED_BADGES = 0xD355  # 1 byte bitflags

# Battle
IS_IN_BATTLE = 0xD056  # -1=lost, 0=none, 1=wild, 2=trainer
BATTLE_TYPE = 0xD057   # Wait, D057 is type? D056 is boolean?
CUR_ENEMY_LEVEL = 0xCFE8 # Red CFE9 -> Yellow CFE8?

# Text/Dialogue
TEXT_BOX_ID = 0xCF12
CURRENT_MENU_ITEM = 0xCC25

# Pokemon character encoding (subset)
CHAR_MAP = {
    0x50: "A", 0x51: "B", 0x52: "C", 0x53: "D", 0x54: "E", 0x55: "F", 0x56: "G",
    0x57: "H", 0x58: "I", 0x59: "J", 0x5A: "K", 0x5B: "L", 0x5C: "M", 0x5D: "N",
    0x5E: "O", 0x5F: "P", 0x60: "Q", 0x61: "R", 0x62: "S", 0x63: "T", 0x64: "U",
    0x65: "V", 0x66: "W", 0x67: "X", 0x68: "Y", 0x69: "Z", 0x6A: "(", 0x6B: ")",
    0x6C: ":", 0x6D: ";", 0x6E: "[", 0x6F: "]", 0x7F: " ", 0x4E: ".", 0x4F: ",",
    0xE1: "P", 0xE2: "O", 0xE3: "K", 0xE4: "é",  # POKé prefix
    0x00: " ", 0x50: "\x00",  # Terminator
}
