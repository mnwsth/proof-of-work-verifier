"""Shared POW student instructions for Classroom and Google Forms.

Use the same string in the Classroom assignment description and the Form
description so the two surfaces cannot drift.
"""

from __future__ import annotations


MIN_VIDEO_SECONDS = 30

LATE_POLICY = (
    "Late submission policy: the policy takes effect as soon as the submission "
    "deadline passes. Any late submission is graded under that policy. The late "
    "policy applies to the entire team, not only the team lead."
)


def build_pow_instructions(
    *,
    section_label: str,
    exercise_url: str,
    videos: list[tuple[str, list[str]]],
    rubric_text: str,
    youtube_title_suffixes: list[str],
) -> str:
    n = len(videos)
    video_word = "video" if n == 1 else "videos"
    each = "the video" if n == 1 else "each video"
    ids_phrase = (
        "the 11-character video ID"
        if n == 1
        else f"all {n} 11-character video IDs"
    )
    links_phrase = "the Share link" if n == 1 else f"all {n} Share links"
    different_ids = (
        ""
        if n == 1
        else f" The {n} video IDs must be different."
    )
    titles = "\n".join(
        f"   <TEAM-NAME>_<TEAM-LEAD-ID>_{suffix}" for suffix in youtube_title_suffixes
    )
    upload_lines = "\n".join(f"Video {i}: {title}." for i, (title, _) in enumerate(videos, start=1))
    demo_blocks = []
    for i, (title, steps) in enumerate(videos, start=1):
        numbered = "\n".join(f"{j}. {step}" for j, step in enumerate(steps, start=1))
        demo_blocks.append(f"Video {i} — {title}. Demonstrate:\n\n{numbered}")
    demos = "\n\n".join(demo_blocks)
    after_deadline = (
        "After the deadline: do not edit the video in Studio (no trim, cut, blur, or audio replace), "
        "do not change privacy, do not delete the video, and do not replace the Form link with a different video."
        if n == 1
        else "After the deadline: do not edit any video in Studio (no trim, cut, blur, or audio replace), "
        "do not change privacy, do not delete any video, and do not replace any Form link with a different video."
    )
    verify = (
        "We will record the submitted URL shortly after the deadline and later check whether that same video has changed. "
        "A private or deleted video cannot be verified."
        if n == 1
        else "We will record the submitted URLs shortly after the deadline and later check whether those same videos have changed. "
        "A private or deleted video cannot be verified."
    )
    form_paste = (
        "In the Form, paste the Share link (youtu.be/… or youtube.com/watch?v=…) and the 11-character video ID. "
        "Do not paste a Studio/edit URL, a playlist, a Shorts URL, or a channel page."
        if n == 1
        else "In the Form, paste the Share link (youtu.be/… or youtube.com/watch?v=…) and the 11-character video ID for each video. "
        "Do not paste a Studio/edit URL, a playlist, a Shorts URL, or a channel page."
        + different_ids
    )
    return f"""Only the team lead submits, once, for the whole team. Submit only through the Google Form — not as a Classroom file, a Classroom link attachment, or email.

The Google Form accepts only one response per team lead. You cannot edit or resubmit after you send it. Sign in with your @iitgn.ac.in account; the Form records that email automatically. Before you click Submit, check {links_phrase}, {ids_phrase}, that {"the video is" if n == 1 else "all videos are"} Unlisted and playable, and that {each} is at least {MIN_VIDEO_SECONDS} seconds long.{different_ids}

{LATE_POLICY}

Upload {n} Unlisted YouTube {video_word} for {section_label}.

{exercise_url}

{upload_lines}

{"The video" if n == 1 else "All videos"} must clearly show the circuit working. One person from the team must narrate while showing the circuit.

{demos}

Rubric

{rubric_text.rstrip()}

Before you submit, follow these instructions.

1. Every video must be at least {MIN_VIDEO_SECONDS} seconds long.
2. The team lead’s name, or ID number and name, must be clearly visible on the side of each breadboard. Paper tape on the side of the board is fine. Do not place the breadboard on a sheet of paper with names. Videos without this will not be accepted.
3. On YouTube, set {"the video" if n == 1 else "each video"} to Unlisted (not Private, not Public). Wait until processing has finished (the watch page plays and shows a duration).
4. Name the YouTube title{"s" if n > 1 else ""}:
{titles}
5. {form_paste}
6. Submit before the deadline. After the deadline, the late submission policy applies to the entire team.

{after_deadline}

{verify}
"""
