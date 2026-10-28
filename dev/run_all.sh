#!/bin/sh
# Runs every browser + engine check. Needs SMB_ROM set (see HANDOFF.md).
cd "$(dirname "$0")" || exit 1
: "${SMB_ROM:?Set SMB_ROM to your Super Mario Bros. (World) .nes}"
status=0
for t in test_bench test_objects test_powerups test_blocks test_sounds test_scope test_music test_ipad test_mechanics test_snapshots; do
  echo "== $t"; python3 "$t.py" || status=1
done
if [ -n "$MM3_ROM" ]; then for t in test_mm3 test_tile_inspector test_color_match; do echo "== $t"; python3 "$t.py" || status=1; done; fi
if [ -n "$SMB2_ROM" ]; then echo "== test_smb2"; python3 test_smb2.py || status=1; fi
exit $status
