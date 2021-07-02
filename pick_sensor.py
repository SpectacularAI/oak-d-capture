"""
Pick certain sensor and filter out other stuff from JSONL
"""
import json, sys

def change_type(orig_type, target_type):
    if target_type == 'default':
        if any(x in orig_type for x in ('Internal', 'External')): return None
        return orig_type
    else:
        target_type = target_type.capitalize()
        if target_type in orig_type:
            return orig_type.replace(target_type, '')
        else:
            return None

def filter_jsonl_stream(input_stream, output_stream, type, round_ts=False):
    for line in input_stream:
        d = json.loads(line)
        if round_ts:
            if abs(d.get('time', 100)) < 0.01: d['time'] = 0
        s = d.get('sensor', None)
        if s is not None:
            s['type'] = change_type(s['type'], type)
            if s['type'] is None: continue
        output_stream.write(json.dumps(d)+'\n')
if __name__ == '__main__':
    import argparse
    p = argparse.ArgumentParser(__doc__.strip())
    p.add_argument('type', choices=["default", "internal", "external"])
    p.add_argument('--input', default=sys.stdin, type=argparse.FileType('r'))
    p.add_argument('--output', default=sys.stdout, type=argparse.FileType('wt'))
    p.add_argument('--round_ts', action='store_true', help='round nasty near-zero timestamps to zero')
    args = p.parse_args()
    filter_jsonl_stream(args.input, args.output, args.type, args.round_ts)
