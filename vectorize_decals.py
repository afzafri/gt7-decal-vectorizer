"""Trace exported red/white PNG silhouettes into compact GT7 SVG paths.

Uses ImageMagick to decode pixels; all geometry comes from the source pixels.
No raster embedding, live text, filters, or external dependencies in output.
"""
from pathlib import Path
import argparse
import json
import re
import shutil
import subprocess
import sys
import xml.etree.ElementTree as ET
import zipfile

ROOT = Path(__file__).resolve().parent

def simplify(points, tolerance):
    if len(points) < 3:
        return points
    ax, ay = points[0]
    bx, by = points[-1]
    dx, dy = bx-ax, by-ay
    denom = dx*dx+dy*dy
    best, index = 0, 0
    for i, (x, y) in enumerate(points[1:-1], 1):
        t = max(0, min(1, ((x-ax)*dx+(y-ay)*dy)/denom)) if denom else 0
        distance = (x-ax-t*dx)**2+(y-ay-t*dy)**2
        if distance > best:
            best, index = distance, i
    if best <= tolerance*tolerance:
        return [points[0], points[-1]]
    return simplify(points[:index+1], tolerance)[:-1]+simplify(points[index:], tolerance)

def outlines(mask, w, h, min_area=5):
    edges = {}
    def edge(a, b):
        edges.setdefault(a, []).append(b)
    for y in range(h):
        for x in range(w):
            i = y*w+x
            if not mask[i]:
                continue
            if y == 0 or not mask[i-w]: edge((x,y), (x+1,y))
            if x == w-1 or not mask[i+1]: edge((x+1,y), (x+1,y+1))
            if y == h-1 or not mask[i+w]: edge((x+1,y+1), (x,y+1))
            if x == 0 or not mask[i-1]: edge((x,y+1), (x,y))
    loops = []
    while edges:
        start = next(iter(edges))
        current = start
        loop = [start]
        previous = (start[0]-1, start[1])
        while True:
            choices = edges[current]
            if len(choices) > 1:
                dx, dy = current[0]-previous[0], current[1]-previous[1]
                # At diagonal contacts, keep contours separate by turning right.
                target = (current[0]-dy, current[1]+dx)
                nxt = target if target in choices else choices[0]
                choices.remove(nxt)
            else:
                nxt = choices.pop()
            if not choices: del edges[current]
            previous, current = current, nxt
            if current == start: break
            loop.append(current)
        area = sum(a[0]*b[1]-b[0]*a[1] for a,b in zip(loop, loop[1:]+loop[:1]))/2
        if abs(area) >= min_area:
            loops.append(loop)
    return loops

def path_for(loops, tolerance):
    commands = []
    for loop in loops:
        # Split closed contour at its furthest vertex before RDP simplification.
        a = loop[0]
        k = max(range(len(loop)), key=lambda i: (loop[i][0]-a[0])**2+(loop[i][1]-a[1])**2)
        pts = simplify(loop[:k+1], tolerance)[:-1]+simplify(loop[k:]+[a], tolerance)[:-1]
        if len(pts) < 3: continue
        commands.append('M'+ ' '.join(f'{x},{y}' for x,y in pts)+'z')
    return ''.join(commands)

def hex_color(value):
    if not re.fullmatch(r'#[0-9a-fA-F]{3}([0-9a-fA-F]{3})?', value):
        raise argparse.ArgumentTypeError('Use a hex color such as #fff or #ed0027.')
    return value

def convert(source, args):
    w,h = map(int, subprocess.check_output(['magick','identify','-format','%w %h',str(source)]).split())
    pixels = subprocess.check_output(['magick',str(source),'-colorspace','sRGB','-depth','8','rgba:-'])
    if len(pixels) != w*h*4:
        raise ValueError(f'Unexpected pixel data for {source.name}')
    masks = [bytearray(w*h), bytearray(w*h)]
    for i in range(w*h):
        r,g,b,a = pixels[4*i:4*i+4]
        if a < args.alpha_threshold: continue
        if r > 100 and r > g*1.6 and r > b*1.25:
            masks[1][i] = 1
        elif min(r,g,b) > 100 and r+g+b > 450:
            masks[0][i] = 1
    loops = [outlines(m,w,h,args.min_area) for m in masks]
    if not any(loops):
        raise ValueError(f'No red/white artwork detected in {source.name}')
    colors = [args.white_color,args.red_color]
    tolerance = args.tolerance
    while True:
        paths = ''.join(f'<path fill="{c}" fill-rule="evenodd" d="{d}"/>'
                        for c,l in zip(colors,loops) if (d := path_for(l,tolerance)))
        svg = f'<svg xmlns="http://www.w3.org/2000/svg" version="1.1" width="{w}" height="{h}" viewBox="0 0 {w} {h}">{paths}</svg>'
        if len(svg.encode()) < args.max_bytes: break
        if tolerance >= args.max_tolerance:
            raise ValueError(f'{source.name} exceeds {args.max_bytes} bytes; split the design or increase --max-tolerance.')
        tolerance = min(args.max_tolerance, round(tolerance+0.25, 6))
    root = ET.fromstring(svg)
    if root.get('version') != '1.1' or not all(el.tag.split('}')[-1] in {'svg','path'} for el in root.iter()):
        raise ValueError(f'SVG validation failed for {source.name}')
    return svg, {'file':source.stem+'.svg','bytes':len(svg.encode()),
                 'width':w,'height':h,'simplification_px':tolerance}

def main():
    parser = argparse.ArgumentParser(description='Trace flat red/white PNG decals into transparent GT7 SVG 1.1 paths.')
    parser.add_argument('--input',type=Path,default=ROOT/'To Process PNG',help='Folder of PNGs, nonrecursive; extension is case insensitive.')
    parser.add_argument('--output',type=Path,default=ROOT/'GT7 SVG',help='SVG destination folder.')
    parser.add_argument('--tolerance',type=float,default=1.5,help='Initial contour simplification in source pixels (default: 1.5).')
    parser.add_argument('--max-tolerance',type=float,default=2.5,help='Maximum simplification when reducing file size (default: 2.5).')
    parser.add_argument('--min-area',type=float,default=5,help='Discard contours smaller than this pixel area (default: 5).')
    parser.add_argument('--alpha-threshold',type=int,default=128,help='Ignore pixels below this alpha value (default: 128).')
    parser.add_argument('--max-bytes',type=int,default=15000,help='Every SVG must be strictly below this byte count (default: 15000).')
    parser.add_argument('--white-color',type=hex_color,default='#fff',help='Output color for white source shapes.')
    parser.add_argument('--red-color',type=hex_color,default='#ed0027',help='Output color for red source shapes.')
    parser.add_argument('--preview',action='store_true',help='Render a PNG contact sheet on dark gray.')
    parser.add_argument('--zip',action='store_true',help='Package the converted SVGs in decals.zip.')
    parser.add_argument('--overwrite',action='store_true',help='Allow replacement of generated files.')
    args = parser.parse_args()
    if not shutil.which('magick'): parser.error('ImageMagick 7 is required; magick was not found on PATH.')
    if not args.input.is_dir(): parser.error(f'Input folder does not exist: {args.input}')
    if args.input.resolve() == args.output.resolve(): parser.error('Use separate input and output folders.')
    if not (0 < args.tolerance <= args.max_tolerance) or args.min_area < 0 or not 0 <= args.alpha_threshold <= 255 or args.max_bytes <= 0:
        parser.error('Check tolerances, minimum area, alpha threshold and byte limit.')
    sources = sorted(p for p in args.input.iterdir() if p.is_file() and p.suffix.lower()=='.png')
    if not sources: parser.error('No PNG files found in the input folder.')
    names = [p.stem.lower() for p in sources]
    if len(names) != len(set(names)): parser.error('PNG basenames must be unique, ignoring case.')
    targets = [args.output/(p.stem+'.svg') for p in sources]+[args.output/'validation.json']
    if args.preview: targets.append(args.output/'preview.png')
    if args.zip: targets.append(args.output/'decals.zip')
    if not args.overwrite and any(p.exists() for p in targets):
        parser.error('Output files already exist; use a fresh output folder or --overwrite.')
    # Convert and validate the whole batch before writing final SVGs.
    converted = [(source,*convert(source,args)) for source in sources]
    args.output.mkdir(parents=True,exist_ok=True)
    report = []
    for source,svg,info in converted:
        (args.output/info['file']).write_text(svg,encoding='utf-8')
        report.append(info)
        print(f"{info['file']}: {info['bytes']} bytes")
    (args.output/'validation.json').write_text(json.dumps(report,indent=2)+'\n',encoding='utf-8')
    if args.zip:
        with zipfile.ZipFile(args.output/'decals.zip','w',zipfile.ZIP_DEFLATED) as archive:
            for info in report: archive.write(args.output/info['file'],info['file'])
    if args.preview:
        preview_dir = args.output/'previews'
        preview_dir.mkdir(exist_ok=True)
        images = []
        for info in report:
            image = preview_dir/(Path(info['file']).stem+'.png')
            subprocess.run(['magick','-background','none',str(args.output/info['file']),
                            '-background','#222222','-alpha','remove','-alpha','off',
                            '-resize','900x300','-gravity','center','-extent','940x340',str(image)],check=True)
            images.append(str(image))
        subprocess.run(['magick','montage',*images,'-tile','2x','-geometry','+12+12',
                        '-background','#222222',str(args.output/'preview.png')],check=True)
    print(f'Saved {len(report)} SVGs in {args.output.resolve()}')

if __name__ == '__main__':
    try:
        main()
    except (ValueError,OSError,subprocess.CalledProcessError) as error:
        print(f'Error: {error}',file=sys.stderr)
        sys.exit(1)
