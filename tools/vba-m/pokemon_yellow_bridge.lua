local output_path = "C:\\Users\\gilli\\OneDrive\\Desktop\\projects\\pokemon_yellow_agent\\data\\emulator_state.json"

local function read_u8(addr)
  return memory.readbyte(addr)
end

local function write_state()
  local state = {
    timestamp = os.date("!%Y-%m-%dT%H:%M:%SZ"),
    map_id = read_u8(0xD35E),
    player_y = read_u8(0xD361),
    player_x = read_u8(0xD362),
    player_direction = read_u8(0xD35D),
    in_battle = read_u8(0xD057),
  }

  local file = io.open(output_path, "w")
  if file then
    file:write(string.format(
      "{\"timestamp\":\"%s\",\"map_id\":%d,\"player_y\":%d,\"player_x\":%d,\"player_direction\":%d,\"in_battle\":%d}",
      state.timestamp,
      state.map_id,
      state.player_y,
      state.player_x,
      state.player_direction,
      state.in_battle
    ))
    file:close()
  end
end

while true do
  write_state()
  emu.frameadvance()
end
