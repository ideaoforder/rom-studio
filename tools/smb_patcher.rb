#!/usr/bin/env ruby
# frozen_string_literal: true
#
# smb_patcher.rb — Super Mario Bros. (NES, World/USA) player sprite, palette,
# and name patcher. Pure Ruby stdlib (json, zlib) — no gems.
#
#   ruby smb_patcher.rb dump  smb.nes [workdir] [--palette player1|player2|fire]
#   ruby smb_patcher.rb pose  workdir/config.json
#   ruby smb_patcher.rb build workdir/config.json
#   ruby smb_patcher.rb parts workdir/config.json
#   ruby smb_patcher.rb colors [out.png]
#
# dump  -> parts.png (paint these), rig.yml (poses), config.json — each only
#          if missing — plus frames.png, sprites.png, nes_colors.png
# pose  -> parts.png + rig.yml rendered into frames.png (no ROM written)
# build -> pose (if config has "rig"), then patched ROM, .ips, optional .chr,
#          and <output>.preview.png
# parts -> re-lay-out parts.png after editing part sizes in rig.yml (keeps art)
#
# Remove "rig" from config.json to hand-edit frames.png directly instead.
# Round-trip guarantee: without "rig", dump then build with no edits produces a
# byte-identical ROM.

require "json"
require "zlib"
require "pathname"
require "fileutils"
require_relative "smb_rig"

module SMB
  # ---------------------------------------------------------------- NES colors
  NES_RGB = %w[
    7C7C7C 0000FC 0000BC 4428BC 940084 A80020 A81000 881400 503000 007800 006800 005800 004058 000000 000000 000000
    BCBCBC 0078F8 0058F8 6844FC D800CC E40058 F83800 E45C10 AC7C00 00B800 00A800 00A844 008888 000000 000000 000000
    F8F8F8 3CBCFC 6888FC 9878F8 F878F8 F85898 F87858 FCA044 F8B800 B8F818 58D854 58F898 00E8D8 787878 000000 000000
    FCFCFC A4E4FC B8B8F8 D8B8F8 F8B8F8 F8A4C0 F0D0B0 FCE0A8 F8D878 D8F878 B8F8B8 B8F8D8 00FCFC F8D8F8 000000 000000
  ].map { |h| [h[0, 2], h[2, 2], h[4, 2]].map { |c| c.to_i(16) } }.freeze

  GUTTER_RGB = [0x2B, 0x2B, 0x2B].freeze

  # ------------------------------------------------------------- ROM layout
  # File offsets for Super Mario Bros. (World) — the standard US cart.
  CHR_OFFSET       = 0x8010
  GFX_OFFSETS      = 0x6E17 # PlayerGfxTblOffsets (used only to validate)
  GFX_TABLE        = 0x6E27 # PlayerGraphicsTable, 26 frames x 8 tiles
  SWIM_KICK        = 0x6EF7 # SwimKickTileNum (big, small)
  PLAYER_COLORS    = 0x05E7 # 3 x [bg, c1, c2, c3]
  BLANK_TILE       = 0xFC

  # [offset, context_offset, context_bytes, length, kind]
  NAME_SLOTS = {
    player1: [
      [0x0765, 0x0762, [0x20, 0x43, 0x05], 5, :hud],     # status bar
      [0x07AB, 0x07A8, [0x21, 0xCD, 0x05], 5, :hud],     # 2P time up
      [0x07BE, 0x07BB, [0x21, 0xCD, 0x05], 5, :hud],     # 2P game over
      [0x0D71, 0x0D64, [0x25, 0x48, 0x10], 6, :thanks]   # THANK YOU MARIO!
    ],
    player2: [
      [0x07FD, 0x0802, [0x04, 0x03, 0x02, 0x00], 5, :hud], # LuigiName
      [0x0D85, 0x0D78, [0x25, 0x48, 0x10], 6, :thanks]     # THANK YOU LUIGI!
    ]
  }.freeze

  # Frame list: [name, table offset, flip rule]. Flip rules mirror the game's
  # ChkForPlayerAttrib: some poses reuse one tile for both halves of a row.
  BIG = [
    ["big walk 1", 0x00], ["big walk 2", 0x08], ["big walk 3", 0x10], ["big skid", 0x18],
    ["big jump", 0x20], ["big swim 1", 0x28], ["big swim 2", 0x30], ["big swim 3", 0x38],
    ["big climb 1", 0x40], ["big climb 2", 0x48], ["big crouch", 0x50, [3]], ["big fire throw", 0x58],
    ["big swim kick", 0x28, nil, 0]
  ].freeze
  SMALL = [
    ["small walk 1", 0x60], ["small walk 2", 0x68], ["small walk 3", 0x70], ["small skid", 0x78],
    ["small jump", 0x80], ["small swim 1", 0x88], ["small swim 2", 0x90], ["small swim 3", 0x98],
    ["small climb 1", 0xA0], ["small climb 2", 0xA8], ["small killed", 0xB0, [2, 3]],
    ["small swim kick", 0x88, nil, 1]
  ].freeze
  SHARED = [
    ["small standing", 0xB8, [3]], ["growing", 0xC0, [3]], ["big standing", 0xC8, [3]]
  ].freeze
  ROWS = [BIG, SMALL, SHARED].freeze

  CELL_W = 16
  CELL_H = 32
  GUTTER = 8

  # ------------------------------------------------------------- text codec
  def self.encode_text(str)
    str.upcase.chars.map do |ch|
      case ch
      when "0".."9" then ch.ord - 48
      when "A".."Z" then ch.ord - 55
      when " " then 0x24
      when "!" then 0x2B
      else raise ArgumentError, "can't encode #{ch.inspect} (letters, digits, spaces only)"
      end
    end
  end

  def self.decode_text(bytes)
    bytes.map do |b|
      case b
      when 0x00..0x09 then (b + 48).chr
      when 0x0A..0x23 then (b + 55).chr
      when 0x2B then "!"
      else " "
      end
    end.join
  end

  # ------------------------------------------------------------- tiles
  def self.decode_tile(bytes)
    (0...8).map do |y|
      lo = bytes[y]
      hi = bytes[y + 8]
      (0...8).map { |x| b = 7 - x; ((lo >> b) & 1) | (((hi >> b) & 1) << 1) }
    end
  end

  def self.encode_tile(pixels)
    lo = pixels.map { |row| row.each_with_index.sum { |v, x| (v & 1) << (7 - x) } }
    hi = pixels.map { |row| row.each_with_index.sum { |v, x| ((v >> 1) & 1) << (7 - x) } }
    lo + hi
  end

  # ------------------------------------------------------------- ROM
  class Rom
    attr_reader :bytes

    def initialize(path)
      @path = path
      @bytes = File.binread(path).bytes
      validate!
    end

    def validate!
      fail!("not an iNES file") unless @bytes[0, 4] == [0x4E, 0x45, 0x53, 0x1A]
      fail!("expected 32KB PRG / 8KB CHR (NROM)") unless @bytes[4] == 2 && @bytes[5] == 1
      fail!("file is #{@bytes.size} bytes, expected 40976") unless @bytes.size == 40_976
      fail!("player graphics offsets not where expected") unless @bytes[GFX_OFFSETS, 8] == [0x20, 0x28, 0xC8, 0x18, 0x00, 0x40, 0x50, 0x58]
      fail!("player palette table not where expected") unless [0, 4, 8].all? { |i| @bytes[PLAYER_COLORS + i] == 0x22 }
      NAME_SLOTS.each_value do |slots|
        slots.each do |_off, ctx, expect, _len, _kind|
          fail!("name text not where expected (0x#{ctx.to_s(16)})") unless @bytes[ctx, expect.size] == expect
        end
      end
    end

    def fail!(msg)
      abort "#{@path}: #{msg}. This tool targets Super Mario Bros. (World) — the standard US/EU cart dump."
    end

    def tile(n) = SMB.decode_tile(@bytes[CHR_OFFSET + n * 16, 16])

    def set_tile(n, pixels)
      @bytes[CHR_OFFSET + n * 16, 16] = SMB.encode_tile(pixels)
    end

    def gfx_table = @bytes[GFX_TABLE, 0xD0]
    def swim_kick = @bytes[SWIM_KICK, 2]

    PALETTE_KEYS = { "player1" => 1, "player2" => 5, "fire" => 9 }.freeze

    def palettes
      PALETTE_KEYS.transform_values { |o| @bytes[PLAYER_COLORS + o, 3].map { |b| format("%02X", b) } }
    end

    def set_palette(key, colors)
      off = PALETTE_KEYS.fetch(key) { abort "unknown palette #{key.inspect} (use player1, player2, fire)" }
      vals = colors.map { |c| Integer(c.to_s, 16) }
      abort "palette #{key} needs exactly 3 colors" unless vals.size == 3
      vals.each do |v|
        abort "palette #{key}: #{format('%02X', v)} is out of range (00-3F)" unless v.between?(0, 0x3F)
        warn "warning: #{key} uses $0D, which can glitch some TVs — use $0F for black" if v == 0x0D
      end
      @bytes[PLAYER_COLORS + off, 3] = vals
    end

    def names
      { "player1" => SMB.decode_text(@bytes[0x0765, 5]).rstrip,
        "player2" => SMB.decode_text(@bytes[0x07FD, 5]).rstrip }
    end

    def set_name(key, name)
      name = name.to_s.upcase.strip
      abort "name #{name.inspect} is longer than 5 characters" if name.size > 5
      abort "name can't be empty" if name.empty?
      NAME_SLOTS.fetch(key.to_sym).each do |off, _ctx, _expect, len, kind|
        text = kind == :thanks ? "#{name}!" : name
        @bytes[off, len] = SMB.encode_text(text.ljust(len))
      end
    end

    # Palette bytes described by offset (from a game profile), validated.
    def set_bytes(offset, colors, label)
      vals = colors.map { |c| Integer(c.to_s, 16) }
      abort "#{label}: offset 0x#{offset.to_s(16)} is outside PRG" unless offset.between?(0x10, CHR_OFFSET - vals.size)
      abort "#{label}: colors must be 00-3F" unless vals.all? { |v| v.between?(0, 0x3F) }
      @bytes[offset, vals.size] = vals
    end

    # One byte of game code/data by file offset (sound effect parameters and tables).
    # nonzero: the game's code branches on this value, so 0 would crash it.
    def patch_byte(offset, value, label, nonzero: false)
      v = Integer(value.to_s, 16)
      abort "#{label}: offset 0x#{offset.to_s(16)} is outside PRG" unless offset.between?(0x10, CHR_OFFSET - 1)
      abort "#{label}: value must be 00-FF" unless v.between?(0, 0xFF)
      abort "#{label}: can't be 00 — the game's code relies on it being nonzero" if nonzero && v.zero?
      @bytes[offset] = v
    end

    # A block of bytes (e.g. the repacked music region), given as hex.
    def patch_range(offset, hex, label)
      abort "#{label}: hex must be pairs of 0-9A-F" unless hex =~ /\A(?:[0-9a-fA-F]{2})+\z/
      bytes = [hex].pack("H*").bytes
      abort "#{label}: 0x#{offset.to_s(16)}+#{bytes.size} runs outside PRG" unless offset >= 0x10 && offset + bytes.size <= CHR_OFFSET
      @bytes[offset, bytes.size] = bytes
    end

    def write(path) = File.binwrite(path, @bytes.pack("C*"))
  end

  # ------------------------------------------------------------- frames
  # Each frame: name, 8 slots of {tile:, flip:} (col = i % 2, row = i / 2), and
  # its pixel origin in frames.png.
  def self.frames(rom)
    table = rom.gfx_table
    kick = rom.swim_kick
    out = []
    ROWS.each_with_index do |row, r|
      row.each_with_index do |(name, off, flip_rows, kick_idx), c|
        tiles = table[off, 8].dup
        tiles[6] = kick[kick_idx] if kick_idx
        slots = tiles.each_with_index.map do |t, i|
          { tile: t, flip: (flip_rows || []).include?(i / 2) && i.odd? }
        end
        out << { name: name, slots: slots,
                 x: GUTTER + c * (CELL_W + GUTTER), y: GUTTER + r * (CELL_H + GUTTER) }
      end
    end
    out
  end

  def self.sheet_size
    w = GUTTER + ROWS.map(&:size).max * (CELL_W + GUTTER)
    h = GUTTER + ROWS.size * (CELL_H + GUTTER)
    [w, h]
  end

  # Index grid for frames.png: 0..3 = tile colors, 4 = gutter / not-a-sprite.
  def self.render_frames(rom, tile_source = nil)
    tile_source ||= ->(n) { rom.tile(n) }
    w, h = sheet_size
    grid = Array.new(h) { Array.new(w, 4) }
    frames(rom).each do |f|
      f[:slots].each_with_index do |s, i|
        next if s[:tile] == BLANK_TILE
        px = tile_source.call(s[:tile])
        px = px.map(&:reverse) if s[:flip]
        ox = f[:x] + (i % 2) * 8
        oy = f[:y] + (i / 2) * 8
        8.times { |y| 8.times { |x| grid[oy + y][ox + x] = px[y][x] } }
      end
    end
    grid
  end

  # ------------------------------------------------------------- PNG
  module PNG
    module_function

    def chunk(type, data)
      [data.bytesize].pack("N") + type + data + [Zlib.crc32(type + data)].pack("N")
    end

    def write_indexed(path, grid, palette_rgb)
      h = grid.size
      w = grid[0].size
      raw = grid.map { |row| "\x00".b + row.pack("C*") }.join
      png = "\x89PNG\r\n\x1a\n".b
      png << chunk("IHDR", [w, h, 8, 3, 0, 0, 0].pack("NNCCCCC"))
      png << chunk("PLTE", palette_rgb.flatten.pack("C*"))
      png << chunk("IDAT", Zlib::Deflate.deflate(raw, 9))
      png << chunk("IEND", "")
      File.binwrite(path, png)
    end

    def write_rgb(path, rows) # rows: [[ [r,g,b], ... ], ...]
      h = rows.size
      w = rows[0].size
      raw = rows.map { |row| "\x00".b + row.flatten.pack("C*") }.join
      png = "\x89PNG\r\n\x1a\n".b
      png << chunk("IHDR", [w, h, 8, 2, 0, 0, 0].pack("NNCCCCC"))
      png << chunk("IDAT", Zlib::Deflate.deflate(raw, 9))
      png << chunk("IEND", "")
      File.binwrite(path, png)
    end

    # Reads any non-interlaced PNG into rows of [r, g, b, a].
    def read(path)
      data = File.binread(path)
      raise "#{path}: not a PNG" unless data.start_with?("\x89PNG\r\n\x1a\n".b)

      pos = 8
      idat = +"".b
      plte = nil
      trns = nil
      w = h = depth = ctype = nil
      while pos < data.bytesize
        len = data[pos, 4].unpack1("N")
        type = data[pos + 4, 4]
        body = data[pos + 8, len]
        case type
        when "IHDR"
          w, h, depth, ctype, _c, _f, interlace = body.unpack("NNCCCCC")
          raise "#{path}: interlaced PNGs aren't supported — re-save without interlacing" if interlace == 1
        when "PLTE" then plte = body.bytes.each_slice(3).to_a
        when "tRNS" then trns = body.bytes
        when "IDAT" then idat << body
        when "IEND" then break
        end
        pos += 12 + len
      end

      channels = { 0 => 1, 2 => 3, 3 => 1, 4 => 2, 6 => 4 }.fetch(ctype) { raise "unsupported PNG color type #{ctype}" }
      bits_pp = channels * depth
      stride = (w * bits_pp + 7) / 8
      bpp = [(bits_pp + 7) / 8, 1].max
      raw = Zlib::Inflate.inflate(idat).bytes
      prev = Array.new(stride, 0)
      rows = []
      h.times do |y|
        ftype = raw[y * (stride + 1)]
        line = raw[y * (stride + 1) + 1, stride]
        cur = Array.new(stride, 0)
        stride.times do |i|
          a = i >= bpp ? cur[i - bpp] : 0
          b = prev[i]
          c = i >= bpp ? prev[i - bpp] : 0
          x = line[i]
          cur[i] = case ftype
                   when 0 then x
                   when 1 then x + a
                   when 2 then x + b
                   when 3 then x + ((a + b) >> 1)
                   when 4
                     p = a + b - c
                     pa = (p - a).abs
                     pb = (p - b).abs
                     pc = (p - c).abs
                     x + (pa <= pb && pa <= pc ? a : (pb <= pc ? b : c))
                   else raise "bad PNG filter #{ftype}"
                   end & 0xFF
        end
        rows << decode_row(cur, w, depth, ctype, plte, trns)
        prev = cur
      end
      rows
    end

    def decode_row(bytes, w, depth, ctype, plte, trns)
      samples = if depth < 8
                  per = 8 / depth
                  mask = (1 << depth) - 1
                  (0...(w * (ctype == 3 || ctype == 0 ? 1 : 0))).map do |i|
                    (bytes[i / per] >> (8 - depth * (i % per + 1))) & mask
                  end
                elsif depth == 16
                  bytes.each_slice(2).map(&:first)
                else
                  bytes
                end
      scale = ->(v) { depth < 8 && ctype == 0 ? v * 255 / ((1 << depth) - 1) : v }
      case ctype
      when 3
        samples.first(w).map do |i|
          r, g, b = plte.fetch(i)
          [r, g, b, trns && i < trns.size ? trns[i] : 255]
        end
      when 0 then samples.first(w).map { |v| v = scale.(v); [v, v, v, 255] }
      when 4 then samples.each_slice(2).first(w).map { |v, a| [v, v, v, a] }
      when 2 then samples.each_slice(3).first(w).map { |r, g, b| [r, g, b, 255] }
      when 6 then samples.each_slice(4).first(w).to_a
      end
    end
  end

  # ------------------------------------------------------------- tiny font (hex labels)
  FONT = {
    "0" => %w[111 101 101 101 111], "1" => %w[010 110 010 010 111], "2" => %w[111 001 111 100 111],
    "3" => %w[111 001 111 001 111], "4" => %w[101 101 111 001 001], "5" => %w[111 100 111 001 111],
    "6" => %w[111 100 111 101 111], "7" => %w[111 001 001 010 010], "8" => %w[111 101 111 101 111],
    "9" => %w[111 101 111 001 111], "A" => %w[010 101 111 101 101], "B" => %w[110 101 110 101 110],
    "C" => %w[011 100 100 100 011], "D" => %w[110 101 101 101 110], "E" => %w[111 100 111 100 111],
    "F" => %w[111 100 111 100 100]
  }.freeze

  def self.write_color_chart(path)
    sw = 40
    shh = 28
    rows = Array.new(4 * shh) { Array.new(16 * sw) { [0, 0, 0] } }
    64.times do |i|
      cx = (i % 16) * sw
      cy = (i / 16) * shh
      rgb = NES_RGB[i]
      lum = rgb[0] * 0.3 + rgb[1] * 0.59 + rgb[2] * 0.11
      ink = lum > 128 ? [0, 0, 0] : [255, 255, 255]
      (1...shh - 1).each { |y| (1...sw - 1).each { |x| rows[cy + y][cx + x] = rgb } }
      format("%02X", i).chars.each_with_index do |ch, k|
        FONT[ch].each_with_index do |bits, fy|
          bits.chars.each_with_index do |bit, fx|
            next unless bit == "1"
            2.times { |dy| 2.times { |dx| rows[cy + 5 + fy * 2 + dy][cx + 5 + (k * 4 + fx) * 2 + dx] = ink } }
          end
        end
      end
    end
    PNG.write_rgb(path, rows)
  end

  # ------------------------------------------------------------- commands
  def self.rgb_for(hex) = NES_RGB[Integer(hex.to_s, 16)]

  def self.edit_colors(palette3)
    colors = [rgb_for("22")] + palette3.map { |c| rgb_for(c) }
    if colors.uniq.size < 4
      warn "warning: palette has duplicate on-screen colors; using Mario's colors for the editing sheet"
      colors = [rgb_for("22")] + %w[16 27 18].map { |c| rgb_for(c) }
    end
    colors
  end

  def self.import_frames(rom, png_path, key_path)
    key = JSON.parse(File.read(key_path))
    colors = key.fetch("colors").map { |h| [h[1, 2], h[3, 2], h[5, 2]].map { |c| c.to_i(16) } }
    palette = colors + [GUTTER_RGB]
    img = PNG.read(png_path)
    w, h = sheet_size
    abort "#{png_path} is #{img[0].size}x#{img.size}, expected #{w}x#{h} — don't resize or crop it" unless img.size == h && img[0].size == w

    to_index = lambda do |(r, g, b, a)|
      next 0 if a < 128
      best = palette.each_with_index.min_by { |(pr, pg, pb), _| (pr - r)**2 + (pg - g)**2 + (pb - b)**2 }[1]
      best == 4 ? 0 : best
    end

    candidates = Hash.new { |hh, k| hh[k] = [] }
    frames(rom).each do |f|
      f[:slots].each_with_index do |s, i|
        ox = f[:x] + (i % 2) * 8
        oy = f[:y] + (i / 2) * 8
        px = (0...8).map { |y| (0...8).map { |x| to_index.(img[oy + y][ox + x]) } }
        if s[:tile] == BLANK_TILE
          if px.flatten.any?(&:positive?)
            warn "note: drawing in the empty space above '#{f[:name]}' is ignored (the game has no tiles there)"
          end
          next
        end
        px = px.map(&:reverse) if s[:flip]
        candidates[s[:tile]] << [px, f[:name], s[:flip]]
      end
    end

    conflicts = []
    changed = 0
    candidates.each do |tile, cands|
      orig = rom.tile(tile)
      edits = cands.reject { |px, _, _| px == orig }
      next if edits.empty?

      if edits.map(&:first).uniq.size > 1
        where = edits.map { |_, name, flip| flip ? "#{name} (mirrored half)" : name }.uniq
        conflicts << format("tile $%02X was edited differently in: %s", tile, where.join(", "))
        next
      end
      rom.set_tile(tile, edits.first.first)
      changed += 1
    end

    unless conflicts.empty?
      abort "Shared tiles disagree — the game draws these from ONE tile, so every copy must match:\n  " \
            "#{conflicts.join("\n  ")}\nPick one version, copy it to the others (or revert them), and rebuild."
    end
    changed
  end

  # Game-agnostic sheet import. objects.json describes every cell: where it
  # sits in objects.png, its colors, and for each 8x8 slot the CHR file offset
  # and flips the game draws it with (null = not part of the sheet).
  def self.import_objects(rom, png_path, key_path)
    key = JSON.parse(File.read(key_path))
    img = PNG.read(png_path)
    w, h = key.fetch("size")
    abort "#{png_path} is #{img[0].size}x#{img.size}, expected #{w}x#{h} — don't resize or crop it" unless img.size == h && img[0].size == w

    candidates = Hash.new { |hh, k| hh[k] = [] }
    key.fetch("frames").each do |f|
      palette = f.fetch("colors").map { |hx| [hx[1, 2], hx[3, 2], hx[5, 2]].map { |c| c.to_i(16) } } + [GUTTER_RGB]
      cols = f.fetch("cols")
      f.fetch("slots").each_with_index do |slot, i|
        next unless slot
        off, flip = slot
        unless off.between?(CHR_OFFSET, CHR_OFFSET + 0x2000 - 16) && ((off - CHR_OFFSET) % 16).zero?
          abort "objects.json: #{f['object']} / #{f['frame']} points at 0x#{off.to_s(16)}, which isn't a CHR tile"
        end
        ox = f.fetch("x") + (i % cols) * 8
        oy = f.fetch("y") + (i / cols) * 8
        px = (0...8).map do |y|
          (0...8).map do |x|
            r, g, b, a = img[oy + y][ox + x]
            next 0 if a < 128
            best = palette.each_with_index.min_by { |(pr, pg, pb), _| (pr - r)**2 + (pg - g)**2 + (pb - b)**2 }[1]
            best == 4 ? 0 : best
          end
        end
        px = px.map(&:reverse) if flip.to_s.include?("h")
        px = px.reverse if flip.to_s.include?("v")
        candidates[off] << [px, "#{f['object']} / #{f['frame']}"]
      end
    end

    conflicts = []
    changed = 0
    candidates.each do |off, cands|
      orig = decode_tile(rom.bytes[off, 16])
      edits = cands.reject { |px, _| px == orig }
      next if edits.empty?
      if edits.map(&:first).uniq.size > 1
        conflicts << format("tile at 0x%04X was drawn differently in: %s", off, edits.map(&:last).uniq.join(", "))
        next
      end
      rom.bytes[off, 16] = encode_tile(edits.first.first)
      changed += 1
    end
    abort "Shared tiles disagree in objects.png:\n  #{conflicts.join("\n  ")}" unless conflicts.empty?
    changed
  end

  def self.preview(rom, path)
    base = render_frames(rom)
    sky = rgb_for("22")
    scale = 3
    bands = rom.palettes.values.map do |pal|
      cols = [sky] + pal.map { |c| rgb_for(c) } + [sky]
      base.flat_map do |row|
        line = row.flat_map { |i| [cols[i]] * scale }
        [line] * scale
      end
    end
    PNG.write_rgb(path, bands.flatten(1))
  end

  def self.frame_key(rom, colors)
    { "colors" => colors.map { |c| format("#%02X%02X%02X", *c) },
      "note" => "index 0 = transparent (sky), 1-3 = sprite colors; dark gray = not part of the sprite",
      "frames" => frames(rom).map { |f| { "name" => f[:name], "x" => f[:x], "y" => f[:y], "w" => CELL_W, "h" => CELL_H } } }
  end

  # Writes frames.png + its .json key. tile_source overrides ROM tiles.
  def self.write_frames_sheet(png_path, rom, colors, tile_source = nil)
    PNG.write_indexed(png_path, render_frames(rom, tile_source), colors + [GUTTER_RGB])
    File.write(png_path.sub(/\.png\z/i, ".json"), JSON.pretty_generate(frame_key(rom, colors)) + "\n")
  end

  def self.load_config(config_path)
    dir = File.dirname(config_path)
    cfg = JSON.parse(File.read(config_path))
    [cfg, dir, Rom.new(File.expand_path(cfg.fetch("input"), dir))]
  end

  def self.sheet_colors(cfg, rom, view = "player1")
    edit_colors(cfg.dig("palettes", view) || rom.palettes.fetch(view))
  end

  def self.dump(rom_path, dir, view_palette)
    rom = Rom.new(rom_path)
    FileUtils.mkdir_p(dir)
    config_path = File.join(dir, "config.json")

    config = if File.exist?(config_path)
               puts "config.json exists — leaving it alone"
               JSON.parse(File.read(config_path))
             else
               rel_in = Pathname.new(File.expand_path(rom_path)).relative_path_from(Pathname.new(File.expand_path(dir))).to_s
               c = { "input" => rel_in, "output" => "smb_hacked.nes", "ips" => "smb_hacked.ips",
                     "rig" => "rig.yml", "frames" => "frames.png",
                     "palettes" => rom.palettes, "names" => rom.names }
               File.write(config_path, JSON.pretty_generate(c) + "\n")
               puts "wrote config.json"
               c
             end

    colors = sheet_colors(config, rom, view_palette)
    write_frames_sheet(File.join(dir, "frames.png"), rom, colors)

    sheet = Array.new(128) { Array.new(128, 0) }
    256.times do |n|
      t = rom.tile(n)
      8.times { |y| 8.times { |x| sheet[(n / 16) * 8 + y][(n % 16) * 8 + x] = t[y][x] } }
    end
    PNG.write_indexed(File.join(dir, "sprites.png"), sheet, colors)
    write_color_chart(File.join(dir, "nes_colors.png"))
    puts "wrote frames.png, frames.json, sprites.png (reference), nes_colors.png"

    rig_path = File.join(dir, config["rig"] || "rig.yml")
    unless File.exist?(rig_path)
      File.write(rig_path, Rig::DEFAULT_RIG)
      puts "wrote #{File.basename(rig_path)}"
    end
    if File.exist?(File.join(dir, "parts.png"))
      puts "parts.png exists — leaving it alone (run `parts` to re-lay-out)"
    else
      Rig.write_parts(Rig.load(rig_path), dir, sheet_colors(config, rom))
      puts "wrote parts.png (paint these!) and parts.json"
    end
  end

  def self.parts(config_path)
    cfg, dir, rom = load_config(config_path)
    rig = Rig.load(File.expand_path(cfg.fetch("rig") { abort "config has no \"rig\"" }, dir))
    res = Rig.write_parts(rig, dir, sheet_colors(cfg, rom))
    puts "wrote parts.png — kept art: #{res[:kept].join(', ').then { |s| s.empty? ? 'none' : s }}"
    puts "  new (mannequin): #{res[:fresh].join(', ')}" if res[:fresh].any?
    puts "  dropped (no longer in rig.yml): #{res[:dropped].join(', ')}" if res[:dropped].any?
  end

  # parts.png + rig.yml -> frames.png (+ posed_raw.png showing poses before
  # shared-tile settling). Returns the settled tile map.
  def self.pose(cfg, dir, rom)
    rig = Rig.load(File.expand_path(cfg.fetch("rig"), dir))
    parts_px = Rig.read_parts(File.join(dir, "parts.png"), File.join(dir, "parts.json"))
    missing = rig[:parts].keys - parts_px.keys
    abort "parts.png has no #{missing.join(', ')} — run `parts` after changing rig.yml parts" if missing.any?

    tiles, renders, report = Rig.pose(rig, parts_px, rom)
    colors = sheet_colors(cfg, rom)
    frames_png = File.expand_path(cfg.fetch("frames", "frames.png"), dir)
    write_frames_sheet(frames_png, rom, colors, ->(n) { tiles[n] || rom.tile(n) })

    w, h = sheet_size
    raw = Array.new(h) { Array.new(w, 4) }
    frames(rom).each do |f|
      g = renders[f[:name]] or next
      CELL_H.times { |y| CELL_W.times { |x| raw[f[:y] + y][f[:x] + x] = g[y][x] } }
    end
    PNG.write_indexed(File.join(dir, "posed_raw.png"), raw, colors + [GUTTER_RGB])

    puts "posed #{renders.size} frame(s) -> #{File.basename(frames_png)} (posed_raw.png = before shared-tile settling)"
    puts report.empty? ? "  every pose fit its tiles exactly" : report
    tiles
  end

  def self.ips(orig, mod)
    out = +"PATCH".b
    i = 0
    while i < mod.size
      if orig[i] == mod[i]
        i += 1
        next
      end
      j = i
      j += 1 while j < mod.size && orig[j] != mod[j] && j - i < 0xFFFF
      out << [i].pack("N")[1, 3] << [j - i].pack("n") << mod[i...j].pack("C*")
      i = j
    end
    out << "EOF"
  end

  def self.build(config_path, pose_only: false)
    cfg, dir, rom = load_config(config_path)
    original = rom.bytes.dup

    pose(cfg, dir, rom) if cfg["rig"]
    return if pose_only

    if (fr = cfg["frames"])
      png = File.expand_path(fr, dir)
      n = import_frames(rom, png, png.sub(/\.png\z/i, ".json"))
      puts "frames: #{n} tile(s) changed"
    end
    (cfg["palettes"] || {}).each { |k, v| rom.set_palette(k, v) }
    (cfg["names"] || {}).each { |k, v| rom.set_name(k, v) }
    if (ob = cfg["objects"])
      png = File.expand_path(ob, dir)
      n = import_objects(rom, png, png.sub(/\.png\z/i, ".json"))
      puts "objects: #{n} tile(s) changed"
    end
    (cfg["sprite_palettes"] || {}).each { |id, p| rom.set_bytes(p.fetch("offset"), p.fetch("colors"), id) }
    patches = cfg["byte_patches"] || []
    patches.each { |p| rom.patch_byte(p.fetch("offset"), p.fetch("value"), p["label"] || "byte", nonzero: p["nonzero"]) }
    puts "byte patches: #{patches.size}" unless patches.empty?
    (cfg["byte_ranges"] || []).each do |r|
      rom.patch_range(r.fetch("offset"), r.fetch("hex"), r["label"] || "range")
      puts "#{r['label'] || 'range'}: #{r.fetch('hex').size / 2} bytes"
    end

    out = File.expand_path(cfg.fetch("output"), dir)
    rom.write(out)
    puts "wrote #{out}"
    if (c = cfg["chr"])
      File.binwrite(File.expand_path(c, dir), rom.bytes[CHR_OFFSET, 0x2000].pack("C*"))
      puts "wrote #{c} (raw 8KB CHR)"
    end
    if (p = cfg["ips"])
      File.binwrite(File.expand_path(p, dir), ips(original, rom.bytes))
      puts "wrote #{p} (shareable patch — contains no Nintendo data you didn't change)"
    end
    prev = out.sub(/\.nes\z/i, "") + ".preview.png"
    preview(rom, prev)
    puts "wrote #{prev} (rows: player1, player2, fire)"
  end
end

if $PROGRAM_NAME == __FILE__
  args = ARGV.dup
  view = "player1"
  if (i = args.index("--palette"))
    view = args[i + 1] or abort "--palette needs a value"
    args.slice!(i, 2)
  end
  case args.shift
  when "dump"
    rom = args.shift or abort "usage: dump ROM [workdir] [--palette player1|player2|fire]"
    SMB.dump(rom, args.shift || "smb_work", view)
  when "parts" then SMB.parts(args.shift || "smb_work/config.json")
  when "pose"  then SMB.build(args.shift || "smb_work/config.json", pose_only: true)
  when "build" then SMB.build(args.shift || "smb_work/config.json")
  when "colors"
    path = args.shift || "nes_colors.png"
    SMB.write_color_chart(path)
    puts "wrote #{path}"
  else
    puts File.read(__FILE__).lines[2..22].map { |l| l.sub(/^# ?/, "") }.join
  end
end
