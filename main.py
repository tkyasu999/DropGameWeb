
import asyncio
import math
import random
from dataclasses import dataclass

import pygame

# ----------------------------
# Suika-like (Watermelon) Game
# - Pure pygame (no native physics libs)
# - pygbag-friendly async main loop
# ----------------------------

# Window / playfield
W, H = 480, 820
FPS = 60

# Playfield walls
WALL = 18
FLOOR_Y = H - 24
CEIL_Y = 80  # top margin for UI
GAMEOVER_LINE_Y = 140  # if a fruit crosses this line -> game over

# Physics constants (tuned for "suika-ish" feel)
GRAVITY = 1700.0               # px/s^2
AIR_DAMPING = 0.999            # per-step damping
RESTITUTION = 0.12             # bounciness
FRICTION = 0.985               # tangential damping on contact
MAX_SPEED = 2600.0

# Merge rules
MERGE_COOLDOWN_FRAMES = 8      # prevent immediate double merges
MERGE_DISTANCE_EPS = 0.5       # small overlap allowance
SPAWN_COOLDOWN = 0.38          # seconds between spawns

# Fruits: radius increases; colors are arbitrary but pleasant
# Level 0..10 (last is "watermelon" like)
FRUITS = [
    ("cherry",   16, (235,  64,  52),  1),
    ("strawb",   21, (255,  86, 126),  3),
    ("grape",    26, (156,  77, 255),  6),
    ("dekopon",  32, (255, 164,  46), 10),
    ("orange",   39, (255, 126,  33), 15),
    ("apple",    47, (210,  40,  70), 21),
    ("pear",     56, (120, 210,  70), 28),
    ("peach",    66, (255, 166, 180), 36),
    ("pine",     78, (255, 220,  60), 45),
    ("melon",    92, (120, 220, 170), 55),
    ("water",   110, ( 70, 190,  90), 70),
]

# Spawn bag (smaller fruits more common)
SPAWN_LEVELS = [0, 0, 1, 1, 2, 2, 3, 3, 4]

BG = (18, 18, 24)
PANEL = (28, 28, 38)
WHITE = (240, 240, 245)
GRAY = (165, 165, 175)
LINE = (255, 90, 90)


@dataclass
class Ball:
    x: float
    y: float
    vx: float
    vy: float
    level: int
    r: float
    color: tuple
    score: int
    merge_cd: int = 0  # frames until it can merge again
    id: int = 0        # for debugging / stable ordering


def clamp(v, lo, hi):
    return lo if v < lo else hi if v > hi else v


def draw_text(surface, font, txt, x, y, color=WHITE, align="topleft"):
    s = font.render(txt, True, color)
    rect = s.get_rect()
    setattr(rect, align, (x, y))
    surface.blit(s, rect)


def make_ball(x, y, level, ball_id):
    _name, r, color, sc = FRUITS[level]
    return Ball(
        x=float(x), y=float(y),
        vx=0.0, vy=0.0,
        level=level, r=float(r),
        color=color, score=sc,
        merge_cd=0, id=ball_id
    )


def resolve_wall_collisions(b: Ball):
    # Left wall
    if b.x - b.r < WALL:
        b.x = WALL + b.r
        b.vx = -b.vx * (0.7 + RESTITUTION)
        b.vy *= 0.98

    # Right wall
    if b.x + b.r > W - WALL:
        b.x = W - WALL - b.r
        b.vx = -b.vx * (0.7 + RESTITUTION)
        b.vy *= 0.98

    # Floor
    if b.y + b.r > FLOOR_Y:
        b.y = FLOOR_Y - b.r
        if b.vy > 0:
            b.vy = -b.vy * (0.45 + RESTITUTION)

        # friction on floor
        b.vx *= FRICTION
        if abs(b.vy) < 28:
            b.vy = 0.0


def resolve_ball_collision(a: Ball, b: Ball):
    dx = b.x - a.x
    dy = b.y - a.y
    dist = math.sqrt(dx * dx + dy * dy) + 1e-9
    min_dist = a.r + b.r

    if dist >= min_dist:
        return False

    # Separate overlap
    overlap = (min_dist - dist) + MERGE_DISTANCE_EPS
    nx = dx / dist
    ny = dy / dist

    # push out equally
    a.x -= nx * overlap * 0.5
    a.y -= ny * overlap * 0.5
    b.x += nx * overlap * 0.5
    b.y += ny * overlap * 0.5

    # Relative velocity along normal
    rvx = b.vx - a.vx
    rvy = b.vy - a.vy
    vn = rvx * nx + rvy * ny

    # Only resolve if moving towards each other
    if vn > 0:
        return True

    # Impulse (equal mass approximation)
    j = -(1.0 + RESTITUTION) * vn
    j *= 0.5  # equal masses -> divide by 2

    ix = j * nx
    iy = j * ny

    a.vx -= ix
    a.vy -= iy
    b.vx += ix
    b.vy += iy

    # Tangential friction
    tx = -ny
    ty = nx
    vt = rvx * tx + rvy * ty
    jt = -vt * 0.08
    a.vx -= jt * tx
    a.vy -= jt * ty
    b.vx += jt * tx
    b.vy += jt * ty

    return True


def pick_next_level():
    return random.choice(SPAWN_LEVELS)


async def main():
    pygame.init()
    pygame.display.set_caption("Suika (pygbag) - Pure pygame")
    screen = pygame.display.set_mode((W, H))
    clock = pygame.time.Clock()

    font = pygame.font.SysFont("Arial", 22)
    font2 = pygame.font.SysFont("Arial", 18)
    big = pygame.font.SysFont("Arial", 44, bold=True)

    balls = []
    next_level = pick_next_level()
    score = 0
    ball_id = 1

    # drop control
    drop_x = W * 0.5
    last_spawn_t = -999.0
    started = False
    gameover = False
    gameover_flash = 0.0

    # For "game over" stability
    over_line_time = 0.0

    dt = 1.0 / FPS

    def reset():
        nonlocal balls, next_level, score, ball_id, started, gameover, over_line_time, last_spawn_t
        balls = []
        next_level = pick_next_level()
        score = 0
        ball_id = 1
        started = False
        gameover = False
        gameover_flash = 0.0
        over_line_time = 0.0
        last_spawn_t = -999.0

    running = True
    t = 0.0

    while running:
        clock.tick(FPS)
        t += dt

        # --- input ---
        for event in pygame.event.get():
            if event.type == pygame.QUIT:
                running = False

            if event.type == pygame.MOUSEMOTION:
                mx, _my = event.pos
                drop_x = clamp(mx, WALL + 20, W - WALL - 20)

            if event.type == pygame.MOUSEBUTTONDOWN and event.button == 1:
                if gameover:
                    reset()
                    continue

                started = True

                if t - last_spawn_t >= SPAWN_COOLDOWN:
                    lv = next_level
                    next_level = pick_next_level()
                    b = make_ball(drop_x, CEIL_Y + 30, lv, ball_id)
                    ball_id += 1
                    balls.append(b)
                    last_spawn_t = t

            if event.type == pygame.KEYDOWN:
                if event.key == pygame.K_r:
                    reset()

        # --- update ---
        if started and not gameover:
            # integrate
            for b in balls:
                if b.merge_cd > 0:
                    b.merge_cd -= 1

                b.vy += GRAVITY * dt
                b.vx *= AIR_DAMPING
                b.vy *= AIR_DAMPING

                sp = math.hypot(b.vx, b.vy)
                if sp > MAX_SPEED:
                    s = MAX_SPEED / (sp + 1e-9)
                    b.vx *= s
                    b.vy *= s

                b.x += b.vx * dt
                b.y += b.vy * dt

                resolve_wall_collisions(b)

            # collisions (iterative)
            for _ in range(3):
                for i in range(len(balls)):
                    for j in range(i + 1, len(balls)):
                        resolve_ball_collision(balls[i], balls[j])
                for b in balls:
                    resolve_wall_collisions(b)

            # merges
            merged_any = True
            while merged_any:
                merged_any = False
                for i in range(len(balls)):
                    a = balls[i]
                    if a.merge_cd > 0:
                        continue
                    for j in range(i + 1, len(balls)):
                        b = balls[j]
                        if b.merge_cd > 0:
                            continue
                        if a.level != b.level:
                            continue

                        dist = math.hypot(b.x - a.x, b.y - a.y)
                        if dist <= a.r + b.r + 0.5:
                            if a.level < len(FRUITS) - 1:
                                new_level = a.level + 1
                                nx = (a.x + b.x) * 0.5
                                ny = (a.y + b.y) * 0.5
                                nvx = (a.vx + b.vx) * 0.5
                                nvy = (a.vy + b.vy) * 0.5

                                score += (a.score + b.score) + (new_level + 1)

                                balls.pop(j)
                                balls.pop(i)

                                nb = make_ball(nx, ny, new_level, ball_id)
                                ball_id += 1
                                nb.vx = nvx * 0.65
                                nb.vy = nvy * 0.65
                                nb.merge_cd = MERGE_COOLDOWN_FRAMES
                                balls.append(nb)

                                merged_any = True
                                break
                    if merged_any:
                        break

            # game over check
            any_over = False
            for b in balls:
                if (b.y - b.r) < GAMEOVER_LINE_Y:
                    any_over = True
                    break

            if any_over:
                over_line_time += dt
            else:
                over_line_time = max(0.0, over_line_time - dt * 0.5)

            if over_line_time >= 1.0:
                gameover = True
                gameover_flash = 0.0

        if gameover:
            gameover_flash += dt

        # --- draw ---
        screen.fill(BG)

        pygame.draw.rect(
            screen, PANEL,
            (WALL, CEIL_Y, W - 2 * WALL, FLOOR_Y - CEIL_Y),
            border_radius=14
        )
        pygame.draw.rect(
            screen, (60, 60, 80),
            (WALL, CEIL_Y, W - 2 * WALL, FLOOR_Y - CEIL_Y),
            3, border_radius=14
        )
        pygame.draw.line(
            screen, LINE,
            (WALL + 6, GAMEOVER_LINE_Y),
            (W - WALL - 6, GAMEOVER_LINE_Y),
            3
        )

        # preview next fruit at drop position
        if not gameover:
            name, r, color, _sc = FRUITS[next_level]
            px = clamp(drop_x, WALL + r + 2, W - WALL - r - 2)
            pygame.draw.circle(screen, color, (int(px), int(CEIL_Y + 30)), int(r))
            pygame.draw.circle(screen, (255, 255, 255), (int(px), int(CEIL_Y + 30)), int(r), 2)
            draw_text(screen, font2, f"NEXT: {name}", 18, 46, GRAY, "topleft")

        # balls
        for b in balls:
            pygame.draw.circle(screen, b.color, (int(b.x), int(b.y)), int(b.r))
            pygame.draw.circle(screen, (255, 255, 255), (int(b.x), int(b.y)), int(b.r), 2)

        # UI
        draw_text(screen, font, f"SCORE: {score}", 18, 18, WHITE, "topleft")
        draw_text(screen, font2, "Click: drop  /  R: reset", W - 18, 22, GRAY, "topright")

        if not started:
            draw_text(screen, big, "CLICK TO START", W // 2, H // 2 - 10, WHITE, "center")
            draw_text(screen, font2, "Drop fruits and merge same ones!", W // 2, H // 2 + 38, GRAY, "center")

        if gameover:
            alpha = 110 + int(60 * math.sin(gameover_flash * 6.0))
            overlay = pygame.Surface((W, H), pygame.SRCALPHA)
            overlay.fill((0, 0, 0, alpha))
            screen.blit(overlay, (0, 0))
            draw_text(screen, big, "GAME OVER", W // 2, H // 2 - 24, (255, 220, 220), "center")
            draw_text(screen, font, f"SCORE: {score}", W // 2, H // 2 + 26, WHITE, "center")
            draw_text(screen, font2, "Click to restart  /  R: reset", W // 2, H // 2 + 64, GRAY, "center")

        pygame.display.flip()

        # ★ pygbag必須：ブラウザへ制御を返す
        await asyncio.sleep(0)


# ★ pygbag必須：ファイル末尾（これより後ろにコードを書かない）
asyncio.run(main())
