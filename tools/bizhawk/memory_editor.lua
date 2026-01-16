-- Memory Editor for Pokemon Yellow - Modify game state
local edit_path = "C:/Users/gilli/OneDrive/Desktop/projects/pokemon_yellow_agent/data/memory_edit.json"

memory.usememorydomain("System Bus")

-- Helper: Write 2-byte little-endian
local function write_u16(addr, value)
  memory.write_u8(addr, value & 0xFF)
  memory.write_u8(addr + 1, (value >> 8) & 0xFF)
end

-- Helper: Write 3-byte BCD (money)
local function write_bcd(addr, value)
  local d1 = (value // 100000) % 10
  local d2 = (value // 10000) % 10
  local d3 = (value // 1000) % 10
  local d4 = (value // 100) % 10
  local d5 = (value // 10) % 10
  local d6 = value % 10
  memory.write_u8(addr, d1 * 16 + d2)
  memory.write_u8(addr + 1, d3 * 16 + d4)
  memory.write_u8(addr + 2, d5 * 16 + d6)
end

-- Set party Pokemon
function set_party_pokemon(slot, species, level, hp, max_hp, attack, defense, speed, special)
  local base = 0xC210 + (slot - 1) * 44

  -- Species
  memory.write_u8(base + 0, species)
  -- HP
  write_u16(base + 1, hp or max_hp or 100)
  -- Level (box and actual)
  memory.write_u8(base + 3, level)
  memory.write_u8(base + 33, level)
  -- Stats
  write_u16(base + 34, max_hp or 100)
  write_u16(base + 36, attack or 50)
  write_u16(base + 38, defense or 50)
  write_u16(base + 40, speed or 50)
  write_u16(base + 42, special or 50)
  -- Status (clear)
  memory.write_u8(base + 4, 0)

  -- Update species list
  memory.write_u8(0xC20B + slot - 1, species)
end

-- Process edit commands
local function process_edits()
  local file = io.open(edit_path, "r")
  if not file then return end

  local content = file:read("*all")
  file:close()

  if not content or content == "" then return end

  -- Parse JSON manually (simple)
  local cmd = content:match('"cmd"%s*:%s*"([^"]*)"')

  if cmd == "set_starter" then
    local species = tonumber(content:match('"species"%s*:%s*(%d+)'))
    local level = tonumber(content:match('"level"%s*:%s*(%d+)')) or 5

    if species then
      -- Set party count to 1
      memory.write_u8(0xC20A, 1)
      -- Set starter
      set_party_pokemon(1, species, level, nil, 30, 30, 30, 30, 30)
      print(string.format("SET STARTER: Species %d, Level %d", species, level))
    end

  elseif cmd == "give_money" then
    local amount = tonumber(content:match('"amount"%s*:%s*(%d+)'))
    if amount then
      write_bcd(0xC465, amount)
      print(string.format("GAVE MONEY: %d", amount))
    end

  elseif cmd == "give_badges" then
    local badges = tonumber(content:match('"badges"%s*:%s*(%d+)')) or 8
    local badge_byte = (1 << badges) - 1  -- All badges up to N
    memory.write_u8(0xC473, badge_byte)
    print(string.format("GAVE BADGES: %d", badges))

  elseif cmd == "teleport" then
    local map = tonumber(content:match('"map"%s*:%s*(%d+)'))
    local x = tonumber(content:match('"x"%s*:%s*(%d+)'))
    local y = tonumber(content:match('"y"%s*:%s*(%d+)'))
    if map and x and y then
      memory.write_u8(0xC4AA, map)
      memory.write_u8(0xC4A2, x)
      memory.write_u8(0xC4A1, y)
      print(string.format("TELEPORT: Map %d, (%d, %d)", map, x, y))
    end
  end

  -- Clear edit file
  local clear = io.open(edit_path, "w")
  if clear then clear:write(""); clear:close() end
end

-- Auto-evolve trade evolutions at normal stage 3 level (40)
local trade_evolutions = {
  [64] = {evolved = 65, level = 40},   -- Kadabra -> Alakazam
  [67] = {evolved = 68, level = 40},   -- Machoke -> Machamp
  [75] = {evolved = 76, level = 40},   -- Graveler -> Golem
  [93] = {evolved = 94, level = 40},   -- Haunter -> Gengar
}

function check_trade_evolutions()
  local party_count = memory.read_u8(0xC20A)
  for i = 1, party_count do
    local base = 0xC210 + (i - 1) * 44
    local species = memory.read_u8(base + 0)
    local level = memory.read_u8(base + 33)

    -- If trade evolution species and at evolution level, evolve
    if trade_evolutions[species] and level >= trade_evolutions[species].level then
      local evolved = trade_evolutions[species].evolved
      memory.write_u8(base + 0, evolved)
      memory.write_u8(0xC20B + i - 1, evolved)
      print(string.format("EVOLVED: Species %d -> %d at level %d", species, evolved, level))
    end
  end
end

return {
  process_edits = process_edits,
  set_party_pokemon = set_party_pokemon,
  check_trade_evolutions = check_trade_evolutions
}
