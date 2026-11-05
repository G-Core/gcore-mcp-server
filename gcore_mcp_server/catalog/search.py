"""A small dependency-free BM25 index for searching the SDK catalog."""

from __future__ import annotations

import math
import re
from collections import Counter

_CAMEL = re.compile(r"(?<=[a-z0-9])(?=[A-Z])")
_SPLIT = re.compile(r"[^A-Za-z0-9]+")

# Common English words and API filler that would otherwise dominate scores.
_STOP = frozenset(
    "a an and are as at be by for from how i in is it me my of on or "
    "the this to what which with all can do does please give find".split()
)

# Map user vocabulary onto SDK vocabulary.
_SYNONYMS: dict[str, tuple[str, ...]] = {
    "vm": ("instances",),
    "vms": ("instances",),
    "server": ("instances", "servers"),
    "servers": ("instances", "servers"),
    "machine": ("instances",),
    "machines": ("instances",),
    "disk": ("volumes",),
    "disks": ("volumes",),
    "ip": ("floating", "ips", "reserved"),
    "ips": ("floating", "ips", "reserved"),
    "firewall": ("security", "groups", "firewall"),
    "firewalls": ("security", "groups", "firewall"),
    "sg": ("security", "groups"),
    "kubernetes": ("k8s",),
    "cluster": ("clusters",),
    "lb": ("load", "balancers"),
    "loadbalancer": ("load", "balancers"),
    "loadbalancers": ("load", "balancers"),
    "key": ("keys",),
    "ssh": ("ssh", "keys"),
    "bucket": ("buckets", "storage"),
    "buckets": ("buckets", "storage"),
    "domain": ("domains", "zones"),
    "record": ("records", "rrsets"),
    "records": ("records", "rrsets"),
    "dns": ("dns", "zones"),
    "cost": ("cost", "reports"),
    "costs": ("cost", "reports"),
    "billing": ("cost", "reports", "usage"),
    "quota": ("quotas",),
    "limits": ("quotas", "limits"),
    "remove": ("delete",),
    "show": ("list", "get"),
    "reboot": ("reboot", "action"),
    "restart": ("reboot", "action"),
    "start": ("start", "action"),
    "stop": ("stop", "action"),
    "make": ("create",),
    "add": ("create", "add"),
    "new": ("create",),
    "unattached": ("volumes", "list"),
    "network": ("networks",),
    "subnet": ("subnets",),
    "image": ("images",),
    "flavor": ("flavors",),
    "size": ("flavors",),
    "sizes": ("flavors",),
    "region": ("regions",),
    "project": ("projects",),
    "snapshot": ("snapshots",),
    "secret": ("secrets",),
    "certificate": ("certificates", "ssl"),
    "cert": ("certificates", "ssl"),
    "cache": ("purge", "prefetch"),
    "video": ("videos", "streaming"),
    "stream": ("streams", "streaming"),
}


_PHRASES: tuple[tuple[re.Pattern[str], str], ...] = (
    (re.compile(r"\bvirtual machines?\b", re.I), "instances"),
    (re.compile(r"\bload balancers?\b", re.I), "load_balancers"),
    (re.compile(r"\bsecurity groups?\b", re.I), "security_groups"),
    (re.compile(r"\bfloating ips?\b", re.I), "floating_ips"),
    (re.compile(r"\bssh keys?\b", re.I), "ssh_keys"),
    (re.compile(r"\bdns records?\b", re.I), "dns rrsets"),
)


def normalize_phrases(text: str) -> str:
    """Rewrite multi-word user phrases into SDK resource names."""
    for pattern, replacement in _PHRASES:
        text = pattern.sub(replacement, text)
    return text


def tokenize(text: str) -> list[str]:
    """Lower-case word tokens, split on punctuation, underscores and camelCase."""
    tokens: list[str] = []
    for piece in _SPLIT.split(_CAMEL.sub(" ", text)):
        tok = piece.lower()
        if tok and tok not in _STOP:
            tokens.append(tok)
    return tokens


def expand_query(tokens: list[str]) -> list[str]:
    """Add SDK-vocabulary synonyms to the query tokens."""
    out = list(tokens)
    for tok in tokens:
        out.extend(_SYNONYMS.get(tok, ()))
        if tok.endswith("s") and len(tok) > 3:
            out.append(tok[:-1])
        else:
            out.append(tok + "s")
    return out


class BM25Index:
    """Okapi BM25 over pre-tokenized documents."""

    def __init__(self, docs: list[list[str]], k1: float = 1.2, b: float = 0.75):
        self.k1 = k1
        self.b = b
        self.tfs = [Counter(d) for d in docs]
        self.lengths = [len(d) for d in docs]
        n = len(docs)
        self.avg_len = (sum(self.lengths) / n) if n else 0.0
        df: Counter[str] = Counter()
        for d in docs:
            df.update(set(d))
        self.idf = {t: math.log(1 + (n - f + 0.5) / (f + 0.5)) for t, f in df.items()}

    def scores(self, query: list[str]) -> list[float]:
        """BM25 score of every document for ``query``."""
        out: list[float] = []
        for tf, length in zip(self.tfs, self.lengths):
            s = 0.0
            norm = self.k1 * (1 - self.b + self.b * length / (self.avg_len or 1))
            for term in query:
                f = tf.get(term)
                if f:
                    s += self.idf.get(term, 0.0) * f * (self.k1 + 1) / (f + norm)
            out.append(s)
        return out
