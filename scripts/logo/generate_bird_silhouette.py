#!/usr/bin/env python3
"""
Draw a kiwi bird (Apteryx) silhouette as SVG for use as ControlNet guidance.

Key anatomy:
  - Very round oval body (nearly spherical)
  - Small oval head, short neck
  - EXTREMELY long thin downward-curved beak (≈ body height)
  - No visible wings (vestigial, hidden in feathers)
  - Short stocky legs with 3 forward toes + 1 rear toe

Rendered as colored (rufous brown) on white, 768×768 — gives img2img a palette to work with.
"""

import math

W, H = 768, 768

# Kiwi bird colour palette
COL_BODY   = "#7A3B20"   # dark rufous brown
COL_HEAD   = "#8C4828"   # slightly lighter brown for head
COL_NECK   = "#7A3B20"   # same as body
COL_BEAK   = "#C8A96E"   # horn/tan beak
COL_LEG    = "#4A2410"   # very dark brown legs/feet
COL_EYE_RG = "white"     # eye ring
COL_PUPIL  = "#1A0A00"   # near-black pupil

def pt(x, y): return f"{x:.1f},{y:.1f}"

def bezier_arc(cx, cy, rx, ry, start_deg, end_deg, steps=32):
    """Approximate an ellipse arc as a polyline."""
    points = []
    for i in range(steps + 1):
        t = math.radians(start_deg + (end_deg - start_deg) * i / steps)
        x = cx + rx * math.cos(t)
        y = cy + ry * math.sin(t)
        points.append((x, y))
    return points

lines = [
    '<?xml version="1.0" encoding="UTF-8"?>',
    f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {W} {H}" width="{W}" height="{H}">',
    '  <rect width="100%" height="100%" fill="white"/>',
]

# ── Body ────────────────────────────────────────────────────────────────────
BCX, BCY = 430, 440
BRX, BRY = 155, 175

lines.append(f'  <ellipse cx="{BCX}" cy="{BCY}" rx="{BRX}" ry="{BRY}" fill="{COL_BODY}"/>')

# ── Head ────────────────────────────────────────────────────────────────────
HCX, HCY = 315, 295
HRX, HRY = 60, 52

lines.append(f'  <ellipse cx="{HCX}" cy="{HCY}" rx="{HRX}" ry="{HRY}" fill="{COL_HEAD}"/>')

# ── Neck ────────────────────────────────────────────────────────────────────
neck_path = (
    f'M {pt(HCX - 25, HCY + 42)} '
    f'Q {pt(BCX - 140, BCY - 120)} {pt(BCX - 125, BCY - 148)} '
    f'L {pt(BCX - 60, BCY - 165)} '
    f'Q {pt(HCX + 30, HCY - 30)} {pt(HCX + 30, HCY + 38)} '
    f'Z'
)
lines.append(f'  <path d="{neck_path}" fill="{COL_NECK}"/>')

# ── Beak ────────────────────────────────────────────────────────────────────
# Starts at left side of head, curves to a point
# Kiwi beak: starts narrow at head, stays thin all the way, slight downward arc

beak_base_x = HCX - HRX + 5   # where beak attaches to head (left side)
beak_base_y = HCY + 5
beak_tip_x  = 118              # very long — extends well past the head
beak_tip_y  = HCY + 28         # droops slightly at the tip

# Upper beak edge: from base, curving gently down to tip
# Lower beak edge: parallel, slightly below
beak_w_base = 14   # width at head
beak_w_mid  = 8    # width at midpoint

mid_x = (beak_base_x + beak_tip_x) / 2
mid_y_upper = (beak_base_y - beak_w_base/2 + beak_tip_y - 2) / 2 - 2
mid_y_lower = (beak_base_y + beak_w_base/2 + beak_tip_y + 2) / 2 + 2

beak_path = (
    f'M {pt(beak_base_x, beak_base_y - beak_w_base/2)} '
    f'Q {pt(mid_x, mid_y_upper)} {pt(beak_tip_x, beak_tip_y)} '
    f'Q {pt(mid_x, mid_y_lower)} {pt(beak_base_x, beak_base_y + beak_w_base/2)} '
    f'Z'
)
lines.append(f'  <path d="{beak_path}" fill="{COL_BEAK}"/>')

# ── Legs ────────────────────────────────────────────────────────────────────
def draw_leg(lines, hip_x, foot_x, foot_y, toe_spread=28):
    """Draw a leg with a 3-toed foot."""
    hip_y = BCY + BRY - 20
    ankle_y = foot_y - 22
    leg_w = 20
    leg_path = (
        f'M {pt(hip_x - leg_w/2, hip_y)} '
        f'L {pt(foot_x - leg_w/2, ankle_y)} '
        f'L {pt(foot_x + leg_w/2, ankle_y)} '
        f'L {pt(hip_x + leg_w/2, hip_y)} Z'
    )
    lines.append(f'  <path d="{leg_path}" fill="{COL_LEG}"/>')

    # Three forward toes + one small rear toe
    toe_len = 38
    toe_w = 7
    angles = [-25, 0, 25]   # degrees from horizontal
    for a in angles:
        rad = math.radians(a)
        tx = foot_x + toe_len * math.cos(rad)
        ty = ankle_y + toe_len * math.sin(rad)
        # Toe as thin tapered path
        perp = math.radians(a + 90)
        toe_path = (
            f'M {pt(foot_x + toe_w * math.cos(perp), ankle_y + toe_w * math.sin(perp))} '
            f'L {pt(tx + 2, ty)} '
            f'L {pt(foot_x - toe_w * math.cos(perp), ankle_y - toe_w * math.sin(perp))} Z'
        )
        lines.append(f'  <path d="{toe_path}" fill="{COL_LEG}"/>')

    # Rear hallux
    rear_x = foot_x - 20
    rear_y = ankle_y + 8
    toe_path = (
        f'M {pt(foot_x - 4, ankle_y)} '
        f'L {pt(rear_x, rear_y)} '
        f'L {pt(foot_x + 4, ankle_y)} Z'
    )
    lines.append(f'  <path d="{toe_path}" fill="{COL_LEG}"/>')

# Left leg (slightly forward)
draw_leg(lines, hip_x=BCX - 38, foot_x=BCX - 45, foot_y=BCY + BRY + 52)
# Right leg (slightly behind)
draw_leg(lines, hip_x=BCX + 28, foot_x=BCX + 38, foot_y=BCY + BRY + 45)

# ── Eye ─────────────────────────────────────────────────────────────────────
# Small white circle (eye highlight) on the head
# Kiwi eye is tiny, close to the beak base
eye_x = HCX - 18
eye_y = HCY - 4
lines.append(f'  <circle cx="{eye_x}" cy="{eye_y}" r="10" fill="{COL_EYE_RG}"/>')
lines.append(f'  <circle cx="{eye_x}" cy="{eye_y}" r="5" fill="{COL_PUPIL}"/>')

lines.append('</svg>')

svg = '\n'.join(lines)
out = '/tmp/kiwi_silhouette.svg'
with open(out, 'w') as f:
    f.write(svg)
print(f"Written: {out}")
