# SPDX-License-Identifier: AGPL-3.0-or-later
# Copyright (C) 2014-2026 Mohsen Hozan
#
# This file is part of Emognition. It is free software: you can redistribute
# it and/or modify it under the terms of the GNU Affero General Public License
# as published by the Free Software Foundation, either version 3 of the
# License, or (at your option) any later version. See the LICENSE file.

"""Tests for the UI-free background schedule (core/backgrounds.py)."""

import math
import random

import pytest

from emognition.core.backgrounds import (
    CALM_GRADIENT,
    BackgroundPlan,
    clamp_every_n,
    friendly_name,
    list_pictures,
    plan_backgrounds,
    resolve_background,
    slideshow_index,
)


def _matlab_bgchanger(n_trials: int, intervl: int, n_images: int) -> list[int]:
    """Re-enact bgchanger.m: which picture (0-based) is on screen for each trial.

    pb_beginner.m calls bgchanger with keypresscount == 0 (picture 1); after the
    k-th response, bgchanger switches when k is a multiple of intervl, to
    1+ceil(k/intervl), wrapping past the last picture.
    """
    shown, current = [], 1
    for trial in range(1, n_trials + 1):
        shown.append(current - 1)
        k = trial  # keypresscount after answering this trial
        if round(k / intervl) == k / intervl:
            indx = 1 + math.ceil(k / intervl)
            while indx > n_images:
                indx -= n_images
            current = indx
    return shown


@pytest.mark.parametrize("every_n", [1, 2, 5, 20])
@pytest.mark.parametrize("n_images", [1, 2, 3, 6])
def test_slideshow_index_matches_matlab(every_n, n_images):
    expected = _matlab_bgchanger(60, every_n, n_images)
    assert [slideshow_index(t, every_n, n_images) for t in range(1, 61)] == expected


def test_clamp_every_n_uses_matlab_range():
    assert clamp_every_n(0) == 1
    assert clamp_every_n(5) == 5
    assert clamp_every_n(99) == 20


def test_slideshow_index_rejects_bad_input():
    with pytest.raises(ValueError):
        slideshow_index(1, 5, 0)
    with pytest.raises(ValueError):
        slideshow_index(0, 5, 3)


def test_list_pictures_is_case_insensitive_sorted_and_skips_junk(tmp_path):
    for name in ["b.JPG", "a.png", "pic10.jpg", "pic2.jpeg", ".hidden.png", "notes.txt"]:
        (tmp_path / name).write_bytes(b"x")
    (tmp_path / "folder.png").mkdir()  # a directory with a picture-like name
    names = [p.rsplit("/", 1)[-1].rsplit("\\", 1)[-1] for p in list_pictures(str(tmp_path))]
    assert names == ["a.png", "b.JPG", "pic2.jpeg", "pic10.jpg"]


def test_list_pictures_keeps_folder_order_and_skips_missing(tmp_path):
    first, second = tmp_path / "bundled", tmp_path / "user"
    first.mkdir(); second.mkdir()
    (first / "z.png").write_bytes(b"x")
    (second / "a.png").write_bytes(b"x")
    found = list_pictures(str(first), str(tmp_path / "missing"), str(second))
    assert [p.endswith("z.png") for p in found] == [True, False]


@pytest.mark.parametrize("source, label", [
    ("03-rolling-hills.jpg", "Rolling hills"),
    ("/x/05_classic_purple.JPG", "Classic purple"),
    ("IMG_1234.jpeg", "IMG 1234"),
    ("123.png", "123"),
    (CALM_GRADIENT, "Calm gradient"),
])
def test_friendly_name(source, label):
    assert friendly_name(source) == label


def test_plan_shuffles_once_reproducibly():
    pics = [f"p{i}.jpg" for i in range(6)]
    a = plan_backgrounds(pics, shuffle=True, rng=random.Random(7))
    b = plan_backgrounds(pics, shuffle=True, rng=random.Random(7))
    assert a.sources == b.sources and sorted(a.sources) == sorted(pics)
    assert a.shuffled
    plain = plan_backgrounds(pics, shuffle=False)
    assert plain.sources == tuple(pics) and not plain.shuffled


def test_a_slideshow_starts_with_the_chosen_picture():
    pics = [f"p{i}.jpg" for i in range(6)]
    in_order = plan_backgrounds(pics, shuffle=False, first="p3.jpg")
    assert in_order.sources == ("p3.jpg", "p4.jpg", "p5.jpg", "p0.jpg", "p1.jpg", "p2.jpg")
    shuffled = plan_backgrounds(pics, shuffle=True, rng=random.Random(7), first="p3.jpg")
    assert shuffled.sources[0] == "p3.jpg" and sorted(shuffled.sources) == sorted(pics)
    again = plan_backgrounds(pics, shuffle=True, rng=random.Random(7), first="p3.jpg")
    assert again.sources == shuffled.sources                       # still reproducible
    outside = plan_backgrounds(pics, shuffle=False, first="mine.jpg")
    assert outside.sources[0] == "mine.jpg" and len(outside.sources) == 7


def test_single_picture_is_never_marked_shuffled():
    plan = plan_backgrounds(["only.jpg"], shuffle=True, every_n=50)
    assert not plan.shuffled and not plan.is_slideshow and plan.every_n == 20


def test_source_for_trial_and_next_change():
    plan = BackgroundPlan(sources=("a", "b", "c"), every_n=5)
    assert [plan.source_for_trial(t) for t in (1, 5, 6, 11, 16)] == ["a", "a", "b", "c", "a"]
    assert plan.next_change_after(1, 12) == 6
    assert plan.next_change_after(7, 12) == 11
    assert plan.next_change_after(11, 12) is None        # no later block in range
    assert BackgroundPlan().next_change_after(1, 99) is None   # static default


def test_plain_plan_has_no_pictures():
    plan = BackgroundPlan(sources=())
    assert plan.is_plain and plan.first is None and plan.source_for_trial(3) is None


@pytest.mark.parametrize("plan, text", [
    (BackgroundPlan(), "Calm gradient"),
    (BackgroundPlan(sources=()), "None (plain)"),
    (BackgroundPlan(sources=("/p/02-under-the-sea.jpg",)), "Under the sea"),
    (BackgroundPlan(sources=("a", "b", "c"), every_n=5, shuffled=True),
     "Slideshow: 3 pictures, every 5 trials, shuffled"),
    (BackgroundPlan(sources=("a", "b"), every_n=1), "Slideshow: 2 pictures, every trial, in order"),
])
def test_describe(plan, text):
    assert plan.describe() == text


def test_resolve_specials_and_paths(tmp_path):
    pics = tmp_path / "pics"
    pics.mkdir()
    for name in ("one.png", "two.jpg"):
        (pics / name).write_bytes(b"x")
    assert resolve_background("Default") == BackgroundPlan()
    assert resolve_background(None) == BackgroundPlan()
    assert resolve_background("none").is_plain

    show = resolve_background("slideshow", picture_folders=[str(pics)], shuffle=False, every_n=3)
    assert show.is_slideshow and show.every_n == 3 and not show.shuffled

    folder = resolve_background(str(pics), shuffle=False)
    assert [s.endswith(("one.png", "two.jpg")) for s in folder.sources] == [True, True]

    single = resolve_background(str(pics / "two.jpg"))
    assert single.sources == (str(pics / "two.jpg"),) and not single.is_slideshow


@pytest.mark.parametrize("make", ["missing", "not_picture", "empty_folder", "empty_slideshow"])
def test_resolve_rejects_unusable_settings(tmp_path, make):
    if make == "missing":
        spec, folders = str(tmp_path / "nope.png"), ()
    elif make == "not_picture":
        (tmp_path / "doc.txt").write_text("hi")
        spec, folders = str(tmp_path / "doc.txt"), ()
    elif make == "empty_folder":
        (tmp_path / "empty").mkdir()
        spec, folders = str(tmp_path / "empty"), ()
    else:
        spec, folders = "slideshow", (str(tmp_path / "missing"),)
    with pytest.raises(ValueError):
        resolve_background(spec, picture_folders=folders)
