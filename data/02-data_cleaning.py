import pandas as pd

import math

 

INPUT_EXCEL = r"/Users/victortimir/Documents/Comanche/concert_data.xlsx"            # from your first script

OUTPUT_EXCEL = r"/Users/victortimir/Documents/Comanche/clean_concert_data.xlsx"  # new file with parsed artists

SHEET_NAME = "all_upcoming"             # sheet from the first script

 

def parse_artists_from_event_name(event_name):

    """

    Try to pull artist names out of the event title.

 

    Examples:

      "Ariana and the Rose w/ Nicole Haber & Cicadachar at Drake Underground"

        -> "Ariana and the Rose, Nicole Haber, Cicadachar"

 

      "JKYL & HYDE"

        -> "JKYL & HYDE"

 

      "Bed By 10 Festival"

        -> None  (we treat these as not having a clear artist list)

    """

    if not isinstance(event_name, str):

        return None

 

    original = event_name.strip()

    if not original:

        return None

 

    lower_orig = original.lower()

 

    # If it's clearly just a festival name (and nothing else), bail out

    # (you can extend this blacklist with more words if needed)

    festival_words = ["festival", "fest"]

    if any(word in lower_orig for word in festival_words):

        # BUT: if the title also has "w/" or "with", we might still parse it

        if " w/ " not in lower_orig and " with " not in lower_orig:

            return None

 

    # Start from the original name

    name = original

    lower = lower_orig

 

    # 1) Drop " at Venue" part: keep everything before the last " at "

    if " at " in lower:

        idx = lower.rfind(" at ")

        name = name[:idx].strip()

        lower = name.lower()

 

    # 2) Split headliner and supports on " w/ ", " with ", " feat. ", " ft. ", " featuring "

    headliner_part = name

    support_part = ""

 

    markers = [" w/ ", " with ", " feat. ", " ft. ", " featuring "]

    marker_used = None

    for marker in markers:

        if marker in lower:

            idx = lower.index(marker)

            marker_used = marker

            headliner_part = name[:idx].strip()

            support_part = name[idx + len(marker):].strip()

            break

 

    artists = []

 

    # Always keep the headliner part if we have it

    if headliner_part:

        artists.append(headliner_part)

 

    # 3) Split supports on "&", "+", " and ", ","

    if support_part:

        temp = support_part.replace("&", ",").replace("+", ",")

        # also handle " and " by turning it into a comma

        temp = temp.replace(" and ", ",")

        parts = [p.strip() for p in temp.split(",") if p.strip()]

        artists.extend(parts)

 

    # If no marker was found and we have no obvious structure,

    # we might just treat the whole cleaned-up title as one artist,

    # unless it contains obvious generic words.

    if not marker_used and len(artists) == 0:

        generic_words = ["night", "party", "brunch", "karaoke", "tribute", "showcase"]

        if not any(word in lower_orig for word in generic_words):

            artists.append(original)

 

    # Final clean-up: remove duplicates, very short junk, etc.

    cleaned = []

    seen = set()

    for a in artists:

        a_clean = a.strip()

        if not a_clean:

            continue

        # ignore single-character fragments

        if len(a_clean) <= 1:

            continue

        key = a_clean.lower()

        if key in seen:

            continue

        seen.add(key)

        cleaned.append(a_clean)

 

    return ", ".join(cleaned) if cleaned else None

 

def is_blank(val):

    if val is None:

        return True

    if isinstance(val, float) and math.isnan(val):

        return True

    if isinstance(val, str) and not val.strip():

        return True

    return False

 

def main():

    print(f"Reading {INPUT_EXCEL} (sheet '{SHEET_NAME}')...")

    df = pd.read_excel(INPUT_EXCEL, sheet_name=SHEET_NAME)

 

    # Make sure expected columns exist

    if "artist" not in df.columns or "name" not in df.columns:

        raise ValueError("Excel must have 'artist' and 'name' columns.")

 

    # Keep a copy of original artist

    df["artist_original"] = df["artist"]

 

    parsed_artists = []

    for _, row in df.iterrows():

        artist_val = row.get("artist")

        event_name = row.get("name")

 

        if is_blank(artist_val):

            parsed = parse_artists_from_event_name(event_name)

        else:

            parsed = None  # don't touch rows that already had an artist

 

        parsed_artists.append(parsed)

 

    df["artist_parsed"] = parsed_artists

 

    # artist_final = original artist if present, otherwise parsed artist

    final_artists = []

    for orig, parsed in zip(df["artist_original"], df["artist_parsed"]):

        if not is_blank(orig):

            final_artists.append(orig)

        else:

            final_artists.append(parsed if not is_blank(parsed) else None)

 

    df["artist_final"] = final_artists

 

    print(f"Writing enriched data to {OUTPUT_EXCEL}...")

    with pd.ExcelWriter(OUTPUT_EXCEL, engine="openpyxl") as writer:

        df.to_excel(writer, sheet_name="all_upcoming_enriched", index=False)

 

    print("Done.")

    print(f"- Input : {INPUT_EXCEL} (sheet '{SHEET_NAME}')")

    print(f"- Output: {OUTPUT_EXCEL} (sheet 'all_upcoming_enriched')")

 

if __name__ == "__main__":

    main()