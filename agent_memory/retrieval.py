"""Stable lexical ranking baseline."""

from __future__ import annotations

import re

STOP = set("""a an and are as at be but by can do does for from get got how i if in into
is it its me my no not of on or out so that the their them then there these they this to
up was what when where which who why with you your please""".split())
WEIGHTS = (8.0, 10.0, 5.0, 1.0)
SYNTHESIS_BOOST = 1.08


def normalize_query(query: str) -> str:
    terms = []
    for term in re.findall(r"[a-z0-9_]+", query.casefold()):
        if len(term) > 2 and term not in STOP and term not in terms:
            terms.append(term)
    return " OR ".join(f'"{term}"*' for term in terms[:16])


def recall(db, query: str, limit=3, project=None, global_only=False):
    match = normalize_query(query)
    if not match:
        return []
    filters, params = ["documents_fts MATCH ?"], [match]
    if project:
        filters.append("documents.project=?")
        params.append(project)
    if global_only:
        filters.append("(documents.path LIKE 'wiki/%' OR documents.path LIKE 'global/%')")
    params.append(limit)
    weights = ",".join(map(str, WEIGHTS))
    rank = (f"bm25(documents_fts,{weights})*CASE WHEN documents.type IN "
            f"('wiki','global') THEN {SYNTHESIS_BOOST} ELSE 1.0 END")
    rows = db.execute(f"""SELECT documents.path,documents.title,documents.project,
      -({rank}) AS score,snippet(documents_fts,3,'[',']',' … ',18) AS snippet
      FROM documents_fts JOIN documents ON documents.id=documents_fts.rowid
      WHERE {' AND '.join(filters)} ORDER BY score DESC,documents.path LIMIT ?""", params)
    return [dict(row) for row in rows]
