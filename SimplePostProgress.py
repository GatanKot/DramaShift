import sys


class SimplePostProgress:
    def __init__(self, desc="Fetched", unit="Posts"):
        self.desc = desc
        self.unit = unit
        self.count = 0

    def update(self, new_count):
        self.count = new_count
        sys.stdout.write(f"\r{self.desc}: {self.count} {self.unit}")
        sys.stdout.flush()

    def close(self):
        sys.stdout.write('\n')
        sys.stdout.flush()
