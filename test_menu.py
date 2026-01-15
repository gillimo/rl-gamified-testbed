import agent_core
import time

print("Menu input test - focus BizHawk NOW!")
print("Will send: DOWN, DOWN, ENTER, Z")
time.sleep(3)

print("Pressing DOWN...")
agent_core.press_key("down")
time.sleep(0.3)

print("Pressing DOWN...")
agent_core.press_key("down")
time.sleep(0.3)

print("Pressing ENTER (Start)...")
agent_core.press_key("return")
time.sleep(0.3)

print("Pressing Z (A button)...")
agent_core.press_key("z")
time.sleep(0.3)

print("Done! Did the menu respond?")
