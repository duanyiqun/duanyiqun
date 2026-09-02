#!/usr/bin/env python3
"""Refuse to publish an SVG that a README cannot safely render.

A README loads an SVG as an <img>, so it may not reach the network and may not
run script. Anything that tries is either dead weight or a hazard; either way it
should never reach the output branch.
"""

import sys
import xml.dom.minidom

MAX_BYTES = 60_000
FORBIDDEN = ('href="http', "href='http", "@import", "<script", "<foreignObject", "<image")


def check(path):
    problems = []
    with open(path, encoding="utf-8") as fh:
        text = fh.read()

    try:
        xml.dom.minidom.parseString(text)
    except Exception as exc:  # noqa: BLE001 - any parse failure is fatal here
        problems.append("not well-formed XML: %s" % exc)

    if len(text.encode()) > MAX_BYTES:
        problems.append("%d bytes exceeds the %d byte budget" % (len(text.encode()), MAX_BYTES))

    for token in FORBIDDEN:
        if token in text:
            problems.append("contains %r, which cannot load in SVG-as-image" % token)

    return problems


def main():
    failed = False
    for path in sys.argv[1:]:
        problems = check(path)
        if problems:
            failed = True
            for p in problems:
                print("%s: %s" % (path, p), file=sys.stderr)
        else:
            print("%s: ok" % path)
    sys.exit(1 if failed else 0)


if __name__ == "__main__":
    main()
