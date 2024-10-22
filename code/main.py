from thefuzz import fuzz
from tabulate import tabulate
from tmx2dataframe import tmx2dataframe
import glob
from dataclasses import dataclass
from rich import print

# source_text = input("Source text: ")

@dataclass
class Segment:
    source_lang: str
    source_text: str
    id: str
    file: str
    section: str
    is_translated: bool
    has_context: bool

    
def has_context_binding(segment, match):
    if match["source_sentence"] == segment.source_text \
        and match["id"] == segment.id and match["file"] == segment.file:
        return True
    return False


def get_population_weight(match):
    weight = 2 if match["filepath"].startswith("enforce/") \
        else 1 if match["filepath"].startswith("auto/") else 0
    return weight


def pprint(matches):
    for m in matches:
        print(m)

def compose_segment():
    return Segment(
        source_text="FOO",
        id="tu2_0", # id="tu2_0@item2",
        file="batch/S24030067.html",
        section="item2",
        source_lang="en",
        is_translated=True,
        has_context=False
    )


def collect_all_entries():
    matches = []
    # Returns a list of names in list files.
    files = glob.glob('tm/**/*.tmx', recursive = True)
    for tmx_fpath in files:
        _, df = tmx2dataframe.read(tmx_fpath)
        df['filepath'] = tmx_fpath.lstrip("tm/")
        matches.extend(df.to_dict(orient='records'))
    return matches


def get_ice_matches(segment, matches):
    # see how many entries are exact matches
    return [match for match in matches 
                        if match["source_sentence"] == segment.source_text 
                        and match["id"] == segment.id
                        and match["file"] == segment.file]
    # if none, we have no insertion candidate
    # if one, we can populate the segment
    # if more than one, we need more criteria


def get_exact_matches(segment, matches):
    # see how many entries are exact matches
    return [match for match in matches if match["source_sentence"] == segment.source_text]
    # if none, we have no insertion candidate
    # if one, we can populate the segment
    # if more than one, we need more criteria


def filter_matches_by_weight(matches, weight):
    weighed_matches = [m for m in matches if m["filepath"].startswith(f"{weight}/")]
    if len(weighed_matches) >= 1:
        return weighed_matches
    
    return matches


def sort_matches_by_filepath(matches):
    sorted_matches = sorted(matches, key=lambda x: x['filepath'])
    first_filepath = sorted_matches[0]["filepath"]
    return [m for m in sorted_matches if m["filepath"] == first_filepath]


def sort_matches_by_position(matches):
    sorted_matches = sorted(matches, key=lambda x: x['position'])
    print("Selected the first match from the first file.")
    return sorted_matches[0]


def select_matches(segment, matches):
    # select ice or exact matches
    ice_matches = get_ice_matches(segment, matches)
    pprint(ice_matches)
    if len(ice_matches) >= 1:
        print("2. (A) One or more ICE matches")
        return ice_matches
    else:
        print("2. (A) No ICE matches, look for exact matches without context.")
        exact_matches = get_exact_matches(segment, matches)
        if len(exact_matches) >= 1:
            print("2. (B) One or more exact match")
            return exact_matches
        else:
            print("2. (B) No exact matches, we can't populate the segment :/")
            return []


def find_populating_matches(segment, matches):
    if segment.is_translated and not segment.has_context:
        return filter_matches_by_weight(matches, "enforce")
    elif not segment.is_translated:
        return filter_matches_by_weight(matches, "auto")
    else:
        return []
    

def find_matches_with_weight(perfect_matches, weighed_matches):
    return [
        dict(item) for item in set(tuple(sorted(d.items())) for d in perfect_matches) &
                               set(tuple(sorted(d.items())) for d in weighed_matches)
    ]

def get_weighed_matches(segment, ice_matches, exact_matches):
    if not segment.has_context:
        enforce_ice_matches = filter_matches_by_weight(ice_matches, "enforce")
        if enforce_ice_matches:
            return enforce_ice_matches
        
        auto_ice_matches = filter_matches_by_weight(ice_matches, "auto")
        if auto_ice_matches:
            return auto_ice_matches
        
        enforce_exact_matches = filter_matches_by_weight(exact_matches, "enforce")
        if enforce_exact_matches:
            return enforce_exact_matches
        
    if not segment.is_translated:
        auto_exact_matches = filter_matches_by_weight(exact_matches, "auto")
        if auto_exact_matches:
            return auto_exact_matches
        
    return []
        
                



def insert_algorithm(segment):
    entries = collect_all_entries()

    # select entries where there is a match of text with potential context binding
    if entries:
        ice_matches = get_ice_matches(segment, entries)
        exact_matches = get_exact_matches(segment, entries)

    weighed_matches = get_weighed_matches(segment, ice_matches, exact_matches)

    if len(weighed_matches) == 1:
        print("One weighed perfect match found: Done!")
    elif len(weighed_matches) > 1:
        print(f"Several ({len(weighed_matches)}) weighed perfect matches found, apply more criteria: file path")
        sorted_matches = sort_matches_by_filepath(weighed_matches)
        # print(len(sorted_matches))
        # pprint(sorted_matches)
        if len(sorted_matches) == 1:
            print("One only match found in the first file! Done :)")
            return sorted_matches[0]
        elif len(sorted_matches) > 1:
            print(f"Several ({len(sorted_matches)}) matches from the first file, apply more criteria: position")
            return sort_matches_by_position(sorted_matches)

    
segment = compose_segment()
if segment.is_translated and segment.has_context:
    exit("0. The translation will not be updated.")
insert_match = insert_algorithm(segment)
pprint([insert_match])

print("-----------------------------------------------------")

max_match_number = 10
matches = collect_all_entries()

# add similarity score
matches = [{**match, "score": fuzz.ratio(segment.source_text, match["source_sentence"])} 
                   for match in matches]

# add boolean property for context binding
matches = [{**match, "binding": has_context_binding(segment, match)} 
                   for match in matches]

# add auto-population weight (2=enforce, 1=auto, 0:none)
matches = [{**match, "weight": get_population_weight(match)} 
                   for match in matches]

# add rank by file paths

# add rank by position in file

sorted_matches = sorted(matches, key=lambda x: (-x['score'], -x['binding'], -x['weight'], x['filepath'], x['position']))
max_sorted_matches = sorted_matches[:max_match_number]

keys_order = ["score", "binding", "weight", "filepath", "position", "file", 
              "id", "source_language", "target_language", "source_sentence", "target_sentence"]
reordered_matches = [{key: m[key] for key in keys_order} for m in max_sorted_matches]
print(tabulate(reordered_matches, headers="keys", tablefmt="grid"))

# compare
keys_to_remove = {"score", "binding", "weight"}
original_dicts = [{k:v for k,v in d.items() if k not in keys_to_remove} for d in max_sorted_matches]

# print(original_dicts)
assert original_dicts[0] == insert_match