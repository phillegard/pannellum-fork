#!/usr/bin/env python3
"""Generate a Pannellum virtual tour from equirectangular panoramas with
position/orientation metadata. Produces a self-contained HTML file with
Street View-style navigation arrows between scenes."""

import argparse
import json
import math
import os
import re
import sys


# ---------------------------------------------------------------------------
# Quaternion helpers (pure Python, no dependencies)
# ---------------------------------------------------------------------------

def quat_conjugate(q):
    """Return conjugate (inverse for unit quaternions) [w, x, y, z]."""
    return [q[0], -q[1], -q[2], -q[3]]


def quat_multiply(a, b):
    """Hamilton product of two quaternions [w, x, y, z]."""
    return [
        a[0]*b[0] - a[1]*b[1] - a[2]*b[2] - a[3]*b[3],
        a[0]*b[1] + a[1]*b[0] + a[2]*b[3] - a[3]*b[2],
        a[0]*b[2] - a[1]*b[3] + a[2]*b[0] + a[3]*b[1],
        a[0]*b[3] + a[1]*b[2] - a[2]*b[1] + a[3]*b[0],
    ]


def quat_rotate(q, v):
    """Rotate vector v=[x,y,z] by quaternion q=[w,x,y,z].
    Returns rotated vector via sandwich product q * v * q^-1."""
    v_quat = [0.0, v[0], v[1], v[2]]
    q_conj = quat_conjugate(q)
    result = quat_multiply(quat_multiply(q, v_quat), q_conj)
    return [result[1], result[2], result[3]]


def normalize_vec(v):
    """Normalize a 3D vector."""
    mag = math.sqrt(v[0]**2 + v[1]**2 + v[2]**2)
    if mag < 1e-10:
        return [0.0, 0.0, 0.0]
    return [v[0]/mag, v[1]/mag, v[2]/mag]


# ---------------------------------------------------------------------------
# Data parsing
# ---------------------------------------------------------------------------

def parse_metadata(txt_path):
    """Parse position and orientation from a .txt metadata file.
    Expected format:
        position = [X, Y, Z];
        orientation = [W, X, Y, Z];
    """
    with open(txt_path, 'r') as f:
        content = f.read()

    pos_match = re.search(
        r'position\s*=\s*\[([^\]]+)\]', content)
    ori_match = re.search(
        r'orientation\s*=\s*\[([^\]]+)\]', content)

    if not pos_match or not ori_match:
        print(f"Warning: Could not parse {txt_path}", file=sys.stderr)
        return None

    position = [float(x.strip()) for x in pos_match.group(1).split(',')]
    orientation = [float(x.strip()) for x in ori_match.group(1).split(',')]

    return {'position': position, 'orientation': orientation}


def scan_panoramas(data_dir):
    """Find all .txt + .jpg pairs in data_dir, return list of panorama dicts."""
    panoramas = []
    for fname in sorted(os.listdir(data_dir)):
        if not fname.endswith('.txt'):
            continue
        base = fname[:-4]
        jpg_path = os.path.join(data_dir, base + '.jpg')
        txt_path = os.path.join(data_dir, fname)

        if not os.path.exists(jpg_path):
            print(f"Warning: No .jpg for {fname}, skipping", file=sys.stderr)
            continue

        meta = parse_metadata(txt_path)
        if meta is None:
            continue

        panoramas.append({
            'name': base,
            'jpg_path': jpg_path,
            'position': meta['position'],
            'orientation': meta['orientation'],
        })

    return panoramas


# ---------------------------------------------------------------------------
# Geometry: compute yaw from panorama A to panorama B
# ---------------------------------------------------------------------------

def compute_hotspot_yaw(pano_a, pano_b, yaw_offset=0.0):
    """Compute the Pannellum yaw (degrees) from pano_a looking toward pano_b.

    Steps:
    1. Direction vector in world space: D = normalize(B.pos - A.pos)
    2. Rotate to camera-local space: D_local = Q_A^-1 * D * Q_A
    3. Convert to yaw: atan2(D_local.x, D_local.y) where +Y=forward, +X=right
    """
    pos_a = pano_a['position']
    pos_b = pano_b['position']
    q_a = pano_a['orientation']  # [w, x, y, z]

    # World-space direction from A to B
    diff = [pos_b[i] - pos_a[i] for i in range(3)]
    d_world = normalize_vec(diff)

    # Rotate direction into camera-local space using inverse of camera's
    # orientation. For unit quaternion, inverse = conjugate.
    q_inv = quat_conjugate(q_a)
    d_local = quat_rotate(q_inv, d_world)

    # Convert to Pannellum yaw. Pannellum yaw: 0 = center of image,
    # positive = right. Camera local space: +Y = forward, +X = right, +Z = up.
    # atan2(right, forward) gives clockwise angle from forward, matching
    # Pannellum's yaw convention.
    yaw_rad = math.atan2(d_local[0], d_local[1])
    yaw_deg = math.degrees(yaw_rad) + yaw_offset

    # Normalize to [-180, 180]
    yaw_deg = ((yaw_deg + 180) % 360) - 180

    return yaw_deg


def compute_distance(pano_a, pano_b):
    """Euclidean distance between two panoramas."""
    diff = [pano_b['position'][i] - pano_a['position'][i] for i in range(3)]
    return math.sqrt(sum(d**2 for d in diff))


def compute_north_offset(pano):
    """Compute northOffset for a panorama scene.

    Transform camera forward [0,1,0] to world space, then compute
    heading angle from +Y axis (treated as North).
    Returns degrees.
    """
    q = pano['orientation']
    forward_world = quat_rotate(q, [0.0, 1.0, 0.0])
    # Heading: angle from +Y axis, clockwise positive
    heading_deg = math.degrees(math.atan2(forward_world[0], forward_world[1]))
    return heading_deg


# ---------------------------------------------------------------------------
# Scene ID / title helpers
# ---------------------------------------------------------------------------

def make_scene_id(name):
    """Create a URL-safe scene ID from panorama name."""
    return re.sub(r'[^a-zA-Z0-9]+', '_', name).strip('_').lower()


def make_title(name):
    """Create a human-readable title from panorama name."""
    # Strip common prefixes like "Job 030- "
    title = re.sub(r'^Job\s+\d+-?\s*', '', name)
    return title.strip() or name


# ---------------------------------------------------------------------------
# Tour config generation
# ---------------------------------------------------------------------------

def generate_tour_config(panoramas, output_dir, data_dir,
                         yaw_offset=0.0, debug=False):
    """Generate the Pannellum tour configuration dict."""
    scenes = {}
    scene_ids = []

    for pano in panoramas:
        sid = make_scene_id(pano['name'])
        scene_ids.append(sid)
        pano['scene_id'] = sid

    first_scene = scene_ids[0] if scene_ids else None

    for i, pano in enumerate(panoramas):
        sid = pano['scene_id']
        north_offset = compute_north_offset(pano)

        # Relative path from output_dir to the jpg
        jpg_abs = os.path.abspath(pano['jpg_path'])
        out_abs = os.path.abspath(output_dir)
        panorama_path = os.path.relpath(jpg_abs, out_abs)

        hotspots = []
        for j, other in enumerate(panoramas):
            if i == j:
                continue
            yaw = compute_hotspot_yaw(pano, other, yaw_offset)
            dist = compute_distance(pano, other)

            hotspots.append({
                'pitch': 0,
                'yaw': round(yaw, 2),
                'type': 'scene',
                'text': f'{make_title(other["name"])} ({dist:.1f}m)',
                'sceneId': other['scene_id'],
                'targetYaw': 'sameAzimuth',
                'targetPitch': 'same',
                'cssClass': 'streetview-arrow',
                'scale': True,
            })

        scenes[sid] = {
            'title': make_title(pano['name']),
            'panorama': panorama_path,
            'northOffset': round(north_offset, 2),
            'hotSpots': hotspots,
        }

        if debug:
            scenes[sid]['hotSpotDebug'] = True

    tour_config = {
        'default': {
            'firstScene': first_scene,
            'sceneFadeDuration': 1000,
            'autoLoad': True,
            'compass': True,
        },
        'scenes': scenes,
    }

    return tour_config


# ---------------------------------------------------------------------------
# HTML output
# ---------------------------------------------------------------------------

HTML_TEMPLATE = """\
<!DOCTYPE html>
<html>
<head>
    <meta charset="utf-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Panorama Tour</title>
    <link rel="stylesheet" href="../src/css/pannellum.css">
    <style>
        html, body {{
            margin: 0;
            padding: 0;
            overflow: hidden;
            background: #000;
        }}
        #panorama {{
            width: 100vw;
            height: 100vh;
        }}

        /* Street View arrow hotspot styling */
        .pnlm-hotspot-base.streetview-arrow {{
            width: 40px;
            height: 40px;
            margin: -20px 0 0 -20px;
            background: none;
            cursor: pointer;
        }}
        .streetview-arrow .arrow-icon {{
            position: absolute;
            width: 75%;
            height: 75%;
            top: 0;
            left: 0;
            border-radius: 50%;
            background: #4285f4;
            box-shadow: 0 0 0 3px rgba(255, 255, 255, 0.25);
            transition: box-shadow 0.20s ease;
        }}
        .streetview-arrow:hover .arrow-icon {{
            box-shadow: 0 0 0 3px #4285f4;
        }}
        .pnlm-hotspot-base.streetview-arrow:hover {{
            background: none;
        }}
        .pnlm-hotspot-base.streetview-arrow span {{
            visibility: hidden;
            position: absolute;
            background-color: rgba(0, 0, 0, 0.75);
            color: #ffffff;
            border-radius: 4px;
            padding: 4px 10px;
            white-space: nowrap;
            font-size: 13px;
            bottom: 48px;
            left: 50%;
            transform: translateX(-50%);
            pointer-events: none;
        }}
        .pnlm-hotspot-base.streetview-arrow:hover span {{
            visibility: visible;
        }}
    </style>
</head>
<body>
    <div id="panorama"></div>
    <script src="../src/js/libpannellum.js"></script>
    <script src="../src/js/pannellum.js"></script>
    <script>
        var tourConfig = {tour_json};

        // Allow direct linking to a scene via URL hash (e.g., tour.html#job_030_setup_005)
        var hash = window.location.hash.slice(1);
        if (hash && tourConfig.scenes[hash]) {{
            tourConfig.default.firstScene = hash;
        }}

        var viewer = pannellum.viewer('panorama', tourConfig);

        // On each scene load, create .arrow-icon child divs
        viewer.on('load', function() {{
            var cfg = viewer.getConfig();
            if (!cfg.hotSpots) return;
            cfg.hotSpots.forEach(function(hs) {{
                if (hs.cssClass === 'streetview-arrow' && hs.div && !hs._arrowIcon) {{
                    var arrow = document.createElement('div');
                    arrow.className = 'arrow-icon';
                    hs.div.insertBefore(arrow, hs.div.firstChild);
                    hs._arrowIcon = arrow;
                }}
            }});
        }});

        // rAF loop: compute per-arrow screen-space rotation
        (function updateArrows() {{
            var cfg = viewer.getConfig();
            if (cfg && cfg.hotSpots) {{
                var camYaw = viewer.getYaw(), camPitch = viewer.getPitch();
                var hfov = viewer.getHfov();
                var canvas = viewer.getRenderer().getCanvas();
                var cw = canvas.clientWidth;
                var hfovTan = Math.tan(hfov * Math.PI / 360);
                var camPR = camPitch * Math.PI / 180;
                var cpSin = Math.sin(camPR), cpCos = Math.cos(camPR);

                cfg.hotSpots.forEach(function(hs) {{
                    if (!hs._arrowIcon) return;
                    var hpR = hs.pitch * Math.PI / 180;
                    var ydR = (-hs.yaw + camYaw) * Math.PI / 180;
                    var hpS = Math.sin(hpR), hpC = Math.cos(hpR);
                    var yC = Math.cos(ydR), yS = Math.sin(ydR);
                    var z = hpS * cpSin + hpC * yC * cpCos;
                    if (z <= 0) return;
                    var x1 = -cw / hfovTan * yS * hpC / z / 2;
                    var y1 = -cw / hfovTan * (hpS * cpCos - hpC * yC * cpSin) / z / 2;
                    // Point toward horizon (pitch + 1 degree)
                    var upR = (hs.pitch + 1) * Math.PI / 180;
                    var upS = Math.sin(upR), upC = Math.cos(upR);
                    var zU = upS * cpSin + upC * yC * cpCos;
                    if (zU <= 0) return;
                    var x2 = -cw / hfovTan * yS * upC / zU / 2;
                    var y2 = -cw / hfovTan * (upS * cpCos - upC * yC * cpSin) / zU / 2;
                    var angle = Math.atan2(x2 - x1, -(y2 - y1)) * 180 / Math.PI;
                    hs._arrowIcon.style.transform = 'rotate(' + angle + 'deg)';
                }});
            }}
            requestAnimationFrame(updateArrows);
        }})();
    </script>
</body>
</html>
"""


def write_tour_html(tour_config, output_dir):
    """Write the tour HTML file to output_dir/tour.html."""
    os.makedirs(output_dir, exist_ok=True)
    output_path = os.path.join(output_dir, 'tour.html')

    tour_json = json.dumps(tour_config, indent=2)
    html = HTML_TEMPLATE.format(tour_json=tour_json)

    with open(output_path, 'w') as f:
        f.write(html)

    return output_path


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------

def main():
    parser = argparse.ArgumentParser(
        description='Generate a Pannellum virtual tour from panorama data.')
    parser.add_argument('data_dir',
                        help='Directory containing .jpg + .txt panorama pairs')
    parser.add_argument('-o', '--output', default='tour_output',
                        help='Output directory (default: tour_output)')
    parser.add_argument('--yaw-offset', type=float, default=0.0,
                        help='Global yaw offset in degrees for calibration')
    parser.add_argument('--debug', action='store_true',
                        help='Enable hotSpotDebug (click to log yaw/pitch)')
    args = parser.parse_args()

    if not os.path.isdir(args.data_dir):
        print(f"Error: {args.data_dir} is not a directory", file=sys.stderr)
        sys.exit(1)

    panoramas = scan_panoramas(args.data_dir)
    if not panoramas:
        print("Error: No panorama pairs found", file=sys.stderr)
        sys.exit(1)

    print(f"Found {len(panoramas)} panoramas:")
    for p in panoramas:
        print(f"  {p['name']}")
        print(f"    pos={p['position']}, ori={p['orientation']}")

    tour_config = generate_tour_config(
        panoramas, args.output, args.data_dir,
        yaw_offset=args.yaw_offset, debug=args.debug)

    output_path = write_tour_html(tour_config, args.output)
    print(f"\nTour written to: {output_path}")
    print(f"\nTo view, run from the pannellum root directory:")
    print(f"  python3 -m http.server 8000")
    out_display = args.output.rstrip('/')
    print(f"  Open http://localhost:8000/{out_display}/tour.html")

    if args.debug:
        print(f"\nDebug mode enabled: click anywhere to log yaw/pitch")
    if args.yaw_offset != 0:
        print(f"Yaw offset applied: {args.yaw_offset}°")


if __name__ == '__main__':
    main()
