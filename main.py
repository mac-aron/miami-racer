from ursina import *
from random import choice, uniform, randint
import math, time, os


# ---------- App / Window ----------
app = Ursina(borderless=False)
window.title = 'Miami Racer'
window.color = color.rgb(10, 15, 25)
window.size = (1280, 720)  # helps avoid first-frame UI hiccups


# ---------- Settings ----------
LANE_OFFSET      = 2.0
NUM_LANES        = 3
TILE_LENGTH      = 12
VISIBLE_TILES    = 14
SIDE_STRIP       = 6.2

# Speed/handling (faster)
BASE_SPEED       = 22
MAX_SPEED        = 140
ACCEL            = 18
TURN_LERP        = 12

# Nitro (toggle only)
NITRO_CHARGE_RATE   = 0.45
NITRO_DECAY_RATE    = 1.2
NITRO_MIN_TO_BURST  = 0.35
NITRO_SPEED_MULT    = 3.6
NITRO_FOV_BOOST     = 45

# Difficulty/spawn
OBSTACLE_BASE    = 0.28
OBSTACLE_MAX     = 0.75
DIFFICULTY_RATE  = 0.03

LANE_COOLDOWN    = 0.16
RESPAWN_IFRAME   = 1.25

# Missiles
MISSILE_SPEED        = 60
MISSILE_COOLDOWN     = 0.18
MISSILE_POOL_SIZE    = 20
EXPLOSION_TIME       = 0.35
EXPLOSION_SCALE      = 2.2

# Missile ammo (5 icons + regen)
MISSILE_AMMO_MAX     = 5
MISSILE_BASE_REGEN   = 2.0
MISSILE_REGEN_MIN    = 0.30

# ---------- Audio ----------
SND_ENGINE_FILE    = 'sounds/engine_loop.ogg'
SND_MISSILE_FILE   = 'sounds/missile_launch.wav'
SND_EXPLODE_FILE   = 'sounds/explosion.wav'
SND_MUSIC_FILE     = 'sounds/music.ogg'

ENGINE_BASE_PITCH  = 0.85
ENGINE_MAX_PITCH   = 1.85
ENGINE_BASE_VOL    = 0.35
ENGINE_NITRO_BOOST = 0.08
ENGINE_NITRO_PITCH_BUMP = 0.18

MUSIC_VOL          = 0.55
MUSIC_DUCK_VOL     = 0.30

EXPLOSION_VOL      = 0.55
MISSILE_VOL        = 0.50

SEED_BUILDINGS = [
    'textures/building_0.png',
    'textures/building_1.png',
    'textures/building_2.png',
    'textures/building_3.png',
    'textures/building_4.png'
]


# ---------- Robust Sky ----------
def make_sky():
    tex_path = 'textures/sky.png'
    texture_ok = os.path.exists(tex_path)
    sky = Entity(model='sphere', scale=600, double_sided=True, unlit=True)
    sky.rotation = (0,0,0)
    if texture_ok:
        try:
            sky.texture = tex_path
            sky.color = color.rgba(255,255,255,255)
        except Exception as e:
            print('Sky texture failed, using gradient fallback:', e)
            sky.texture = None
            sky.color = color.rgb(20, 30, 60)
    else:
        sky.texture = None
        sky.color = color.rgb(20, 30, 60)
    return sky

sky = make_sky()


# ---------- Ocean ----------
ocean = Entity(model='plane', texture='textures/ocean.png', scale=(500,1,500),
               y=-0.05, color=color.white, texture_scale=(100,100), unlit=True)


# ---------- Player ----------
player = Entity(
    model='quad',
    texture='textures/car.png',
    color=color.white,
    collider='box',
    scale=(1.6, 1.0),
    position=(0, 0.6, -3),
    billboard=True,
    double_sided=True
)
player.collider = BoxCollider(player, center=Vec3(0,0,0), size=Vec3(1.2,0.6,1.8))


# ---------- Camera ----------
camera.parent = None
camera_target = Entity(position=(0, 2.7, -7.8))
camera.position = camera_target.position
camera.rotation = (11, 0, 0)
camera.fov = 85

def lane_to_x(idx): return (idx - 1) * LANE_OFFSET

def update_camera(dt):
    desired_pos = player.world_position + Vec3(0, 2.7, -7.8)
    desired_pos.x += math.sin(time.time()*2.6) * 0.12
    camera_target.position = lerp(camera_target.position, desired_pos, min(1, 4*dt))
    camera.position = camera_target.position
    camera.rotation_x = 11
    camera.rotation_y = lerp(camera.rotation_y, (player.x - lane_to_x(target_lane))*-3, min(1, 3*dt))
    camera.rotation_z = 0
    target_fov = 85 + (speed-BASE_SPEED)*0.6 + (NITRO_FOV_BOOST if nitro_burning or unlimited_nitro else 0)
    camera.fov = lerp(camera.fov, target_fov, 4*dt)


# ---------- Lighting ----------
AmbientLight(color=color.rgba(255,255,255,150))
DirectionalLight(direction=(1,-1,-0.5), color=color.rgb(255,220,200))


# ---------- World builders ----------
def make_road_tile(z_index):
    tile = Entity(
        model='cube',
        texture='textures/road.png',
        collider=None,
        scale=(NUM_LANES*LANE_OFFSET*2.2, 0.1, TILE_LENGTH),
        position=(0, 0, z_index*TILE_LENGTH),
        color=color.white,
        unlit=True
    )
    for side in (-1, 1):
        Entity(parent=tile, model='cube', color=color.gray,
               scale=(0.1, 0.11, TILE_LENGTH),
               position=(side*NUM_LANES*LANE_OFFSET*1.1, 0.01, 0), unlit=True)
    return tile

def make_building(x, z):
    tex = choice(SEED_BUILDINGS)
    s = uniform(1.2, 2.6)
    h = uniform(2.5, 6.0)
    return Entity(model='cube', texture=tex, position=(x, h/2, z),
                  scale=(s, h, s), collider=None, color=color.white)

def make_palm(x, z):
    return Entity(model='quad', texture='textures/palm.png', position=(x, 2, z),
                  scale=(2.5, 4), double_sided=True, billboard=True)

def make_obstacle():
    e = Entity(model='quad', texture='textures/obstacle.png', color=color.white,
               position=(0, -99, 0), scale=(1.2, 1.2), collider='box',
               double_sided=True, billboard=True)
    e.collider = BoxCollider(e, center=Vec3(0,0,0), size=Vec3(1.0,1.0,1.2))
    return e


# ---------- Nitro fire particles ----------
class FirePuff(Entity):
    def __init__(self):
        tex = 'textures/fire.png'
        if not os.path.exists(tex):
            tex = None
        super().__init__(model='quad', texture=tex, scale=(0.5,0.5),
                         color=color.rgba(255,180,80,200), position=(0,-99,0),
                         double_sided=True, billboard=True, unlit=True)
        self.life = 0
        self.max_life = 0.4
        self.vel = Vec3(0,0,0)
        self.active = False
    def ignite(self, pos, vel, scale=0.6):
        self.position = pos
        self.scale = (scale, scale)
        self.vel = vel
        self.life = self.max_life
        self.color = color.rgba(255, 180, 80, 230)
        self.active = True
        self.enabled = True
    def step(self, dt):
        if not self.active: return
        self.position += self.vel * dt
        self.life -= dt
        a = max(0, int(230 * (self.life/self.max_life)))
        self.color = color.rgba(255, 180, 80, a)
        self.scale *= 1.02
        if self.life <= 0:
            self.active = False
            self.enabled = False
            fire_pool.append(self)

fire_pool = [FirePuff() for _ in range(50)]
active_fire = []
def spawn_fire():
    if not (nitro_burning or unlimited_nitro) or not fire_pool:
        return
    back = player.world_position + Vec3(0, -0.1, -0.6)
    puff = fire_pool.pop()
    spread = Vec3(uniform(-0.2,0.2), uniform(-0.05,0.15), uniform(-0.2,0))
    vel = Vec3(0, 2.0, -6.0) + spread
    puff.ignite(back, vel, scale=uniform(0.45,0.75))
    active_fire.append(puff)


# ---------- Explosion effect ----------
class Explosion(Entity):
    def __init__(self):
        tex = 'textures/explosion.png' if os.path.exists('textures/explosion.png') else ('textures/fire.png' if os.path.exists('textures/fire.png') else None)
        super().__init__(model='quad', texture=tex, position=(0,-99,0),
                         scale=(1,1), color=color.rgba(255,200,120,255),
                         double_sided=True, billboard=True, unlit=True)
        self.t = 0
        self.active = False
    def boom(self, pos):
        self.position = pos
        self.scale = (0.8,0.8)
        self.color = color.rgba(255, 220, 150, 255)
        self.t = 0
        self.active = True
        self.enabled = True
    def step(self, dt):
        if not self.active: return
        self.t += dt
        self.scale = (1 + self.t*EXPLOSION_SCALE, 1 + self.t*EXPLOSION_SCALE)
        self.color = color.rgba(255, 220, 150, int(255*(1 - self.t/EXPLOSION_TIME)))
        if self.t >= EXPLOSION_TIME:
            self.active = False
            self.enabled = False
            explosion_pool.append(self)

explosion_pool = [Explosion() for _ in range(20)]
active_explosions = []
def spawn_explosion(pos):
    if not explosion_pool: return
    e = explosion_pool.pop()
    e.boom(pos)
    active_explosions.append(e)
    play_explosion_sound()


# ---------- Missiles ----------
class Missile(Entity):
    def __init__(self):
        super().__init__(model='quad', texture='textures/missile.png' if os.path.exists('textures/obstacle.png') else None,
                         color=color.rgba(160,220,255,255),
                         position=(0,-99,0), scale=(0.7,1.8), collider='box',
                         double_sided=True, billboard=True, unlit=True)
        self.speed = MISSILE_SPEED
        self.active = False
    def fire(self, pos):
        self.position = pos
        self.active = True
        self.enabled = True
    def step(self, dt):
        if not self.active:
            return
        self.z += self.speed * dt
        hit = self.intersects().entities
        for h in hit:
            if h in active_obstacles:
                spawn_explosion(h.world_position)
                h.enabled = False
                active_obstacles.remove(h)
                obstacle_pool.append(h)
                self.reset()
                break
        if self.z > camera.z + 120:
            self.reset()
    def reset(self):
        self.active = False
        self.enabled = False
        self.position = (0,-99,0)
        missile_pool.append(self)

missile_pool = [Missile() for _ in range(MISSILE_POOL_SIZE)]
active_missiles = []
last_missile_time = 0

def try_fire_missile():
    global last_missile_time, missile_ammo, missile_regen_timer
    now = time.time()
    if now - last_missile_time < MISSILE_COOLDOWN:
        return
    if missile_ammo <= 0:
        return
    if not missile_pool:
        return
    m = missile_pool.pop()
    spawn = player.world_position + Vec3(0, 0.2, 1.0)
    m.fire(spawn)
    active_missiles.append(m)
    last_missile_time = now

    # Consume ammo; update timer and HUD immediately
    missile_ammo = max(0, missile_ammo - 1)
    missile_regen_timer = 0.0
    update_missile_icons()  # ensure HUD reflects the shot this frame

    play_missile_sound()


# ---------- World ----------
tiles = [make_road_tile(i) for i in range(VISIBLE_TILES)]
decor = []
obstacle_pool = [make_obstacle() for _ in range(40)]
active_obstacles = []

def spawn_decor_around(z):
    for side in (-1, 1):
        for _ in range(randint(1, 2)):
            x = side * SIDE_STRIP + uniform(-0.8, 0.8)
            if uniform(0,1) < 0.6:
                decor.append(make_building(x, z + uniform(-TILE_LENGTH/2, TILE_LENGTH/2)))
            else:
                decor.append(make_palm(x, z + uniform(-TILE_LENGTH/2, TILE_LENGTH/2)))

def spawn_obstacle_at(z):
    if not obstacle_pool:
        return
    lane = randint(0, NUM_LANES-1)
    x = lane_to_x(lane)
    e = obstacle_pool.pop()
    e.position = (x, 0.6, z + uniform(-TILE_LENGTH/3, TILE_LENGTH/3))
    e.enabled = True
    active_obstacles.append(e)

for i, t in enumerate(tiles):
    spawn_decor_around(t.z)
    if uniform(0,1) < OBSTACLE_BASE and i > 2:
        spawn_obstacle_at(t.z)


# ---------- HUD (text) ----------
# Move score and speed to top-left (speed below score)
score_text = Text(text='', parent=camera.ui, origin=(-.5,.5), position=(-.88,.45), scale=1, color=color.orange)
speed_text = Text(text='', parent=camera.ui, origin=(-.5,.5), position=(-.88,.40), scale=1, color=color.azure)

info_text = Text(text='A/D or Arrows: lanes | W/S: speed | N: nitro toggle | M: missile\nSpace: Start/Pause | Esc: Quit',
                 parent=camera.ui, origin=(-.5,0), position=(-.88,.30), color=color.rgba(255,255,255,180))
title_text = Text('MIAMI RACER', parent=camera.ui, origin=(0,0), y=.25, scale=2, color=color.color(30,1,0.9))
press_text = Text('Press SPACE to start', parent=camera.ui, origin=(0,0), y=.1, color=color.rgba(255,180,200,210))

# ---------- HUD (icons only) ----------
# Missile icons (appear only when available; no regen bar)
MISSILE_UI_Y = 0.33
MISSILE_UI_SPACING = 0.08
MISSILE_UI_SCALE = (0.06, 0.10)

missile_icons = []
def make_missile_icon(i):
    x = (-0.16) + i*MISSILE_UI_SPACING
    return Entity(parent=camera.ui, model='quad',
                  texture='textures/missile.png' if os.path.exists('textures/missile.png') else None,
                  position=(x, MISSILE_UI_Y), scale=MISSILE_UI_SCALE,
                  color=color.rgba(255,255,255,0), unlit=True)

for i in range(MISSILE_AMMO_MAX):
    missile_icons.append(make_missile_icon(i))

# Nitro icon (shows only when ready to be used)
NITRO_UI_POS = (0.0, 0.40)
NITRO_UI_SCALE = (0.07, 0.07)
nitro_icon = Entity(parent=camera.ui, model='quad',
                    texture='textures/nitro.png' if os.path.exists('textures/nitro.png') else None,
                    position=NITRO_UI_POS, scale=NITRO_UI_SCALE,
                    color=color.rgba(120, 255, 220, 0), unlit=True)


# ---------- Game Vars ----------
speed = BASE_SPEED
target_lane = 1
score = 0
elapsed = 0
game_over = False
paused = True
last_lane_change = 0
invincible_until = 0

# Nitro state
nitro_charge = 1.0
nitro_burning = False
unlimited_nitro = False

# Missile ammo state
missile_ammo = MISSILE_AMMO_MAX
missile_regen_timer = 0.0
missile_regen_time_target = MISSILE_BASE_REGEN

# UI readiness latch
ui_ready = False


def reset_run():
    global speed, target_lane, score, elapsed, game_over, invincible_until
    global nitro_charge, nitro_burning
    global missile_ammo, missile_regen_timer, missile_regen_time_target

    player.position = (0, 0.6, -3)
    target_lane = 1
    speed = BASE_SPEED
    score = 0
    elapsed = 0
    game_over = False
    invincible_until = time.time() + RESPAWN_IFRAME
    nitro_charge = 1.0
    nitro_burning = False

    missile_ammo = MISSILE_AMMO_MAX
    missile_regen_timer = 0.0
    missile_regen_time_target = MISSILE_BASE_REGEN

    for d in decor[:]:
        destroy(d); decor.remove(d)
    for o in active_obstacles[:]:
        o.enabled = False; o.position = (0,-99,0)
        active_obstacles.remove(o); obstacle_pool.append(o)
    for f in active_fire[:]:
        f.active = False; f.enabled = False
        active_fire.remove(f); fire_pool.append(f)
    for e in active_explosions[:]:
        e.active = False; e.enabled = False
        active_explosions.remove(e); explosion_pool.append(e)
    for m in active_missiles[:]:
        m.reset(); active_missiles.remove(m)

    for i, t in enumerate(tiles):
        t.z = i * TILE_LENGTH
        spawn_decor_around(t.z)
        if i > 2 and uniform(0,1) < OBSTACLE_BASE:
            spawn_obstacle_at(t.z)

    update_missile_icons()
    update_nitro_icon()


def toggle_pause():
    global paused
    paused = not paused
    title_text.enabled = paused
    press_text.enabled = paused
    info_text.enabled = paused


def input(key):
    global target_lane, last_lane_change, paused, nitro_burning, nitro_charge, unlimited_nitro, game_over, score
    if key == 'escape':
        application.quit()

    if key == 'space':
        if paused:
            toggle_pause()
            if score == 0 and not game_over:
                reset_run()
        elif game_over:
            toggle_pause()
            reset_run()
        else:
            toggle_pause()

    if paused or game_over:
        return

    now = time.time()
    if now - last_lane_change >= LANE_COOLDOWN:
        if key in ('a','left arrow'):
            target_lane = max(0, target_lane-1); last_lane_change = now
        if key in ('d','right arrow'):
            target_lane = min(NUM_LANES-1, target_lane+1); last_lane_change = now

    # Nitro toggle (N)
    if key == 'n':
        if not unlimited_nitro:
            nitro_burning = not nitro_burning
            if nitro_burning and nitro_charge <= 0:
                nitro_charge = 1.0
        else:
            unlimited_nitro = False
            nitro_burning = False
        update_nitro_icon()

    # Missiles
    if key == 'm':
        try_fire_missile()


# ---------- Audio helpers ----------
def make_audio(path, loop=False, autoplay=False, volume=1.0):
    if not os.path.exists(path):
        print(f'[audio] missing file: {path}')
        return None
    try:
        return Audio(path, loop=loop, autoplay=autoplay, volume=volume)
    except Exception as e:
        print(f'[audio] failed to load {path}:', e)
        return None

engine_audio  = make_audio(SND_ENGINE_FILE, loop=True, autoplay=False, volume=ENGINE_BASE_VOL)
music_audio   = make_audio(SND_MUSIC_FILE,  loop=True, autoplay=True,  volume=MUSIC_VOL)

missile_audio_pool = []
MISSILE_SND_POOL_SIZE = 6
if os.path.exists(SND_MISSILE_FILE):
    for _ in range(MISSILE_SND_POOL_SIZE):
        a = make_audio(SND_MISSILE_FILE, loop=False, autoplay=False, volume=MISSILE_VOL)
        if a: missile_audio_pool.append(a)

explosion_audio_pool = []
EXPLOSION_SND_POOL_SIZE = 6
if os.path.exists(SND_EXPLODE_FILE):
    for _ in range(EXPLOSION_SND_POOL_SIZE):
        a = make_audio(SND_EXPLODE_FILE, loop=False, autoplay=False, volume=EXPLOSION_VOL)
        if a: explosion_audio_pool.append(a)

if engine_audio:
    engine_audio.volume = 0.0
    engine_audio.play()

def play_missile_sound():
    if not missile_audio_pool: return
    for a in missile_audio_pool:
        if not getattr(a, 'playing', False):
            try: a.stop(); a.play()
            except: pass
            return
    try: missile_audio_pool[0].stop(); missile_audio_pool[0].play()
    except: pass

def play_explosion_sound():
    if not explosion_audio_pool: return
    for a in explosion_audio_pool:
        if not getattr(a, 'playing', False):
            try: a.stop(); a.play()
            except: pass
            return
    try: explosion_audio_pool[0].stop(); explosion_audio_pool[0].play()
    except: pass


# ---------- Helpers ----------
def compute_missile_regen_time():
    nitro_on = (nitro_burning or unlimited_nitro)
    ceiling = min(MAX_SPEED * (NITRO_SPEED_MULT if nitro_on else 1.0), 1e9)
    if ceiling <= BASE_SPEED + 1e-6:
        return MISSILE_BASE_REGEN
    norm = clamp((speed - BASE_SPEED) / max(1.0, (ceiling - BASE_SPEED)), 0, 1)
    return max(MISSILE_REGEN_MIN, MISSILE_BASE_REGEN * (1.0 - 0.7*norm))

def update_missile_icons():
    for i in range(MISSILE_AMMO_MAX):
        missile_icons[i].color = color.rgba(255,255,255,255 if i < missile_ammo else 0)

def update_nitro_icon():
    ready = (not nitro_burning) and (nitro_charge >= 1.0 or unlimited_nitro)
    if nitro_icon.texture is None:
        nitro_icon.color = color.rgba(0,0,0,0)
        return
    nitro_icon.color = color.rgba(120,255,220,230 if ready else 0)

def force_ui_update_once():
    for t in (score_text, speed_text, info_text, title_text, press_text):
        if t: t.parent = camera.ui
    for e in missile_icons:
        e.parent = e.parent
    if nitro_icon: nitro_icon.parent = nitro_icon.parent
    title_text.alpha = title_text.alpha
    camera.ui.enabled = True


# ---------- Update ----------
def update():
    global speed, score, elapsed, game_over, nitro_charge, nitro_burning
    global missile_ammo, missile_regen_timer, missile_regen_time_target, ui_ready

    if not ui_ready:
        force_ui_update_once()
        ui_ready = True

    update_camera(time.dt)

    # Pause/over: fade engine, duck music, keep HUD updating
    if paused or game_over:
        if engine_audio:
            engine_audio.volume = lerp(engine_audio.volume, 0.0, min(1, 6*time.dt))
        if music_audio:
            music_audio.volume = lerp(music_audio.volume, MUSIC_DUCK_VOL, min(1, 3*time.dt))
        update_missile_icons()
        update_nitro_icon()
        return
    else:
        if music_audio:
            music_audio.volume = lerp(music_audio.volume, MUSIC_VOL, min(1, 3*time.dt))

    # Difficulty ramp
    elapsed += time.dt
    difficulty = 1.0 + DIFFICULTY_RATE * elapsed
    target_max_speed = min(MAX_SPEED, BASE_SPEED + 22 * (difficulty - 1))
    obstacle_chance = min(OBSTACLE_MAX, OBSTACLE_BASE * difficulty)

    # Nitro logic
    if unlimited_nitro:
        nitro_burning = True
        nitro_charge = 1.0
    else:
        if nitro_burning:
            nitro_charge = clamp(nitro_charge - NITRO_DECAY_RATE * time.dt, 0, 1)
            if nitro_charge <= 0:
                nitro_burning = False
        else:
            nitro_charge = 1.0

    # Speed control
    w = 1.0 if held_keys.get('w', 0) else 0.0
    s = 1.0 if held_keys.get('s', 0) else 0.0
    forward = 1.0 + 0.55*w - 0.25*s

    base_difficulty_speed = BASE_SPEED * (1.0 + (difficulty - 1))
    ceiling = target_max_speed * (NITRO_SPEED_MULT if (nitro_burning or unlimited_nitro) else 1.0)
    desired_unclamped = base_difficulty_speed * forward
    desired = clamp(desired_unclamped, BASE_SPEED, ceiling)

    accel_factor = ACCEL * (1.8 if (nitro_burning or unlimited_nitro) else 1.0)
    speed += (desired - speed) * min(1, accel_factor * time.dt)

    # Car movement/tilt
    target_x = lane_to_x(target_lane)
    player.x = lerp(player.x, target_x, 1 - pow(1 - min(1, TURN_LERP * time.dt), 1))
    skew = clamp((player.x - target_x) * -0.1, -0.15, 0.15)
    player.scale_x = 1.6 * (1 + skew)

    # Nitro fire
    # if nitro_burning or unlimited_nitro:
    #     for _ in range(2 + int(speed/35)):
            # spawn_fire()

    # Step effects
    for f in active_fire[:]:
        f.step(time.dt)
        if not f.active: active_fire.remove(f)
    for e in active_explosions[:]:
        e.step(time.dt)
        if not e.active: active_explosions.remove(e)
    for m in active_missiles[:]:
        m.step(time.dt)
        if not m.active: active_missiles.remove(m)

    # Missile regen (icons pop in)
    if missile_ammo < MISSILE_AMMO_MAX:
        missile_regen_time_target = compute_missile_regen_time()
        missile_regen_timer += time.dt
        if missile_regen_timer >= missile_regen_time_target:
            missile_ammo = min(MISSILE_AMMO_MAX, missile_ammo + 1)
            missile_regen_timer = 0.0
            missile_regen_time_target = compute_missile_regen_time()

    # World scroll
    dz = speed * time.dt
    for t in tiles: t.z -= dz
    for d in decor: d.z -= dz
    for o in active_obstacles: o.z -= dz

    # Recycle and spawn
    far_ahead_z = max(t.z for t in tiles)
    for t in tiles:
        if t.z < player.z - TILE_LENGTH:
            t.z = far_ahead_z + TILE_LENGTH
            far_ahead_z = t.z
            spawn_decor_around(t.z)
            if uniform(0,1) < obstacle_chance:
                spawn_obstacle_at(t.z)

    # Cull behind
    min_keep_z = player.z - TILE_LENGTH*3
    for d in decor[:]:
        if d.z < min_keep_z:
            destroy(d); decor.remove(d)
    for o in active_obstacles[:]:
        if o.z < min_keep_z:
            o.enabled = False; o.position = (0,-99,0)
            active_obstacles.remove(o); obstacle_pool.append(o)

    # Collision with obstacles (i-frames)
    if time.time() >= invincible_until:
        hit = player.intersects().entities
        if any(e in active_obstacles for e in hit):
            # CRASH: show explosion and sound at player, then game over
            spawn_explosion(player.world_position)
            play_explosion_sound()
            game_over = True
            title_text.text = 'CRASH!'
            press_text.text = 'Press SPACE to retry'
            title_text.enabled = True
            press_text.enabled = True
            info_text.enabled = False

    # Engine audio with nitro bump
    if engine_audio:
        nitro_on = (nitro_burning or unlimited_nitro)
        ceiling_for_audio = min(MAX_SPEED * (NITRO_SPEED_MULT if nitro_on else 1.0), 1e9)
        norm = 0.0
        if ceiling_for_audio > 0:
            norm = clamp((speed - BASE_SPEED) / max(1.0, (ceiling_for_audio - BASE_SPEED)), 0, 1)
        base_pitch = ENGINE_BASE_PITCH + (ENGINE_MAX_PITCH - ENGINE_BASE_PITCH) * pow(norm, 0.85)
        if nitro_on:
            base_pitch += ENGINE_NITRO_PITCH_BUMP
        engine_audio.pitch = lerp(getattr(engine_audio, 'pitch', ENGINE_BASE_PITCH), base_pitch, min(1, 7*time.dt))
        target_vol = ENGINE_BASE_VOL + (ENGINE_NITRO_BOOST if nitro_on else 0.0)
        engine_audio.volume = lerp(engine_audio.volume, target_vol, min(1, 4*time.dt))

    # Ensure music keeps playing
    if music_audio and not getattr(music_audio, 'playing', True):
        try: music_audio.play()
        except: pass

    # HUD: score (left) and speed below it
    score += speed * time.dt
    score_text.text = f'Score: {int(score)}'
    speed_text.text = f'{int(speed)} km/h'

    # Update icons
    update_missile_icons()
    update_nitro_icon()


# ---------- Boot overlays ----------
speed = BASE_SPEED
target_lane = 1
score = 0
elapsed = 0
game_over = False
paused = True
last_lane_change = 0
invincible_until = 0
nitro_charge = 1.0
nitro_burning = False
unlimited_nitro = False

# Ensure UI visible at boot
title_text.enabled = True
press_text.enabled = True
info_text.enabled = True
score_text.enabled = True
speed_text.enabled = True

app.run()
