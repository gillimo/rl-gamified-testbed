-- Pokemon Yellow Bridge - Clean output
local state_path = "C:/Users/gilli/OneDrive/Desktop/projects/pokemon_yellow_agent/data/emulator_state.json"
local input_path = "C:/Users/gilli/OneDrive/Desktop/projects/pokemon_yellow_agent/data/input_command.json"

memory.usememorydomain("System Bus")

local last_input_id = ""
local last_map = -1
local input_count = 0

local function write_state()
  local map_id = memory.read_u8(0xD35E)
  local payload = string.format(
      '{"timestamp":"%s","frame":%d,"map_id":%d,"player_y":%d,"player_x":%d,"player_direction":%d,"in_battle":%d}',
      os.date("!%Y-%m-%dT%H:%M:%SZ"), emu.framecount(), map_id,
      memory.read_u8(0xD361), memory.read_u8(0xD362),
      memory.read_u8(0xD35D), memory.read_u8(0xD057))
  local file = io.open(state_path, "w")
  if file then
    file:write(payload)
    file:close()
  end
  -- Only print on map change
  if map_id ~= last_map then
    print(string.format("MAP CHANGE: %d -> %d", last_map, map_id))
    last_map = map_id
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
  local frames = tonumber(content:match('"frames"%s*:%s*(%d+)')) or 1

  if not id or id == last_input_id or not button then return end
  last_input_id = id
  input_count = input_count + 1

  local btn_map = {
    A="A", B="B", START="Start", SELECT="Select",
    UP="Up", DOWN="Down", LEFT="Left", RIGHT="Right"
  }
  local mapped = btn_map[button:upper()]
  if not mapped then return end

  print(string.format("[INPUT #%d] %s x%d frames", input_count, mapped, frames))

  for i = 1, frames do
    joypad.set({[mapped] = true})
    emu.frameadvance()
  end

  local clear = io.open(input_path, "w")
  if clear then clear:write(""); clear:close() end
end

print("=== Pokemon Yellow Bridge ===")
print("Waiting for agent commands...")
while true do
  write_state()
  process_input()
  emu.frameadvance()
end
