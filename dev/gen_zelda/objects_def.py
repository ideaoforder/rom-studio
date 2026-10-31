"""Objects: (name, group, area, source). source is ("anim", object type, [frame names]) for objects drawn from the
shared animation tables (animation index = type + 1), or a custom layout name handled in build_profile.py.
Areas: "ow" = overworld graphics, "L1".."L9" = each level's dungeon graphics (common + special + boss sets)."""
A = lambda t, *names: ("anim", t, list(names))
LINK = ["walk right 1", "walk right 2", "walk down", "walk up", "attack right", "attack right 2", "attack down", "attack up"]
OBJECTS = [
  ("Link", "Link", "ow", ("link", None, LINK)),
  # overworld
  ("Octorok (red)", "Overworld enemies", "ow", A(0x07)), ("Octorok (blue)", "Overworld enemies", "ow", A(0x09)),
  ("Moblin (blue)", "Overworld enemies", "ow", A(0x03)), ("Moblin (red)", "Overworld enemies", "ow", A(0x04)),
  ("Lynel (blue)", "Overworld enemies", "ow", A(0x01)), ("Lynel (red)", "Overworld enemies", "ow", A(0x02)),
  ("Tektite (blue)", "Overworld enemies", "ow", A(0x0D)), ("Tektite (red)", "Overworld enemies", "ow", A(0x0E)),
  ("Leever (blue)", "Overworld enemies", "ow", A(0x0F)), ("Leever (red)", "Overworld enemies", "ow", A(0x10)),
  ("Zora", "Overworld enemies", "ow", A(0x11)), ("Peahat", "Overworld enemies", "ow", A(0x1A)), ("Armos", "Overworld enemies", "ow", A(0x1E)),
  ("Boulder", "Overworld enemies", "ow", A(0x20)), ("Ghini", "Overworld enemies", "ow", A(0x21)), ("Flying Ghini", "Overworld enemies", "ow", A(0x22)),
  # dungeons
  ("Keese", "Dungeon enemies", "L1", A(0x1B)), ("Gel", "Dungeon enemies", "L1", A(0x14)), ("Zol", "Dungeon enemies", "L3", A(0x13)),
  ("Stalfos", "Dungeon enemies", "L1", A(0x2A)), ("Goriya (blue)", "Dungeon enemies", "L1", A(0x05)), ("Goriya (red)", "Dungeon enemies", "L1", A(0x06)),
  ("Wallmaster", "Dungeon enemies", "L1", A(0x27)), ("Rope", "Dungeon enemies", "L2", A(0x28)),
  ("Darknut (red)", "Dungeon enemies", "L3", A(0x0B)), ("Darknut (blue)", "Dungeon enemies", "L3", A(0x0C)),
  ("Pols Voice", "Dungeon enemies", "L5", A(0x16)), ("Gibdo", "Dungeon enemies", "L5", A(0x30)),
  ("Vire", "Dungeon enemies", "L4", A(0x12)), ("Like Like", "Dungeon enemies", "L4", A(0x17)),
  ("Wizzrobe (blue)", "Dungeon enemies", "L6", A(0x23)), ("Wizzrobe (red)", "Dungeon enemies", "L6", A(0x24)),
  ("Bubble", "Dungeon enemies", "L1", A(0x2B)), ("Blade trap", "Dungeon enemies", "L1", A(0x49)),
  # bosses
  ("Aquamentus", "Bosses", "L1", ("aquamentus", None, ["frame 1", "frame 2"])),
  ("Dodongo", "Bosses", "L2", A(0x31)), ("Manhandla", "Bosses", "L3", A(0x3C)), ("Gleeok head", "Bosses", "L4", A(0x46)),
  ("Gohma (red)", "Bosses", "L6", A(0x33)), ("Gohma (blue)", "Bosses", "L6", A(0x34)), ("Digdogger", "Bosses", "L7", A(0x18)), ("Digdogger (small)", "Bosses", "L7", A(0x38)),
  ("Moldorm", "Bosses", "L2", A(0x41)), ("Patra", "Bosses", "L9", A(0x47)),
  ("Ganon", "Bosses", "L9", ("ganon", None, ["frame " + str(i) for i in range(1, 7)])),
  # people and things
  ("Old man", "People", "L1", A(0x4B)),
  ("Zelda", "People", "L9", A(0x37, "standing")), ("Whirlwind", "Effects", "ow", A(0x2E)), ("Fire", "Effects", "L1", A(0x40)),
  ("Rock", "Effects", "ow", A(0x53, "rock")),
  ("Items", "Items", "ow", ("items", None, None)),
]
