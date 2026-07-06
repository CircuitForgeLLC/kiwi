#!/usr/bin/env python3
"""Generate a kiwifruit cross-section disc as SVG."""
import math

cx, cy, r = 200, 200, 190  # center and total radius

# Color palette — kiwifruit cross section
SKIN_OUTER  = "#5C3D1E"   # dark brown outer skin
SKIN_INNER  = "#7A5230"   # lighter brown inner skin edge
FLESH       = "#7DC242"   # bright kiwi green flesh
FLESH_DARK  = "#5A9A2A"   # deeper green for radial segment lines
PITH        = "#F2EDD7"   # cream/white center pith
PITH_SHADOW = "#D9D0B0"   # slight shadow on pith edge
SEED_COLOR  = "#2C1A0E"   # very dark brown seeds
SEED_HILITE = "#5C3820"   # seed highlight

def polar(cx, cy, radius, angle_deg):
    a = math.radians(angle_deg)
    return cx + radius * math.cos(a), cy + radius * math.sin(a)

lines = ['<?xml version="1.0" encoding="UTF-8"?>']
lines.append('<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 400 400" width="512" height="512">')
lines.append('  <defs>')
# Radial gradient for flesh (slightly darker at edges)
lines.append('    <radialGradient id="fleshGrad" cx="50%" cy="50%" r="50%">')
lines.append(f'      <stop offset="0%" stop-color="{FLESH}" stop-opacity="1"/>')
lines.append(f'      <stop offset="75%" stop-color="{FLESH}" stop-opacity="1"/>')
lines.append(f'      <stop offset="100%" stop-color="{FLESH_DARK}" stop-opacity="1"/>')
lines.append('    </radialGradient>')
# Radial gradient for pith
lines.append('    <radialGradient id="pithGrad" cx="50%" cy="50%" r="50%">')
lines.append('      <stop offset="0%" stop-color="#FFFFFF" stop-opacity="1"/>')
lines.append(f'      <stop offset="70%" stop-color="{PITH}" stop-opacity="1"/>')
lines.append(f'      <stop offset="100%" stop-color="{PITH_SHADOW}" stop-opacity="1"/>')
lines.append('    </radialGradient>')
lines.append('  </defs>')

# 1. Outer skin (full circle, darkest brown)
lines.append(f'  <circle cx="{cx}" cy="{cy}" r="{r}" fill="{SKIN_OUTER}"/>')

# 2. Inner skin ring (slightly lighter, slightly smaller)
lines.append(f'  <circle cx="{cx}" cy="{cy}" r="{r - 12}" fill="{SKIN_INNER}"/>')

# 3. Green flesh
flesh_r = r - 22
lines.append(f'  <circle cx="{cx}" cy="{cy}" r="{flesh_r}" fill="url(#fleshGrad)"/>')

# 4. Radial segment lines (subtle darker green spokes)
num_segments = 24
pith_r = 42
seed_ring_r = flesh_r * 0.52  # seeds sit about halfway between pith and skin

for i in range(num_segments):
    angle = (360 / num_segments) * i
    x1, y1 = polar(cx, cy, pith_r + 8, angle)
    x2, y2 = polar(cx, cy, flesh_r - 4, angle)
    lines.append(f'  <line x1="{x1:.1f}" y1="{y1:.1f}" x2="{x2:.1f}" y2="{y2:.1f}" '
                 f'stroke="{FLESH_DARK}" stroke-width="1.2" stroke-opacity="0.5"/>')

# 5. Seeds — teardrop shapes arranged in a ring
num_seeds = 22
seed_major = 9    # half-length along radial axis
seed_minor = 5.5  # half-width

for i in range(num_seeds):
    angle_deg = (360 / num_seeds) * i - 90  # start from top
    angle_rad = math.radians(angle_deg)

    # Seed center position
    sx = cx + seed_ring_r * math.cos(angle_rad)
    sy = cy + seed_ring_r * math.sin(angle_rad)

    # Seed is an ellipse rotated to point toward center
    rotate_angle = angle_deg + 90  # perpendicular to radial = tangent orientation
    # Actually seeds point radially (like a pie slice tip toward center)
    rotate_angle = angle_deg  # point toward center

    lines.append(f'  <ellipse cx="{sx:.1f}" cy="{sy:.1f}" '
                 f'rx="{seed_minor}" ry="{seed_major}" '
                 f'fill="{SEED_COLOR}" '
                 f'transform="rotate({rotate_angle:.1f},{sx:.1f},{sy:.1f})"/>')
    # Seed highlight (small inner ellipse, slightly offset)
    hx = sx - seed_minor * 0.25 * math.cos(angle_rad + math.pi/2)
    hy = sy - seed_minor * 0.25 * math.sin(angle_rad + math.pi/2)
    lines.append(f'  <ellipse cx="{hx:.1f}" cy="{hy:.1f}" '
                 f'rx="{seed_minor * 0.35:.1f}" ry="{seed_major * 0.35:.1f}" '
                 f'fill="{SEED_HILITE}" opacity="0.6" '
                 f'transform="rotate({rotate_angle:.1f},{hx:.1f},{hy:.1f})"/>')

# 6. Pith center (cream/white, slightly star-shaped via polygon)
# Use a slightly irregular star for the pith boundary — more organic
num_pith_points = 12
pith_points = []
for i in range(num_pith_points):
    angle = (360 / num_pith_points) * i - 90
    # Alternate between outer and inner radius for star effect
    pr = pith_r if i % 2 == 0 else pith_r * 0.80
    px, py = polar(cx, cy, pr, angle)
    pith_points.append(f"{px:.1f},{py:.1f}")
lines.append(f'  <polygon points="{" ".join(pith_points)}" fill="url(#pithGrad)"/>')

# 7. Tiny dot at absolute center
lines.append(f'  <circle cx="{cx}" cy="{cy}" r="5" fill="{PITH_SHADOW}"/>')

lines.append('</svg>')

svg_content = '\n'.join(lines)

output_path = '/tmp/kiwi_disc.svg'
with open(output_path, 'w') as f:
    f.write(svg_content)

print(f"Written to {output_path}")
print(f"Lines: {len(lines)}, Size: {len(svg_content)} bytes")
