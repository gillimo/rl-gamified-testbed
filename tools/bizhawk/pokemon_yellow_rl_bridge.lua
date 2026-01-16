-- Pokemon Yellow RL Bridge - Full memory state
local state_path = "C:/Users/gilli/OneDrive/Desktop/projects/pokemon_yellow_agent/data/emulator_state.json"
local input_path = "C:/Users/gilli/OneDrive/Desktop/projects/pokemon_yellow_agent/data/input_command.json"
local edit_path = "C:/Users/gilli/OneDrive/Desktop/projects/pokemon_yellow_agent/data/memory_edit.json"
local reset_path = "C:/Users/gilli/OneDrive/Desktop/projects/pokemon_yellow_agent/data/reset_command.json"

-- Wait for ROM to be loaded
print("Waiting for ROM to load...")
while emu.getsystemid() == "NULL" do
    emu.frameadvance()
end
print("ROM loaded: " .. emu.getsystemid())

memory.usememorydomain("System Bus")

-- Simple JSON encoder (BizHawk doesn't have json library)
local function json_encode(obj)
  local t = type(obj)
  if t == "nil" then return "null"
  elseif t == "boolean" then return obj and "true" or "false"
  elseif t == "number" then return tostring(obj)
  elseif t == "string" then return '"' .. obj:gsub('\\', '\\\\'):gsub('"', '\\"') .. '"'
  elseif t == "table" then
    local is_array = #obj > 0 or next(obj) == nil
    for k, _ in pairs(obj) do
      if type(k) ~= "number" then is_array = false; break end
    end
    local parts = {}
    if is_array then
      for i = 1, #obj do parts[i] = json_encode(obj[i]) end
      return "[" .. table.concat(parts, ",") .. "]"
    else
      for k, v in pairs(obj) do
        table.insert(parts, '"' .. tostring(k) .. '":' .. json_encode(v))
      end
      return "{" .. table.concat(parts, ",") .. "}"
    end
  end
  return "null"
end

-- Load memory editor
local mem_editor = dofile("C:/Users/gilli/OneDrive/Desktop/projects/pokemon_yellow_agent/tools/bizhawk/memory_editor.lua")

local last_input_id = ""
local last_reset_id = ""

-- Helper: Read 2-byte little-endian
local function read_u16(addr)
  return memory.read_u8(addr) + memory.read_u8(addr + 1) * 256
end

-- Helper: Read 3-byte BCD (money)
local function read_bcd(addr)
  local b1 = memory.read_u8(addr)
  local b2 = memory.read_u8(addr + 1)
  local b3 = memory.read_u8(addr + 2)
  return (b1 >> 4) * 100000 + (b1 & 0xF) * 10000 +
         (b2 >> 4) * 1000 + (b2 & 0xF) * 100 +
         (b3 >> 4) * 10 + (b3 & 0xF)
end

-- Helper: Count bits in byte array (Pokedex)
local function count_bits(addr, len)
  local count = 0
  for i = 0, len - 1 do
    local byte = memory.read_u8(addr + i)
    for b = 0, 7 do
      if (byte & (1 << b)) ~= 0 then count = count + 1 end
    end
  end
  return count
end

-- Helper: Read party Pokemon
local function read_party_mon(base_addr)
  if base_addr == 0 then return nil end
  return {
    species = memory.read_u8(base_addr + 0),
    hp = read_u16(base_addr + 1),
    level = memory.read_u8(base_addr + 33),
    max_hp = read_u16(base_addr + 34),
    attack = read_u16(base_addr + 36),
    defense = read_u16(base_addr + 38),
    speed = read_u16(base_addr + 40),
    special = read_u16(base_addr + 42),
    status = memory.read_u8(base_addr + 4),
    move_1 = memory.read_u8(base_addr + 8),
    move_2 = memory.read_u8(base_addr + 9),
    move_3 = memory.read_u8(base_addr + 10),
    move_4 = memory.read_u8(base_addr + 11),
    pp_1 = memory.read_u8(base_addr + 29),
    pp_2 = memory.read_u8(base_addr + 30),
    pp_3 = memory.read_u8(base_addr + 31),
    pp_4 = memory.read_u8(base_addr + 32),
  }
end

-- Pokemon Yellow WRAM addresses (Standard Yellow - Red/Blue minus 1)
local ADDR = {
  PARTY_COUNT    = 0xD162,  -- wPartyCount
  PARTY_MON1     = 0xD16A,  -- wPartyMon1 (44 bytes each)
  BADGES         = 0xD355,  -- wObtainedBadges
  MONEY          = 0xD346,  -- wPlayerMoney (3 bytes BCD)
  POKEDEX_OWNED  = 0xD2F6,  -- wPokedexOwned (19 bytes)
  POKEDEX_SEEN   = 0xD30A,  -- wPokedexSeen (19 bytes)
  NUM_ITEMS      = 0xD31C,  -- wNumBagItems
  Y_COORD        = 0xD361,  -- wYCoord
  X_COORD        = 0xD360,  -- wXCoord
  MAP_ID         = 0xD35D,  -- wCurMap
  BATTLE_TYPE    = 0xD056,  -- wIsInBattle (0=no, 1=wild, 2=trainer)
  TEXT_BOX       = 0xCF12,  -- wTextBoxID
  MENU_ITEM      = 0xCC25,  -- wCurrentMenuItem (Yellow)
}

local function write_state()
  local party_count = memory.read_u8(ADDR.PARTY_COUNT)
  local party = {}
  for i = 1, 6 do
    if i <= party_count then
      party[i] = read_party_mon(ADDR.PARTY_MON1 + (i - 1) * 44)
    else
      party[i] = nil
    end
  end

  local badges = memory.read_u8(ADDR.BADGES)
  local badge_count = 0
  for b = 0, 7 do
    if (badges & (1 << b)) ~= 0 then badge_count = badge_count + 1 end
  end

  local state = {
    frame = emu.framecount(),
    party_count = party_count,
    party = party,
    money = read_bcd(ADDR.MONEY),
    badges = badge_count,
    pokedex_owned = count_bits(ADDR.POKEDEX_OWNED, 19),
    pokedex_seen = count_bits(ADDR.POKEDEX_SEEN, 19),
    num_items = memory.read_u8(ADDR.NUM_ITEMS),
    x = memory.read_u8(ADDR.X_COORD),
    y = memory.read_u8(ADDR.Y_COORD),
    map = memory.read_u8(ADDR.MAP_ID),
    in_battle = memory.read_u8(ADDR.BATTLE_TYPE),
    text_box_id = memory.read_u8(ADDR.TEXT_BOX),
    menu_item = memory.read_u8(ADDR.MENU_ITEM),
  }

  local file = io.open(state_path, "w")
  if file then
    file:write(json_encode(state))
    file:close()
  end
end

local function process_input()
  local file = io.open(input_path, "r")
  if not file then return end
  local content = file:read("*all")
  file:close()
  if not content or content == "" then return end

  local id = content:match('"id"%s*:%s*"([^"]*)"')
  local button = content:match('"button"%s*:%s*"([^"]*)"')
  local frames = tonumber(content:match('"frames"%s*:%s*(%d+)')) or 4

  if not id or id == last_input_id or not button then return end
  last_input_id = id

  local btn_map = {
    A="A", B="B", START="Start", SELECT="Select",
    UP="Up", DOWN="Down", LEFT="Left", RIGHT="Right"
  }
  local mapped = btn_map[button:upper()]
  if not mapped then return end

  for i = 1, frames do
    joypad.set({[mapped] = true})
    emu.frameadvance()
  end

  local clear = io.open(input_path, "w")
  if clear then clear:write(""); clear:close() end
end

local function process_reset()
  local file = io.open(reset_path, "r")
  if not file then return end
  local content = file:read("*all")
  file:close()
  if not content or content == "" then return end

  local id = content:match('"id"%s*:%s*"([^"]*)"')
  local action = content:match('"action"%s*:%s*"([^"]*)"')
  local slot = tonumber(content:match('"slot"%s*:%s*(%d+)')) or 1

  if not id or id == last_reset_id then return end
  last_reset_id = id

  if action == "load_state" then
    print(">>> HARD RESET: Loading save state slot " .. slot .. " <<<")
    savestate.loadslot(slot)
    print(">>> Save state loaded! <<<")
  end

  -- Clear the file
  local clear = io.open(reset_path, "w")
  if clear then clear:write(""); clear:close() end
end

print("=== Pokemon Yellow RL Bridge ===")
print("Full memory state tracking")
print("Trade evolutions ENABLED (Haunter -> Gengar at level 25)")
print("Save state reset ENABLED")

local frame_count = 0
while true do
  write_state()
  process_input()
  process_reset()
  mem_editor.process_edits()

  -- Check trade evolutions every 60 frames (1 second)
  frame_count = frame_count + 1
  if frame_count % 60 == 0 then
    mem_editor.check_trade_evolutions()
  end

  emu.frameadvance()
end
