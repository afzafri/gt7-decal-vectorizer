# gt7-decal-vectorizer

Convert red-and-white PNG decals into GT7-ready SVGs under 15 KB, with transparent backgrounds, outlined lettering, batch processing, and previews.

Reusable workflow and companion script: `vectorize_decals.py`.

## Disclaimer

The code was created using **GPT 6.1 Sol**. The PNG decal artwork used during development was also generated using **GPT ImageGen**. PNG and SVG artwork files are not included in this repository.

Review the converted artwork before use. This project is independent and is not affiliated with Gran Turismo, Polyphony Digital, or Sony.

This workflow traces existing artwork into real vector paths. It does not embed a PNG inside an SVG, assemble replacement artwork by hand, or regenerate the design. Image generation is not needed for the conversion step.

## Current limitation

Currently, the script only reliably supports **red-and-white PNG artwork**, on a transparent or black background. Black is treated as empty space. Other source colors may be ignored or classified incorrectly. The output color options recolor detected shapes; they do not change which input colors the script detects.

Photos, gradients, shadows, multicolor artwork, and white backgrounds need a different preparation or tracing method. Gradients within the detected shapes are flattened to two solid colors.

## Project scope and contributions

This tool was initially created for personal use. There are currently no plans to expand it beyond the author's own use case, and there is no committed roadmap.

Possible future improvements include dynamic color detection and user-supplied input palettes or color thresholds, if needed for that use case or contributed by others. These features are not implemented yet.

Feel free to contribute! Bug reports, suggestions, and pull requests are welcome, including improvements that support other artwork colors and use cases.

## Suitable artwork

- Flat red-and-white logos, lettering, and stripes on transparency or a black background.
- Crisp source images with adequate resolution and clear gaps inside letters.
- Other projects using the same source palette; output colors can be changed with options.

This is a **red/white silhouette tracer, not a general full-color vectorizer**.

## Requirements

- Python 3.8 or newer. Only standard-library Python modules are used.
- ImageMagick 7, with the `magick` command available on your PATH. SVG rendering support is also needed for the optional preview.

Check your environment:

```sh
python3 --version
magick -version
```

On macOS, if ImageMagick is missing and you use Homebrew:

```sh
brew install imagemagick
```

## Prepare the PNGs

1. Export the artwork at a useful resolution. Avoid unnecessarily tiny exports: tracing cannot recover detail that is absent from the PNG.
2. Use transparency or solid black around the red/white artwork. A black part of the design will also disappear under this workflow.
3. Leave counters in letters such as A, P, and R clearly open. Keep fine lines and punctuation visible.
4. Put the PNGs in one input folder. Both `.png` and `.PNG` are supported; subfolders are not scanned.
5. Keep original exports unchanged. Use a separate output folder.

## Run the conversion

With the default folder layout, run from the script folder:

```sh
python3 vectorize_decals.py --preview --zip --overwrite
```

The default input is `To Process PNG` beside the script; the default output is `GT7 SVG`. Existing output files require `--overwrite` if you choose to regenerate them.

For another project, copy the script wherever convenient and pass explicit paths:

```sh
python3 "/path/to/vectorize_decals.py" \
  --input "/path/to/another-project/PNG exports" \
  --output "/path/to/another-project/GT7 SVG" \
  --preview --zip
```

Existing generated files are protected by default. Use a new output folder when comparing settings, or add `--overwrite` to intentionally replace them.

## How the tracing works

1. ImageMagick decodes each PNG into sRGB RGBA pixels.
2. Pixels with alpha below 128 are ignored by default.
3. Red shapes are detected when red exceeds 100, green × 1.6, and blue × 1.25. White shapes are detected when all RGB channels exceed 100 and their sum exceeds 450. Remaining pixels become transparent.
4. The script follows the actual pixel boundaries into closed contours. Contours below 5 square pixels are removed to reduce speckles; this also applies to tiny holes.
5. Ramer–Douglas–Peucker simplification reduces contour points, starting at 1.5 source pixels of tolerance. Paths use straight segments; curves are approximated by short segments rather than fitted Bézier curves.
6. White and red contours become two compound paths with `fill-rule="evenodd"`, preserving holes in lettering. The default output colors are white (`#fff`) and racing red (`#ed0027`).
7. If an SVG is too large, simplification increases in 0.25-pixel steps, up to 2.5 pixels by default. If it still exceeds the size limit, the batch fails before final SVGs are written.
8. SVGs are checked for version 1.1, a strictly sub-15,000-byte file size, and an element whitelist containing only `svg` and `path`.

The result has transparent negative space, outlined lettering, no font dependency, no bitmaps, and no filters or blending modes.

## Outputs

- One `.svg` per source PNG, retaining the basename.
- `validation.json`: dimensions, byte count, and simplification tolerance for each SVG.
- With `--preview`: individual rendered PNGs in `previews/` and a dark-gray contact sheet named `preview.png`. Gray is only a preview backdrop; the SVGs remain transparent.
- With `--zip`: `decals.zip`, containing only this run's SVG files.

## Quality checks before upload

Inspect the rendered previews next to the source PNGs:

- Check spelling, punctuation, small lettering, and holes in letters.
- Check that narrow gaps between graphics remain open.
- Check the ends of tapered stripes and the silhouette of curved elements.
- Check that unwanted background areas disappeared.
- Confirm every file is below 15 KB in `validation.json`.

Local validation and rendered previews do not confirm website upload acceptance. Test the final files in the uploader.

## Adjustments

See all options:

```sh
python3 vectorize_decals.py --help
```

Keep more contour detail (usually larger files):

```sh
python3 vectorize_decals.py --input "PNG exports" --output "SVG detailed" \
  --tolerance 1.0 --max-tolerance 1.5 --preview
```

Allow more simplification for a large file, then inspect small details carefully:

```sh
python3 vectorize_decals.py --input "PNG exports" --output "SVG smaller" \
  --tolerance 1.5 --max-tolerance 3.5 --preview
```

Retain tiny punctuation or holes that were removed:

```sh
python3 vectorize_decals.py --input "PNG exports" --output "SVG fine details" \
  --min-area 1 --preview
```

Recolor the detected source shapes for another project:

```sh
python3 vectorize_decals.py --input "PNG exports" --output "SVG recolored" \
  --white-color '#ffffff' --red-color '#0077ff' --preview
```

These color options change the output fills; the input detector still expects red and white. Quote hex values in shell commands so `#` is not interpreted as a comment.

If shapes vanish, first check the source palette, alpha, and resolution. If the design cannot fit the byte limit without losing important detail, split the source into separate decals and position them together in the game's livery editor.

## Upload to GT7

To upload the prepared files:

1. Sign in to the official Gran Turismo website with the same PlayStation Network account used for GT7.
2. Open **My Page → Decal Uploader**.
3. Upload individual `.svg` files from the output folder. Extract `decals.zip` first if using the archive; do not upload the ZIP, JSON, or PNG previews.
4. In GT7, find the uploaded decals under **Showcase → My Library → My Items** and use them in the Livery Editor.

The files are prepared against the supplied SVG 1.0/1.1, outlined lettering, no bitmap, no special blending, and 15 KB requirements. Website upload acceptance is a separate final check.
