-- sprite_capture.lua — records what an NES game draws, for building a sprite profile.
--
-- Mesen 2 / MesenCE:
--   1. Debug > Script Window > Settings: turn on "Allow access to I/O and OS functions".
--   2. Load the game, open this file in the Script Window, and press Run.
--   3. Play. Get the player and every enemy you care about on screen; jump, shoot, get hit.
--   4. Press Stop. The capture is saved to LuaScriptData/sprite_capture/capture.jsonl
--      in your home folder (the path is printed in the Script Window log).
--
-- Each line of capture.jsonl is one distinct sprite arrangement: OAM (x, y, tile, attr),
-- the 16 bytes of every tile used, sprite size, and palette RAM. Nothing is written to the game.

local EVERY = 4            -- look at every 4th frame
local MAX_LINES = 20000    -- safety cap

local folder = emu.getScriptDataFolder()
if folder == nil or folder == "" then
  emu.displayMessage("Capture", "Turn on 'Allow access to I/O and OS functions' in Script Window settings, then run again.")
  emu.log("sprite_capture: I/O access is off. Script Window > Settings > 'Allow access to I/O and OS functions'.")
  return
end

local M = emu.memType
local OAM = M.nesSpriteRam
local PAL = M.nesPaletteRam
local PPU = M.nesPpuDebug or M.nesPpuMemory   -- debug variant reads without side effects
if OAM == nil or PAL == nil or PPU == nil then
  emu.log("sprite_capture: this doesn't look like an NES game (missing NES memory types).")
  return
end

local function jstr(s)
  return '"' .. tostring(s):gsub('[%c"\\]', function(c)
    if c == '"' then return '\\"' elseif c == "\\" then return "\\\\" end
    return string.format("\\u%04x", c:byte())
  end) .. '"'
end

-- PPU control flags, found by name so a renamed field shows up in the log instead of failing silently.
local function ppuFlag(state, name)
  local exact = state["ppu.control." .. name]
  if exact ~= nil then return exact end
  for k, v in pairs(state) do
    local lk = k:lower()
    if lk:find("ppu", 1, true) and lk:sub(-#name) == name:lower() then return v end
  end
  return nil
end

local path = folder .. "/capture.jsonl"
local out, err = io.open(path, "w")
if not out then emu.log("sprite_capture: can't write " .. path .. ": " .. tostring(err)); return end

local rom = emu.getRomInfo() or {}
local first = emu.getState()
local large0, sbase0 = ppuFlag(first, "largeSprites"), ppuFlag(first, "spritePatternAddr")
out:write(string.format('{"type":"header","format":"nes-sprite-capture/1","rom":%s,"sha1":%s,"every":%d,"largeKey":%s,"sbaseKey":%s}\n',
  jstr(rom.name or "?"), jstr(rom.fileSha1Hash or ""), EVERY, tostring(large0 ~= nil), tostring(sbase0 ~= nil)))
out:flush()
if large0 == nil or sbase0 == nil then
  emu.log("sprite_capture: couldn't find PPU sprite-size/pattern fields in emu.getState(); assuming 8x8 sprites at $0000.")
end

local frame, lines, seen = 0, 0, {}
local large, sbase, lastStateFrame = large0 == true, tonumber(sbase0) or 0, 0

emu.addEventCallback(function()
  frame = frame + 1
  emu.drawString(4, 4, "REC " .. lines, 0xFFFFFF, 0x000000, 0, 1, 0)
  if frame % EVERY ~= 0 or lines >= MAX_LINES then return end

  if frame - lastStateFrame >= 60 then  -- getState() serializes the whole console, so poll it sparingly
    local st = emu.getState()
    large = ppuFlag(st, "largeSprites") == true
    sbase = tonumber(ppuFlag(st, "spritePatternAddr")) or 0
    lastStateFrame = frame
  end

  local sprites, tiles, sigParts = {}, {}, {}
  for i = 0, 63 do
    local y = emu.read(i * 4, OAM, false)
    if y < 0xEF then
      local t = emu.read(i * 4 + 1, OAM, false)
      local a = emu.read(i * 4 + 2, OAM, false)
      local x = emu.read(i * 4 + 3, OAM, false)
      sprites[#sprites + 1] = string.format("[%d,%d,%d,%d]", x, y, t, a)
      local addrs
      if large then
        local base, tt = (t & 1) * 0x1000, t & 0xFE
        addrs = { base + tt * 16, base + (tt + 1) * 16 }
      else
        addrs = { sbase + t * 16 }
      end
      for _, ad in ipairs(addrs) do
        if tiles[ad] == nil then
          local b = {}
          for k = 0, 15 do b[k + 1] = string.format("%02x", emu.read(ad + k, PPU, false)) end
          tiles[ad] = table.concat(b)
        end
      end
      sigParts[#sigParts + 1] = t .. ":" .. (a & 0xE3)
    end
  end
  if #sprites == 0 then return end

  local tileList, tileSig = {}, {}
  for ad, hex in pairs(tiles) do tileList[#tileList + 1] = string.format('"%d":"%s"', ad, hex); tileSig[#tileSig + 1] = hex end
  table.sort(tileSig)
  local sig = table.concat(sigParts, ",") .. "|" .. table.concat(tileSig)
  if seen[sig] then return end
  seen[sig] = true

  local pal = {}
  for k = 0, 31 do pal[k + 1] = string.format("%02x", emu.read(k, PAL, false)) end

  out:write(string.format('{"type":"frame","n":%d,"large":%s,"sbase":%d,"pal":"%s","sprites":[%s],"tiles":{%s}}\n',
    frame, tostring(large), sbase, table.concat(pal), table.concat(sprites, ","), table.concat(tileList, ",")))
  lines = lines + 1
  if lines % 25 == 0 then out:flush() end
end, emu.eventType.endFrame)

emu.addEventCallback(function()
  out:write(string.format('{"type":"end","frames":%d,"lines":%d}\n', frame, lines))
  out:close()
  emu.log("sprite_capture: saved " .. lines .. " arrangements to " .. path)
end, emu.eventType.scriptEnded)

emu.log("sprite_capture: recording to " .. path .. " — play, then press Stop.")
emu.displayMessage("Capture", "Recording sprites. Press Stop in the Script Window when done.")
