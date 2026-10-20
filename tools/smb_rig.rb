# frozen_string_literal: true
#
# smb_rig.rb — turns a small sheet of body-part templates (parts.png) plus a
# pose file (rig.yml) into every player frame SMB needs.
#
#   parts.png + rig.yml  --pose-->  frames.png  --build-->  ROM / CHR / IPS
#
# Parts are drawn once. Each pose places parts on bones and rotates limbs
# around their joints, so a walk cycle is just a few angles.

require "yaml"
require "json"

module SMB
  module Rig
    SHEET_MAX_W = 64
    PART_GUTTER = 4
    FRAME_W = 16
    FRAME_H = 32

    DEFAULT_RIG = <<~YAML
      # rig.yml — how the body-part templates in parts.png become game frames.
      #
      # parts:     what gets drawn. size [w, h] in pixels; pivot = the joint the
      #            part rotates around, in the part's own pixels ([0,0] = top-left).
      #            Change a size, then run `parts` to re-lay-out parts.png (art is kept).
      # skeletons: which part each bone uses and where its joint sits in the frame.
      #            Frames are 16x32; small characters live in the bottom half (y 16-31).
      #            Bones are drawn in list order, so later bones are in front.
      # poses:     one per game frame. `bone: 30` is shorthand for `bone: {rot: 30}`.
      #            rot is in degrees; positive swings the limb forward (toward the
      #            direction the character faces). Any bone field can be overridden:
      #            at, part, rot, flip (mirror the part), hide, remap ({3: 1} recolors).
      #            `offset: [dx, dy]` shifts the whole body.
      #
      # The game builds frames from shared 8x8 tiles, so some frames are forced
      # to share pixels. Poses listed FIRST win those tiles; `pose` reports which
      # frames got overridden and by how much.

      parts:
        head:       {size: [8, 8],  pivot: [4, 8]}
        head_front: {size: [8, 8],  pivot: [4, 8]}
        torso:      {size: [4, 12], pivot: [2, 0]}
        arm:        {size: [4, 12], pivot: [2, 0]}
        leg:        {size: [4, 12], pivot: [2, 0]}
        s_torso:    {size: [4, 4],  pivot: [2, 0]}
        s_arm:      {size: [2, 4],  pivot: [1, 0]}
        s_leg:      {size: [4, 4],  pivot: [2, 0]}

      skeletons:
        big:
          back_arm:  {part: arm,   at: [8, 8]}
          back_leg:  {part: leg,   at: [8, 20]}
          torso:     {part: torso, at: [8, 8]}
          front_leg: {part: leg,   at: [8, 20]}
          head:      {part: head,  at: [8, 8]}
          front_arm: {part: arm,   at: [8, 8]}
        grow:   # halfway between small and big
          back_arm:  {part: arm,    at: [8, 16]}
          back_leg:  {part: s_leg,  at: [8, 28]}
          torso:     {part: torso,  at: [8, 16]}
          front_leg: {part: s_leg,  at: [8, 28]}
          head:      {part: head,   at: [8, 16]}
          front_arm: {part: arm,    at: [8, 16]}
        small:
          back_arm:  {part: s_arm,   at: [8, 24]}
          back_leg:  {part: s_leg,   at: [8, 28]}
          torso:     {part: s_torso, at: [8, 24]}
          front_leg: {part: s_leg,   at: [8, 28]}
          head:      {part: head,    at: [8, 24]}
          front_arm: {part: s_arm,   at: [8, 24]}
        small_front:   # facing the camera; the game mirrors the left half
          left_arm:  {part: s_arm,      at: [3, 24]}
          left_leg:  {part: s_leg,      at: [6, 28]}
          right_leg: {part: s_leg,      at: [10, 28]}
          torso:     {part: s_torso,    at: [8, 24]}
          head:      {part: head_front, at: [8, 24]}
          right_arm: {part: s_arm,      at: [13, 24]}

      poses:
        big walk 1:      {skeleton: big, front_arm: -35, back_arm: 35, front_leg: 30, back_leg: -30}
        big walk 2:      {skeleton: big, front_arm: -10, back_arm: 10, front_leg: 10, back_leg: -10}
        big walk 3:      {skeleton: big, front_arm: 35, back_arm: -35, front_leg: -30, back_leg: 30}
        big standing:    {skeleton: big}
        big jump:        {skeleton: big, front_arm: 165, back_arm: -40, front_leg: 40, back_leg: -25}
        big skid:        {skeleton: big, offset: [-1, 0], front_arm: 70, back_arm: 50, front_leg: 35, back_leg: 15}
        # The game reuses tiles here, so these come in families:
        #   fire throw / swim 1 / swim kick / climb 1 share the top 3/4 (head + arms)
        #   walk 2 / swim 2 / swim 3 / climb 2 share the top half or more
        # so they only get to differ below the waist. `like:` copies a pose.
        big fire throw:  {skeleton: big, front_arm: 80, back_arm: -20, front_leg: 10, back_leg: -10}
        big swim 1:      {like: big fire throw, front_leg: -20, back_leg: -45}
        big swim kick:   {like: big fire throw, front_leg: 15, back_leg: -50}
        big climb 1:     {like: big fire throw, front_leg: 35, back_leg: -15}
        big swim 2:      {like: big walk 2, front_leg: -30, back_leg: -30}
        big swim 3:      {like: big walk 2, front_leg: -45, back_leg: -15}
        big climb 2:     {like: big walk 2, front_leg: -15, back_leg: 35}
        big crouch:
          skeleton: big
          head:      {at: [8, 16]}
          torso:     {at: [8, 16]}
          back_arm:  {at: [8, 16]}
          front_arm: {at: [8, 16], rot: 20}
          back_leg:  {at: [8, 24], rot: -70}
          front_leg: {at: [8, 24], rot: 70}
        growing:         {skeleton: grow}

        small walk 1:    {skeleton: small, front_arm: -40, back_arm: 40, front_leg: 40, back_leg: -40}
        small walk 2:    {skeleton: small, front_arm: -15, back_arm: 15, front_leg: 15, back_leg: -15}
        small walk 3:    {skeleton: small, front_arm: 40, back_arm: -40, front_leg: -40, back_leg: 40}
        small standing:  {skeleton: small}
        small jump:      {skeleton: small, front_arm: 165, back_arm: -45, front_leg: 50, back_leg: -30}
        small skid:      {skeleton: small, offset: [-1, 0], front_arm: 80, back_arm: 60, front_leg: 45, back_leg: 20}
        small swim 1:    {skeleton: small, front_arm: 100, back_arm: 60, front_leg: -30, back_leg: -50}
        small swim 2:    {skeleton: small, front_arm: 60, back_arm: 100, front_leg: -40, back_leg: -40}
        small swim 3:    {skeleton: small, front_arm: 20, back_arm: 130, front_leg: -50, back_leg: -30}
        small swim kick: {skeleton: small, front_arm: 100, back_arm: 60, front_leg: 20, back_leg: -60}
        small climb 1:   {skeleton: small, front_arm: 160, back_arm: 140, front_leg: 30, back_leg: -15}
        small climb 2:   {skeleton: small, front_arm: 140, back_arm: 160, front_leg: -15, back_leg: 30}
        small killed:    {skeleton: small_front, left_arm: 180, right_arm: 180}
    YAML

    module_function

    # ------------------------------------------------------------ loading
    def load(path)
      raw = YAML.safe_load(File.read(path), aliases: true) || {}
      parts = raw.fetch("parts") { abort "#{path}: missing `parts:`" }.to_h do |name, p|
        size = p.fetch("size") { abort "part #{name}: missing size" }
        pivot = p.fetch("pivot") { abort "part #{name}: missing pivot" }
        [name.to_s, { size: size.map(&:to_i), pivot: pivot.map(&:to_f) }]
      end
      { path: path, parts: parts,
        skeletons: raw.fetch("skeletons") { abort "#{path}: missing `skeletons:`" },
        poses: raw.fetch("poses") { abort "#{path}: missing `poses:`" } }
    end

    def layout(parts)
      rects = {}
      x = y = PART_GUTTER
      row_h = 0
      right = 0
      parts.each do |name, p|
        w, h = p[:size]
        if x > PART_GUTTER && x + w + PART_GUTTER > SHEET_MAX_W
          x = PART_GUTTER
          y += row_h + PART_GUTTER
          row_h = 0
        end
        rects[name] = [x, y, w, h]
        right = [right, x + w].max
        x += w + PART_GUTTER
        row_h = [row_h, h].max
      end
      [rects, right + PART_GUTTER, y + row_h + PART_GUTTER]
    end

    # ------------------------------------------------------------ parts.png
    def mannequin(name, w, h)
      fill = case name
             when /head/ then 2
             when /leg/ then 1
             else 3
             end
      px = Array.new(h) { |y| Array.new(w) { |x| x.zero? || y.zero? || x == w - 1 || y == h - 1 ? 1 : fill } }
      if name =~ /arm/ && h > 3 # hands
        (h - [h / 4, 1].max...h - 1).each { |y| (1...w - 1).each { |x| px[y][x] = 2 } }
      end
      if name == "head" && w >= 7 && h >= 5
        px[h / 2 - 1][w - 2] = 1
      elsif name =~ /head/ && w >= 6 && h >= 5
        px[h / 2 - 1][2] = 1
        px[h / 2 - 1][w - 3] = 1
      end
      px
    end

    def read_parts(png, key_path)
      key = JSON.parse(File.read(key_path))
      colors = key.fetch("colors").map { |hx| [hx[1, 2], hx[3, 2], hx[5, 2]].map { |c| c.to_i(16) } }
      palette = colors + [GUTTER_RGB]
      img = PNG.read(png)
      w, h = key.fetch("size")
      abort "#{png} is #{img[0].size}x#{img.size}, expected #{w}x#{h} — don't resize it (run `parts` to re-lay-out)" unless img.size == h && img[0].size == w

      key.fetch("parts").to_h do |name, (x, y, pw, ph)|
        px = (0...ph).map do |yy|
          (0...pw).map do |xx|
            r, g, b, a = img[y + yy][x + xx]
            next 0 if a < 128
            i = palette.each_with_index.min_by { |(pr, pg, pb), _| (pr - r)**2 + (pg - g)**2 + (pb - b)**2 }[1]
            i == 4 ? 0 : i
          end
        end
        [name, px]
      end
    end

    # Writes parts.png + parts.json for the rig's part list. Existing art is
    # carried over by part name (cropped if a part shrank), so this is safe to
    # re-run after changing sizes.
    def write_parts(rig, dir, colors)
      png = File.join(dir, "parts.png")
      key_path = File.join(dir, "parts.json")
      old = File.exist?(png) && File.exist?(key_path) ? read_parts(png, key_path) : {}
      rects, w, h = layout(rig[:parts])
      sheet = Array.new(h) { Array.new(w, 4) }
      kept = []
      rects.each do |name, (x, y, pw, ph)|
        art = old[name]
        kept << name if art
        art ||= mannequin(name, pw, ph)
        ph.times { |yy| pw.times { |xx| sheet[y + yy][x + xx] = art.dig(yy, xx) || 0 } }
      end
      PNG.write_indexed(png, sheet, colors + [GUTTER_RGB])
      File.write(key_path, JSON.pretty_generate(
        "colors" => colors.map { |c| format("#%02X%02X%02X", *c) },
        "note" => "index 0 = transparent, 1-3 = sprite colors, dark gray = gutter. Don't edit this file.",
        "size" => [w, h], "parts" => rects
      ) + "\n")
      { kept: kept, fresh: rects.keys - kept, dropped: old.keys - rects.keys }
    end

    # ------------------------------------------------------------ posing
    def blit(canvas, art, pivot, at, rot, flip, remap)
      ph = art.size
      pw = art[0].size
      art = art.map(&:reverse) if flip
      pvx = flip ? pw - pivot[0] : pivot[0]
      pvy = pivot[1]
      th = rot * Math::PI / 180
      c = Math.cos(th)
      s = Math.sin(th)
      FRAME_H.times do |dy|
        FRAME_W.times do |dx|
          vx = dx + 0.5 - at[0]
          vy = dy + 0.5 - at[1]
          sx = (c * vx - s * vy + pvx + 1e-9).floor
          sy = (s * vx + c * vy + pvy + 1e-9).floor
          next unless sx.between?(0, pw - 1) && sy.between?(0, ph - 1)
          v = art[sy][sx]
          next if v.zero?
          canvas[dy][dx] = remap.fetch(v, v)
        end
      end
    end

    # Expands `like: other pose` (recursively) and `bone: 30` shorthand.
    def resolve_pose(name, rig, seen = [])
      abort "pose #{name.inspect}: `like:` loop (#{(seen + [name]).join(' -> ')})" if seen.include?(name)
      raw = rig[:poses].fetch(name) { abort "pose #{seen.last.inspect}: like: #{name.inspect} isn't a pose" } || {}
      base = raw["like"] ? resolve_pose(raw["like"], rig, seen + [name]) : {}
      raw.each_with_object(base.dup) do |(k, v), out|
        next if k == "like"
        if %w[skeleton offset].include?(k)
          out[k] = v
        else
          v = { "rot" => v } if v.is_a?(Numeric)
          out[k] = (out[k] || {}).merge(v || {})
        end
      end
    end

    def render_pose(name, _pose, rig, parts_px)
      pose = resolve_pose(name, rig)
      sk_name = pose.delete("skeleton") or abort "pose #{name.inspect}: missing skeleton"
      skel = rig[:skeletons][sk_name] or abort "pose #{name.inspect}: unknown skeleton #{sk_name.inspect} (have: #{rig[:skeletons].keys.join(', ')})"
      ox, oy = pose.delete("offset") || [0, 0]
      unknown = pose.keys - skel.keys
      abort "pose #{name.inspect}: unknown bone(s) #{unknown.join(', ')} (skeleton #{sk_name} has: #{skel.keys.join(', ')})" if unknown.any?

      canvas = Array.new(FRAME_H) { Array.new(FRAME_W, 0) }
      skel.each do |bone, base|
        b = base.merge(pose[bone] || {})
        next if b["hide"]
        part = b["part"].to_s
        meta = rig[:parts][part] or abort "pose #{name.inspect}, bone #{bone}: unknown part #{part.inspect}"
        at = b.fetch("at") { abort "skeleton #{sk_name}, bone #{bone}: missing at" }
        remap = (b["remap"] || {}).to_h { |k, v| [k.to_i, v.to_i] }
        blit(canvas, parts_px.fetch(part), meta[:pivot], [at[0] + ox, at[1] + oy],
             b.fetch("rot", 0).to_f, b["flip"], remap)
      end
      canvas
    end

    # Renders every pose, then settles shared tiles: the first pose (in file
    # order) to use a tile owns it. Returns [tile => pixels, report lines].
    def pose(rig, parts_px, rom)
      frames = SMB.frames(rom).to_h { |f| [f[:name], f] }
      unknown = rig[:poses].keys - frames.keys
      abort "#{rig[:path]}: unknown pose name(s) #{unknown.map(&:inspect).join(', ')}.\nValid names: #{frames.keys.join(', ')}" if unknown.any?

      renders = rig[:poses].to_h { |name, p| [name, render_pose(name, p || {}, rig, parts_px)] }
      slice = lambda do |grid, i|
        (0...8).map { |y| grid[(i / 2) * 8 + y][(i % 2) * 8, 8] }
      end

      owner = {}
      tiles = {}
      renders.each do |name, grid|
        frames[name][:slots].each_with_index do |s, i|
          next if s[:tile] == BLANK_TILE || tiles.key?(s[:tile])
          px = slice.(grid, i)
          tiles[s[:tile]] = s[:flip] ? px.map(&:reverse) : px
          owner[s[:tile]] = name
        end
      end

      report = []
      renders.each do |name, grid|
        changed = 0
        clipped = 0
        donors = []
        frames[name][:slots].each_with_index do |s, i|
          want = slice.(grid, i)
          if s[:tile] == BLANK_TILE
            clipped += want.flatten.count(&:positive?)
            next
          end
          got = tiles[s[:tile]]
          got = got.map(&:reverse) if s[:flip]
          diff = want.flatten.zip(got.flatten).count { |a, b| a != b }
          next if diff.zero?
          changed += diff
          donors << (owner[s[:tile]] == name ? "its own other half — same tile drawn twice" : owner[s[:tile]])
        end
        parts = []
        parts << "#{changed} px forced by shared tiles (from #{donors.uniq.join(', ')})" if changed.positive?
        parts << "#{clipped} px dropped (no tiles there in this pose)" if clipped.positive?
        report << "  #{name}: #{parts.join('; ')}" if parts.any?
      end
      missing = frames.keys - renders.keys
      report << "  not posed (keeps ROM art unless shared): #{missing.join(', ')}" if missing.any?
      [tiles, renders, report]
    end
  end
end
