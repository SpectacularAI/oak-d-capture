"""
Sort JSONL file by a given field (default: time)
"""
import json, sys

def to_key(field):
    return lambda d: d[field]
DEFAULT_FIELD='time'
DEFAULT_KEY=to_key(DEFAULT_FIELD)

def sort_jsonl_stream_by(jsonl_stream, out_stream, key=DEFAULT_KEY):
    for d in sorted([json.loads(s) for s in jsonl_stream], key=key):
        out_stream.write(json.dumps(d)+'\n')

def sort_jsonl_by(jsonl_fn, out_fn, key=DEFAULT_KEY):
    with open(jsonl_fn) as f:
        data = sorted([json.loads(s) for s in f], key=key)
    with open(out_fn, 'wt') as f:
        for d in data:
            f.write(json.dumps(d)+'\n')

if __name__ == '__main__':
    import argparse
    p = argparse.ArgumentParser(__doc__.strip())
    p.add_argument('--field', default=DEFAULT_FIELD)
    p.add_argument('--input', default=sys.stdin, type=argparse.FileType('r'))
    p.add_argument('--output', default=sys.stdout, type=argparse.FileType('wt'))
    args = p.parse_args()
    sort_jsonl_stream_by(args.input, args.output, key=to_key(args.field))
