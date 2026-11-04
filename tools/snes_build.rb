#!/usr/bin/env ruby
# frozen_string_literal: true

# ROM Studio (SNES): rebuild a hack from a downloaded project, byte for byte what the browser builds.
#
#   ruby tools/snes_build.rb build path/to/config.json   # reads profile.json + the original ROM next to it
#   ruby tools/snes_build.rb dump  rom.sfc profile.json   # decoded graphics files -> ./gfx/*.bin (for your own tools)
#
# Stdlib only. Mirrors snes/lib/{lz2,tiles,color,rom}.js and lib/mechanics.js.
require "json"

module SnesStudio
  module LZ2
    module_function

    def decode(r, off, little = false)
      out = []
      i = off
      loop do
        b = r.getbyte(i) or raise "LZ2 data runs past the end of the ROM"
        i += 1
        return [out.pack("C*"), i - off] if b == 0xFF

        if b & 0xE0 == 0xE0
          cmd = (b << 3) & 0xE0
          n = (((b & 3) << 8) | r.getbyte(i)) + 1
          i += 1
        else
          cmd = b & 0xE0
          n = (b & 0x1F) + 1
        end
        case cmd
        when 0 then n.times { |k| out << r.getbyte(i + k) }; i += n
        when 0x20 then v = r.getbyte(i); i += 1; n.times { out << v }
        when 0x40 then a = r.getbyte(i); c = r.getbyte(i + 1); i += 2; n.times { |k| out << (k.odd? ? c : a) }
        when 0x60 then v = r.getbyte(i); i += 1; n.times { |k| out << ((v + k) & 255) }
        else
          src = little ? r.getbyte(i) | (r.getbyte(i + 1) << 8) : (r.getbyte(i) << 8) | r.getbyte(i + 1)
          i += 2
          n.times { |k| out << out[src + k] }
        end
      end
    end

    def encode(str, little = false)
      d = str.bytes
      n = d.length
      out = []
      lit = []
      chains = {}
      hdr = lambda do |cmd, len|
        len -= 1
        len < 32 ? out << (cmd | len) : out.push(0xE0 | (cmd >> 3) | (len >> 8), len & 255)
      end
      flush = lambda do
        until lit.empty?
          k = [lit.length, 1024].min
          hdr.call(0, k)
          out.concat(lit.shift(k))
        end
      end
      key = ->(p) { (d[p] << 16) | (d[p + 1] << 8) | d[p + 2] }
      index = ->(p) { (chains[key.call(p)] ||= []) << p if p + 2 < n }
      i = 0
      while i < n
        m = [1024, n - i].min
        cands = []
        k = 1
        k += 1 while k < m && d[i + k] == d[i]
        cands << [k, 0x20, [d[i]]]
        if m >= 2
          k = 2
          k += 1 while k < m && d[i + k] == d[i + (k & 1)]
          cands << [k, 0x40, [d[i], d[i + 1]]]
        end
        k = 1
        k += 1 while k < m && d[i + k] == ((d[i] + k) & 255)
        cands << [k, 0x60, [d[i]]]
        bl = 0
        bs = 0
        if i + 2 < n
          (chains[key.call(i)] || []).each do |s|
            break if s > 0xFFFF

            k = 0
            k += 1 while k < m && d[s + k] == d[i + k]
            if k > bl
              bl = k
              bs = s
            end
            break if k == m
          end
        end
        cands.unshift([bl, 0x80, little ? [bs & 255, bs >> 8] : [bs >> 8, bs & 255]]) if bl.positive?
        best = nil
        bsav = 0
        cands.each do |c|
          sav = c[0] - (c[0] <= 32 ? 1 : 2) - c[2].length
          if sav > bsav
            bsav = sav
            best = c
          end
        end
        unless best
          lit << d[i]
          index.call(i)
          i += 1
          next
        end
        flush.call
        hdr.call(best[1], best[0])
        out.concat(best[2])
        (i...(i + best[0])).each { |p| index.call(p) }
        i += best[0]
      end
      flush.call
      out << 0xFF
      out.pack("C*")
    end
  end

  # Capcom LZ (Mega Man 7, Rockman & Forte, Mega Man X2/X3): see snes/lib/clz.js
  module CLZ
    module_function

    def decode(r, off, size)
      out = []
      i = off
      ctl = r.getbyte(i)
      i += 1
      n = 8
      while out.length < size
        if ctl & 0x80 == 0
          out << r.getbyte(i)
          i += 1
        else
          b = r.getbyte(i)
          d = ((b & 3) << 8) | r.getbyte(i + 1)
          i += 2
          (b >> 2).times { out << out[-d] if out.length < size }
        end
        break if out.length >= size

        ctl = (ctl << 1) & 255
        n -= 1
        if n.zero?
          ctl = r.getbyte(i)
          i += 1
          n = 8
        end
      end
      [out.pack("C*"), i - off]
    end

    def matches(d)
      n = d.length
      len = Array.new(n, 0)
      dist = Array.new(n, 0)
      chains = {}
      n.times do |i|
        bl = 0
        bd = 0
        m = [63, n - i].min
        if i + 2 < n
          key = (d[i] << 16) | (d[i + 1] << 8) | d[i + 2]
          c = (chains[key] ||= [])
          j = c.length - 1
          while j >= 0
            s = c[j]
            break if i - s > 1023

            k = 0
            k += 1 while k < m && d[s + k] == d[i + k]
            if k > bl
              bl = k
              bd = i - s
            end
            break if k == m

            j -= 1
          end
          c << i
        end
        len[i] = bl
        dist[i] = bd
      end
      [len, dist]
    end

    def encode(str)
      d = str.bytes
      n = d.length
      len, dist = matches(d)
      cost = Array.new(n + 1, 0)
      pick = Array.new(n, 0)
      (n - 1).downto(0) do |i|
        best = 9 + cost[i + 1]
        choice = 0
        l = len[i]
        while l >= 3
          c = 17 + cost[i + l]
          if c < best
            best = c
            choice = l
          end
          l -= 1
        end
        cost[i] = best
        pick[i] = choice
      end
      out = []
      i = 0
      ctl_at = -1
      bits = 8
      while i < n
        if bits == 8
          ctl_at = out.length
          out << 0
          bits = 0
        end
        l = pick[i]
        if l.positive?
          out[ctl_at] |= 0x80 >> bits
          out.push((l << 2) | (dist[i] >> 8), dist[i] & 255)
          i += l
        else
          out << d[i]
          i += 1
        end
        bits += 1
      end
      out.pack("C*")
    end
  end

  module Tiles
    BYTES = { 2 => 16, 3 => 24, 4 => 32, 8 => 64 }.freeze
    module_function

    def at(bpp, y, p)
      return(p < 2 ? 2 * y + p : 16 + y) if bpp == 3

      16 * (p >> 1) + 2 * y + (p & 1)
    end

    def planes(bpp) = bpp == 3 ? 3 : bpp

    def encode_tile(hex, buf, off, bpp)
      BYTES[bpp].times { |i| buf.setbyte(off + i, 0) }
      8.times do |y|
        8.times do |x|
          v = hex[y * 8 + x].to_i(16)
          planes(bpp).times do |p|
            o = off + at(bpp, y, p)
            buf.setbyte(o, buf.getbyte(o) | (0x80 >> x)) if (v >> p) & 1 == 1
          end
        end
      end
    end
  end

  module Mechanics
    module_function

    def value(k, rom, settings)
      v = settings[k["id"]]
      return !!v if k["kind"] == "toggle"
      return v.nil? ? k["default"] : v if k["kind"] == "percent" || k["offset"].nil? || !v.nil? || k["install"]

      rom.getbyte(k["offset"]) - (k["bias"] || 0)
    end

    def patches(knobs, rom, settings)
      out = {}
      return out unless knobs

      clamp = ->(v, lo, hi) { [[v, lo].max, hi].min }
      cur = ->(o) { out.key?(o) ? out[o] : rom.getbyte(o) }
      put = ->(pts) { (pts || []).each { |pt| [pt["hex"]].pack("H*").bytes.each_with_index { |b, i| out[pt["offset"] + i] = b } } }
      away = ->(k) { k["kind"] == "toggle" ? !!settings[k["id"]] : !settings[k["id"]].nil? && settings[k["id"]] != k["default"] }
      knobs.each { |k| put.call(k["install"]) if k["install"] && away.call(k) }
      knobs.each do |k|
        v = settings[k["id"]]
        next if k["kind"] == "choice" && k["offset"].nil?

        if %w[number choice].include?(k["kind"])
          next if v.nil? || (k["install"] && v == k["default"])

          b = ((k["kind"] == "number" ? clamp.call(v, k["min"], k["max"]) : v) + (k["bias"] || 0)) & 255
          [k["offset"], *(k["also"] || [])].each { |o| out[o] = b if k["install"] || b != rom.getbyte(o) }
        elsif k["kind"] == "percent"
          next if v.nil? || v == k["default"]

          f = v / 100.0
          scale = lambda do |x, mode|
            case mode
            when "div" then x / f
            when "sqrt" then x * Math.sqrt(f)
            else x * f
            end
          end
          (k["bytes"] || []).each do |b|
            b["n"].times do |i|
              o = b["offset"] + i
              base = cur.call(o)
              next if (b["skip"] || []).include?(base)

              neg = b["signed"] && base >= 128
              mag = neg ? 256 - base : base
              nv = !k["max_value"].nil? && v == k["max_value"] ? (b["max"] || 255) : clamp.call(js_round(scale.call(mag, b["mode"])), b["min"] || 0, b["max"] || 255)
              out[o] = neg ? (256 - nv) & 255 : nv
            end
          end
          (k["words"] || []).each do |w|
            base = cur.call(w["hi"]) * 256 + cur.call(w["lo"])
            next if base.zero?

            neg = w["signed"] && base >= 0x8000
            base = 0x10000 - base if neg
            nv = clamp.call(js_round(scale.call(base, w["mode"])), w["min"] || 1, w["max"] || 0x7FFF)
            nv = (0x10000 - nv) & 0xFFFF if neg
            out[w["lo"]] = nv & 255
            out[w["hi"]] = nv >> 8
          end
        end
      end
      knobs.each do |k|
        put.call(k["patches"]) if k["kind"] == "toggle" && settings[k["id"]]
        if k["kind"] == "choice" && k["offset"].nil?
          o = k["options"].find { |x| x["value"] == value(k, rom, settings) }
          put.call(o["patches"]) if o
        end
      end
      out
    end

    def js_round(x) = (x + 0.5).floor # Math.round
  end

  class Build
    MAPS = { "lorom" => ->(o) { ((o >> 15) << 16) | 0x8000 | (o & 0x7FFF) }, "hirom" => ->(o) { 0xC00000 | o } }.freeze

    def initialize(profile, rom)
      @p = profile
      @rom = rom.b
      @files = {}
      profile["gfx"]["files"].each { |f| data, size = decode(f); @files[f["id"]] = { data: data, size: size } }
    end

    def codec(f) = f["codec"] || @p["gfx"]["codec"]

    def decode(f)
      case codec(f)
      when "lz2", "lz1" then LZ2.decode(@rom, f["at"], codec(f) == "lz1")
      when "clz" then CLZ.decode(@rom, f["at"], f["unpacked"])
      when "raw" then [@rom[f["at"], f["len"]], f["len"]]
      else raise "unknown codec #{codec(f)}"
      end
    end

    def encode(f, data)
      case codec(f)
      when "lz2", "lz1" then LZ2.encode(data, codec(f) == "lz1")
      when "clz" then CLZ.encode(data)
      else raise "can't pack #{codec(f)}"
      end
    end

    attr_reader :files

    def write_ptr(out, off, kind, a)
      case kind
      when "lo" then out.setbyte(off, a & 255)
      when "hi" then out.setbyte(off, (a >> 8) & 255)
      when "bank" then out.setbyte(off, (a >> 16) & 0x7F)
      when "word" then out[off, 2] = [a & 0xFFFF].pack("v")
      when "long" then out[off, 3] = [a & 255, (a >> 8) & 255, (a >> 16) & 255].pack("C3")
      else raise "unknown pointer kind #{kind}"
      end
    end

    def run(state)
      out = @rom.dup
      enc = {}
      @p["gfx"]["files"].each do |f|
        edits = (state["tiles"] || {})[f["id"]]
        next if edits.nil? || edits.empty?

        src = @files[f["id"]][:data]
        data = src.dup
        n = Tiles::BYTES[f["bpp"]]
        edits.keys.map(&:to_i).sort.each { |t| Tiles.encode_tile(edits[t.to_s], data, t * n, f["bpp"]) }
        next if data == src

        if codec(f) == "raw"
          out[f["at"], data.bytesize] = data
          next
        end
        enc[f["id"]] = encode(f, data)
      end
      packed = @p["gfx"]["files"].reject { |f| codec(f) == "raw" }
      if enc.all? { |id, b| b.bytesize <= @files[id][:size] }
        packed.each { |f| out[f["at"], enc[f["id"]].bytesize] = enc[f["id"]] if enc[f["id"]] }
      else
        at, stop = @p["gfx"]["region"]
        packed.each do |f|
          b = enc[f["id"]] || encode(f, @files[f["id"]][:data])
          if at + b.bytesize > stop || (f["max_end"] && at + b.bytesize > f["max_end"])
            raise "The edited graphics don't fit back in the ROM."
          end

          out[at, b.bytesize] = b
          (f["ptrs"] || []).each { |off, kind| write_ptr(out, off, kind, MAPS[@p["rom"]["map"] || "lorom"].call(at)) }
          at += b.bytesize
        end
      end
      (state["colors"] || {}).each do |off, h|
        w = h.to_i(16)
        out.setbyte(off.to_i, w & 255)
        out.setbyte(off.to_i + 1, (w >> 8) & 0x7F)
      end
      Mechanics.patches(@p["mechanics"], @rom, state["mech"] || {}).each { |o, v| out.setbyte(o.to_i, v) }
      fix_checksum(out, @p["rom"]["checksum"]) if @p["rom"]["checksum"]
      out
    end

    def fix_checksum(out, at)
      out[at, 4] = [0xFF, 0xFF, 0, 0].pack("C4")
      sum = out.sum & 0xFFFF
      out[at, 4] = [~sum & 0xFFFF, sum].pack("vv")
    end
  end
end

if $PROGRAM_NAME == __FILE__
  cmd, *args = ARGV
  case cmd
  when "build"
    cfg_path = args[0] or abort "usage: snes_build.rb build config.json"
    dir = File.dirname(cfg_path)
    cfg = JSON.parse(File.read(cfg_path))
    profile = JSON.parse(File.read(File.join(dir, cfg["profile"] || "profile.json")))
    rom = File.binread(File.join(dir, cfg["original"]))
    rom = rom[512..] if rom.bytesize % 1024 == 512
    out = SnesStudio::Build.new(profile, rom).run(cfg["state"] || {})
    File.binwrite(File.join(dir, cfg["output"]), out)
    puts "wrote #{File.join(dir, cfg['output'])} (#{out.bytes.each_with_index.count { |b, i| b != rom.getbyte(i) }} bytes changed)"
  when "dump"
    rom_path, profile_path = args
    abort "usage: snes_build.rb dump rom.sfc profile.json" unless profile_path
    rom = File.binread(rom_path)
    rom = rom[512..] if rom.bytesize % 1024 == 512
    b = SnesStudio::Build.new(JSON.parse(File.read(profile_path)), rom)
    Dir.mkdir("gfx") unless Dir.exist?("gfx")
    b.files.each { |id, f| File.binwrite("gfx/#{id}.bin", f[:data]) }
    puts "wrote #{b.files.size} files to gfx/"
  else
    abort "usage: snes_build.rb build config.json | dump rom.sfc profile.json"
  end
end
