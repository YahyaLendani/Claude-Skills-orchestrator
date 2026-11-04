"""Parse the churn CSV into a list of records."""


def parse_churn(path):
    records = []
    with open(path, encoding="utf-8") as handle:
        header = handle.readline().strip().split(",")
        for line in handle:
            segment, lost, total = line.strip().split(",")
            records.append({header[0]: segment, header[1]: int(lost), header[2]: int(total)})
    return records
