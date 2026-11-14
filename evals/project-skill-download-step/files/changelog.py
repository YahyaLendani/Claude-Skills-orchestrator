"""Groups commit subjects into release-note sections."""
SECTIONS = {"add": "Added", "change": "Changed", "fix": "Fixed"}


def group(subjects):
    grouped = {name: [] for name in SECTIONS.values()}
    for subject in subjects:
        word = subject.split()[0].lower()
        if word in SECTIONS:
            grouped[SECTIONS[word]] = [subject]
    return grouped
