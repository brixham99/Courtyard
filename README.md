# Courtyard

Playground games for Archie and Holly, on one isometric screen (pygame-ce).
The first game is **Tag**, played against the computer's robot.

```
git clone https://github.com/brixham99/Courtyard.git
cd Courtyard
pip install -r requirements.txt
python3 game.py
```

Needs Python 3.9+ (pygame-ce, numpy, Pillow).

## Tag rules
- 3 rounds of 60 seconds, and best of three wins the match. One player is **it** at a time.
- If you're it, touch the other player to tag them. Then they're it.
- No tag-backs: the newly tagged player counts to 3 (frozen for 1.5 s), and the tagger is *Safe!* for 2 s.
- Whoever spends less time being it wins the round. A tie goes to whoever made more tags.
- The robot is it first. After that, the loser of the last round starts as it.
- Whoever is it runs 10% faster, so a chase can be won. The robot runs at 94% of your pace.

## Controls (tank-style)
| Key | Action |
| --- | --- |
| Left / Right (A / D) | turn a quarter turn (hold to keep turning) |
| Up (W) | run forwards |
| Down (S) | step backwards |
| M | music on/off |
| Esc | back to the title / quit |
| Enter / Space | start, next round |

## Files
- `game.py`: the app (title, character choice, play, HUD, sound, `--selftest`, `--shots DIR`, `--record OUT.mp4`)
- `tag.py`: the rules, movement, collisions and the robot's brain (no drawing, so it can be tested headless)
- `scene.py`: the courtyard, its obstacles and the backgrounds. `SETTINGS` is where new surroundings go.
- `iso.py`: the 2:1 isometric projection (64×32 tiles). The sun is in the east, so shadows fall west.
- `shots.py`: review screenshots
- `tools/cutout.py`: cuts painted sprites out of the magenta
- `tools/robot_frames.py`: builds the robot's enlarged head and its 8-frame walk in 4 facings from 2 painted views
- `tools/make_sounds.py`: makes the whistle, tag slap, footsteps, robot beeps, cheer and the title tune
- `assets/characters/`: Archie and Holly (from Daleks in Hedges / Haunted Mansion) and the robot
- `assets/art_src/`, `assets/ref/`: the robot's painted sources and Nathan's reference

## Still to come
Football, basketball and batdown; network play (from the Daleks in Hedges LAN code); more backgrounds.
