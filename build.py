#!/usr/bin/env python3

import itertools
import multiprocessing.pool
import os
import shutil
import subprocess
import sys
import zipfile
from pathlib import Path

import fontTools.subset
import fontTools.ttLib
import tomllib

from common.helpers import ints_to_unicode_range
from common.structs import Console, FontFile, FontSubset, FontVariant, Subset, Webfont

SCRIPT_PATH = Path(os.path.realpath(__file__))
SCRIPT_DIR = Path(os.path.dirname(SCRIPT_PATH))

REPO_DIR = SCRIPT_DIR.joinpath("repo")
DIST_DIR = REPO_DIR.joinpath("dist")

CONFIG_PKL_FILE = SCRIPT_DIR.joinpath("private-build-plans.pkl")
CONFIG_TOML_FILE = REPO_DIR.joinpath("private-build-plans.toml")

MIN_CHARS_FOR_SUBSET = 8


def main():
    if not os.path.isfile(CONFIG_PKL_FILE):
        raise Exception("missing `private-build-plans.pkl`")

    prepare_repo()
    build_fonts()
    build_nerd_fonts()
    handle_font_folders()
    zip_final_ttc_files()


@Console.grouped("Preparing repo")
def prepare_repo():
    shutil.rmtree(REPO_DIR, ignore_errors=True)

    Console.log("Cloning repo")
    subprocess.run(
        [
            "git",
            "clone",
            "--depth",
            "1",
            "https://github.com/be5invis/Iosevka.git",
            str(REPO_DIR),
        ],
        check=True,
        stdout=sys.stdout,
        stderr=sys.stderr,
    )

    Console.log("Installing npm packages")
    subprocess.run(
        ["npm", "ic"],
        check=True,
        stdout=sys.stdout,
        stderr=sys.stderr,
        cwd=REPO_DIR,
    )


@Console.grouped("Building fonts")
def build_fonts():
    Console.log("Compiling pkl")
    subprocess.run(
        [
            "pkl",
            "eval",
            "--output-path",
            CONFIG_TOML_FILE,
            CONFIG_PKL_FILE,
        ],
        check=True,
    )

    Console.log("Removing old dist")
    shutil.rmtree(DIST_DIR, ignore_errors=True)

    Console.log("Compiling fonts")
    with open(CONFIG_TOML_FILE, "rb") as f:
        build_plans = tomllib.load(f)

    build_plan_names = [f"ttf::{k}" for k in build_plans["buildPlans"]]

    subprocess.run(
        [
            "npm",
            "run",
            "build",
            "--",
            *build_plan_names,
        ],
        stdout=sys.stdout,
        stderr=sys.stderr,
        check=True,
        cwd=REPO_DIR,
    )

    Console.log("Deleting unhinted font variants")
    # Delete the unhinted variants to save space
    for font_folder in os.listdir(DIST_DIR):
        font_folder = DIST_DIR.joinpath(font_folder)
        for font_type in os.listdir(font_folder):
            if font_type.endswith("-Unhinted"):
                shutil.rmtree(font_folder.joinpath(font_type))


@Console.grouped("Building NerdFonts")
def build_nerd_fonts():
    for font_name in os.listdir(DIST_DIR):
        font_folder = DIST_DIR.joinpath(font_name).joinpath("TTF")

        if not font_folder.is_dir():
            continue

        Console.log("Building nerd font for", font_folder.name)
        nerd_font_folder = DIST_DIR.joinpath(font_name + "-NerdFont").joinpath("TTF")
        os.makedirs(nerd_font_folder, exist_ok=True)

        subprocess.run(
            [
                "docker",
                "run",
                "--rm",
                "-v",
                f"{font_folder}:/in:Z",
                "-v",
                f"{nerd_font_folder}:/out:Z",
                "nerdfonts/patcher",
                "--complete",
                "--boxdrawing",
                "--adjust-line-height",
            ],
            stdout=sys.stdout,
            stderr=sys.stderr,
            check=True,
        )


def handle_font_folders():
    for font_name in os.listdir(DIST_DIR):
        handle_font_folder(font_name, DIST_DIR.joinpath(font_name))


@Console.grouped("Handling {0}")
def handle_font_folder(
    font_name: str,
    font_base_dir: Path,
):
    if not os.path.isdir(font_base_dir):
        return

    make_ttc_and_zip(
        font_base_dir.joinpath("TTF"),
        font_base_dir.joinpath(font_name),
    )

    # Don't make NerdFont webfonts
    if not font_base_dir.name.endswith("-NerdFont"):
        make_webfont(font_name, font_base_dir)


def call_star(fn, args):
    return fn(*args)


def make_ttc_and_zip(
    font_dir: Path,
    save_to: Path,
):
    if not os.path.isdir(font_dir):
        return

    with multiprocessing.pool.Pool() as p:
        p.starmap(
            call_star,
            [
                (combine_fonts_into_ttc, (font_dir, save_to)),
                (zip_folder, (font_dir, save_to)),
            ],
        )


def combine_fonts_into_ttc(
    font_dir: Path,
    save_to: Path,
):
    if save_to.suffix != ".ttc":
        save_to = save_to.with_name(save_to.name + ".ttc")

    Console.log(f"Making TTC for {os.path.basename(os.path.dirname(font_dir))}")
    ttc = fontTools.ttLib.TTCollection()
    for font_file_name in os.listdir(font_dir):
        font_path = font_dir.joinpath(font_file_name)
        if font_path.suffix != ".ttf":
            pass
        ttf = fontTools.ttLib.TTFont(file=font_path)
        ttc.fonts.append(ttf)
    Console.log(f"Saving TTC to {save_to}")
    ttc.save(save_to)


def zip_folder(
    font_dir: Path,
    save_to: Path,
):
    Console.log("Zipping folder", font_dir, "->", save_to)
    shutil.make_archive(str(save_to), "zip", font_dir)


@Console.grouped("Making webfont: {0}")
def make_webfont(
    font_name: str,
    font_base_dir: Path,
):
    woff_dir = font_base_dir.joinpath("WOFF2")
    ttf_dir = font_base_dir.joinpath("TTF")

    webfont = Webfont(name=font_name)

    os.makedirs(woff_dir, exist_ok=True)

    with multiprocessing.pool.Pool() as p:
        woff_file_paths = p.starmap(
            font_file_to_woff2,
            [
                (ttf_dir.joinpath(ttf_file_name), woff_dir.joinpath(ttf_file_name))
                for ttf_file_name in os.listdir(ttf_dir)
            ],
        )

    for woff_file_path in woff_file_paths:
        font_var = FontVariant.from_file_path(woff_file_path)
        webfont.variants.append(font_var)

        font_file_to_subsets(font_var, woff_dir)

        if len(font_var.subsets) == 0:
            continue

        font_face_css = "".join(
            font_var.to_css_font_faces(
                font_family=webfont.name,
                relative_to_path=woff_file_path,
            )
        )
        with open(woff_file_path.with_suffix(".css"), "w") as f:
            f.write(font_face_css)

    font_face_css = "".join(
        itertools.chain(
            *[
                f.to_css_font_faces(
                    font_family=webfont.name,
                    relative_to_path=woff_dir,
                )
                for f in webfont.variants
            ]
        )
    )
    with open(woff_dir.joinpath(f"{webfont.name}.css"), "w") as f:
        f.write(font_face_css)


@Console.grouped("Subsetting {0}")
def font_file_to_subsets(
    font_var: FontVariant,
    output_dir: Path,
):
    font_path = font_var.file.file_path

    if not os.path.isfile(font_path):
        return

    with multiprocessing.pool.Pool() as p:
        font_var.subsets = [
            s
            for s in p.starmap(
                font_file_to_subset,
                [
                    (
                        font_var,
                        subset,
                        output_dir.joinpath(
                            f"{font_var.file.file_name_without_ext()}.{subset}.woff2",
                        ),
                    )
                    for subset in list(Subset)
                ],
            )
            if s
        ]
    return font_var


def font_file_to_subset(
    font_var: FontVariant,
    subset: Subset,
    output_path: Path,
):
    subset_unicode = ",".join(subset.as_unicode_range())

    requested_chars = set(fontTools.subset.parse_unicodes(subset_unicode))
    font_chars = font_var.file.available_unicode_characters()
    available_chars = requested_chars.intersection(font_chars)
    n_available_chars = len(available_chars)

    if n_available_chars < MIN_CHARS_FOR_SUBSET:
        Console.log("=" * 80)
        Console.log(
            "Subset",
            subset.name,
            f"too small ({n_available_chars} chars < {MIN_CHARS_FOR_SUBSET} min chars). Skipping.",
        )
        Console.log("=" * 80)
        return None

    Console.log(
        "Subsetting",
        font_var.file.file_name(),
        "to",
        subset.name,
        f"({n_available_chars} chars)",
    )
    available_unicode_range = ints_to_unicode_range(available_chars)  # type: ignore

    output_path = font_file_to_woff2(
        font_var.file.file_path,
        output_path,
        unicodes=",".join(available_unicode_range),
    )

    return FontSubset(
        file=FontFile.from_path(path=output_path, format="woff2"),
        unicode_range=available_unicode_range,
    )


def font_file_to_woff2(
    file_path: Path,
    output_path: Path,
    unicodes: str = "*",
    *,
    additional_args: list[str] = [],
):
    Console.log("Converting", file_path, "to woff2", f"({unicodes})", additional_args)
    output_dir = os.path.dirname(output_path)
    os.makedirs(output_dir, exist_ok=True)
    output_file_path = output_path.with_suffix(".woff2")

    fontTools.subset.main(
        [
            str(file_path),
            "--no-hinting",
            "--desubroutinize",
            "--no-ignore-missing-unicodes",
            "--no-ignore-missing-glyphs",
            "--flavor=woff2",
            f"--unicodes={unicodes}",
            f"--output-file={output_file_path}",
            *additional_args,
        ]
    )

    return output_file_path


@Console.grouped("Zipping TTFs")
def zip_final_ttc_files():
    zip_file_path = DIST_DIR.joinpath("all-ttc.zip")
    with zipfile.ZipFile(zip_file_path, "w", zipfile.ZIP_DEFLATED) as z:
        for font_folder_name in os.listdir(DIST_DIR):
            ttc_font_file_name = f"{font_folder_name}.ttc"
            ttc_font_file = DIST_DIR.joinpath(font_folder_name).joinpath(
                ttc_font_file_name
            )

            if not ttc_font_file.is_file():
                continue

            Console.log("Adding", ttc_font_file_name, "...", end="")
            z.write(ttc_font_file, arcname=ttc_font_file_name)
            Console.log("Done", in_group=False)


if __name__ == "__main__":
    main()
