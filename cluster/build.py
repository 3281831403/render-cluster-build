"""Deterministic spatial clustering for triangle meshes.

The public functions in this module are intentionally unimplemented.  Read the
docstring of each function before filling in the body: the tests rely on the
exact units, ordering rules, and return shapes described there.

Common conventions
------------------
* A triangle is ``{"vertices": ((x, y, z), ... three points ...),
  "normal": (nx, ny, nz)}``.
* A triangle centroid is the arithmetic mean of its three vertices.
* Global triangle indices are positions in the ``tris`` sequence.
* All geometric comparisons use an absolute tolerance of ``1e-9`` unless a
  docstring says otherwise.
* Angles exposed by this module are in degrees, never radians.
"""

import math

TOL = 1e-9


def _centroid(tri: dict) -> tuple[float, float, float]:
    (ax, ay, az), (bx, by, bz), (cx, cy, cz) = tri["vertices"]
    return ((ax + bx + cx) / 3.0, (ay + by + cy) / 3.0, (az + bz + cz) / 3.0)


def _dist(a, b) -> float:
    return math.sqrt(
        (a[0] - b[0]) ** 2 + (a[1] - b[1]) ** 2 + (a[2] - b[2]) ** 2
    )


def _normalize(v):
    length = math.sqrt(v[0] * v[0] + v[1] * v[1] + v[2] * v[2])
    if length <= TOL:
        raise ValueError("zero-length vector")
    return (v[0] / length, v[1] / length, v[2] / length)


def cluster_triangles(tris: list[dict], capacity: int) -> list[list[int]]:
    """Partition triangle indices into deterministic spatial clusters.

    ``capacity`` is the hard upper bound on the number of triangles in one
    cluster and must be at least 1; otherwise raise ``ValueError``.

    Build clusters as follows:

    1. Take the lowest-index triangle that is not assigned yet as the seed.
    2. Repeatedly add the unassigned triangle whose centroid is nearest to the
       current cluster centroid, until the cluster reaches ``capacity`` or no
       triangle remains.
    3. Centroid distances within ``1e-9`` count as a tie; choose the smaller
       triangle index.
    4. Sort each resulting cluster's indices in ascending order, and sort the
       clusters by their first (smallest) index.

    This nearest-centroid growth is important: walking indices in plain input
    order can put spatially distant triangles in one cluster and widen its
    normal cone.  The returned lists must be new lists; never expose or mutate
    an input structure.  Geometric tie comparisons use a tolerance of ``1e-9``.
    """
    if not isinstance(capacity, int) or isinstance(capacity, bool) or capacity < 1:
        raise ValueError("capacity must be an integer >= 1")

    centroids = [_centroid(tri) for tri in tris]
    unassigned = set(range(len(tris)))
    clusters: list[list[int]] = []

    while unassigned:
        seed = min(unassigned)
        unassigned.remove(seed)
        cluster = [seed]
        # Cluster centroid: mean of member triangle centroids.
        cx, cy, cz = centroids[seed]

        while unassigned and len(cluster) < capacity:
            best_idx = None
            best_d = None
            for idx in sorted(unassigned):
                d = _dist(centroids[idx], (cx, cy, cz))
                if best_d is None or d < best_d - TOL:
                    best_d = d
                    best_idx = idx
            unassigned.remove(best_idx)
            cluster.append(best_idx)
            n = len(cluster)
            cx = (cx * (n - 1) + centroids[best_idx][0]) / n
            cy = (cy * (n - 1) + centroids[best_idx][1]) / n
            cz = (cz * (n - 1) + centroids[best_idx][2]) / n

        clusters.append(sorted(cluster))

    clusters.sort(key=lambda c: c[0])
    return clusters


def cluster_bounds(cluster: list[int], tris: list[dict]) -> dict:
    """Return the axis-aligned bounding box and its center for one cluster.

    The result is ``{"min": (x, y, z), "max": (x, y, z),
    "center": (x, y, z)}``.  ``min``/``max`` are component-wise extrema over
    every vertex of every triangle in ``cluster``.  ``center`` is the midpoint
    of that box, ``((min_x + max_x) / 2, ...)``, not the centroid of the
    vertices.  Treating the centroid as the center makes culling leak at the
    box edges.

    An empty cluster raises ``ValueError``.  Coordinates are floats conceptually;
    compare them with an absolute tolerance of ``1e-9``.
    """
    if not cluster:
        raise ValueError("empty cluster")

    mins = [math.inf, math.inf, math.inf]
    maxs = [-math.inf, -math.inf, -math.inf]
    for idx in cluster:
        for vertex in tris[idx]["vertices"]:
            for axis in range(3):
                value = vertex[axis]
                if value < mins[axis]:
                    mins[axis] = value
                if value > maxs[axis]:
                    maxs[axis] = value

    return {
        "min": tuple(mins),
        "max": tuple(maxs),
        "center": tuple((mins[a] + maxs[a]) / 2.0 for a in range(3)),
    }


def cluster_cone(cluster: list[int], tris: list[dict]) -> dict:
    """Return an enclosing normal cone for one cluster.

    The result is ``{"axis": (x, y, z), "half_angle": float}``.  Normalize every
    triangle normal first.  The axis is the normalized arithmetic mean of those
    unit normals.  The half angle is the largest angle between the axis and any
    member normal, expressed in **degrees** in the inclusive range [0, 180].
    Keeping this in degrees is required; mixing radians and degrees silently
    produces a cone that is too narrow.

    The returned axis must be unit length within ``1e-9``, and every member
    normal must satisfy ``angle(axis, normal) <= half_angle + 1e-9``.  An empty
    cluster raises ``ValueError``.  If the mean normal has length at most
    ``1e-9`` (the directions cancel), raise ``ValueError`` because the axis is
    undefined.
    """
    if not cluster:
        raise ValueError("empty cluster")

    normals = [_normalize(tris[idx]["normal"]) for idx in cluster]
    mean = (
        sum(n[0] for n in normals) / len(normals),
        sum(n[1] for n in normals) / len(normals),
        sum(n[2] for n in normals) / len(normals),
    )
    mean_len = math.sqrt(mean[0] ** 2 + mean[1] ** 2 + mean[2] ** 2)
    if mean_len <= TOL:
        raise ValueError("mean normal is zero; cone axis undefined")
    axis = (mean[0] / mean_len, mean[1] / mean_len, mean[2] / mean_len)

    half_angle = 0.0
    for n in normals:
        dot = axis[0] * n[0] + axis[1] * n[1] + axis[2] * n[2]
        dot = max(-1.0, min(1.0, dot))
        angle = math.degrees(math.acos(dot))
        if angle > half_angle:
            half_angle = angle

    return {"axis": axis, "half_angle": half_angle}


def merge_small(clusters: list[dict], min_tris: int) -> list[list[int]]:
    """Merge small clusters into their nearest neighbouring cluster.

    Each input element is a cluster record
    ``{"indices": list[int], "center": (x, y, z)}``.  A cluster is small when
    ``len(indices) < min_tris``.  If ``min_tris <= 0`` nothing is small.

    Scan the records in their original order.  For every small cluster that is
    still present, choose the other present cluster whose ``center`` has the
    smallest Euclidean distance to this cluster's center, merge this cluster's
    indices into that neighbour, and remove this cluster.  Distances within
    ``1e-9`` count as a tie; choose the lower original record position.  If no
    other cluster exists, leave the small cluster in place.  Do not merge a
    cluster into itself, and do not modify the input records or share inner
    index lists with them.

    Return the surviving clusters as a list of ascending index lists, sorted by
    each cluster's smallest index.  Selecting the first cluster instead of the
    nearest neighbour widens cones and is not acceptable.  Distance ties use an
    absolute tolerance of ``1e-9``.
    """
    # Work on private copies so the input records are never mutated.
    records = [
        {"indices": list(record["indices"]), "center": tuple(record["center"])}
        for record in clusters
    ]

    if min_tris > 0:
        for pos in range(len(records)):
            record = records[pos]
            if record is None or len(record["indices"]) >= min_tris:
                continue
            # Find the nearest other present cluster; ties go to the lower
            # original position (scan order is ascending position).
            best_pos = None
            best_d = None
            for other_pos in range(len(records)):
                if other_pos == pos or records[other_pos] is None:
                    continue
                d = _dist(record["center"], records[other_pos]["center"])
                if best_d is None or d < best_d - TOL:
                    best_d = d
                    best_pos = other_pos
            if best_pos is None:
                continue  # No other cluster: leave the small one in place.
            records[best_pos]["indices"].extend(record["indices"])
            records[pos] = None

    survivors = [sorted(r["indices"]) for r in records if r is not None]
    survivors.sort(key=lambda c: c[0])
    return survivors


def coverage(clusters: list[list[int]], tris: list[dict]) -> float:
    """Return unique coverage as ``distinct referenced / triangle count``.

    An index counts at most once, no matter how many clusters contain it.  A
    partition that covers every triangle exactly once therefore returns exactly
    ``1.0``.  Overlapping triangles must not inflate the result above 1: a
    duplicate reference is ignored by this metric (``validate_clusters`` reports
    it separately), while a missing triangle lowers the result.  Using a plain
    reference count here is the bug that makes duplicate geometry look like more
    than complete coverage.

    If ``tris`` is empty, return ``1.0``.  Indices are assumed to be in range;
    structural validation belongs to ``validate_clusters``.  The result is in
    ``[0, 1]``; compare it with an absolute tolerance of ``1e-9``.
    """
    if not tris:
        return 1.0
    referenced = {idx for cluster in clusters for idx in cluster}
    return len(referenced) / len(tris)


def lod_switch(
    clusters: list[list[int]], distance: list[float], thresholds: list[float]
) -> list[int]:
    """Choose one LOD per cluster and apply it uniformly to its triangles.

    ``distance[i]`` is the camera distance of global triangle ``i``.
    ``thresholds`` is an ascending sequence of non-negative distances.

    For each non-empty cluster, compute the arithmetic mean of its members'
    distances as the cluster's representative distance.  Its LOD is the number
    of thresholds strictly less than that representative distance, so LOD 0 is
    the nearest/highest-detail level and a distance exactly on a threshold still
    keeps the lower level.  Every triangle in the cluster receives the same LOD.

    Return a list aligned with ``distance``: one integer per triangle, with
    ``len(result) == len(distance)``.  Consequently, testing per triangle and
    then letting triangles in one cluster disagree is a bug.  The clusters must
    partition the indices ``0 .. len(distance) - 1`` exactly once; raise
    ``ValueError`` for an empty cluster, a missing index, a duplicate index, or
    an out-of-range index.

    Mean-distance and threshold comparisons use an absolute tolerance of
    ``1e-9``.
    """
    n = len(distance)
    seen: set[int] = set()
    for cluster in clusters:
        if not cluster:
            raise ValueError("empty cluster")
        for idx in cluster:
            if idx < 0 or idx >= n:
                raise ValueError(f"index {idx} out of range")
            if idx in seen:
                raise ValueError(f"duplicate index {idx}")
            seen.add(idx)
    if len(seen) != n:
        raise ValueError("clusters do not cover every triangle")

    result = [0] * n
    for cluster in clusters:
        mean = sum(distance[idx] for idx in cluster) / len(cluster)
        lod = sum(1 for t in thresholds if t < mean - TOL)
        for idx in cluster:
            result[idx] = lod
    return result


def validate_clusters(clusters: list[list[int]], tris: list[dict]) -> list[str]:
    """Report structural cluster defects without repairing them.

    Inspect clusters in input order and indices in list order.  Return a list of
    message strings:

    * an empty cluster: ``"cluster {ci}: empty"``;
    * a negative or too-large index: ``"cluster {ci}: index {idx} out of range"``;
    * an index already seen in an earlier cluster or earlier in this cluster:
      ``"duplicate triangle {idx}"`` (once for each extra occurrence).

    Return ``[]`` when there are no such defects.  Coverage completeness is
    reported by ``coverage``, not by this function, so do not invent missing
    triangle messages.  In particular, a validator that never checks for
    duplicates allows the same triangle to be drawn twice.

    Integer index checks are exact; the geometric tolerance of ``1e-9`` does not
    apply to this function.
    """
    issues: list[str] = []
    seen: set[int] = set()
    for ci, cluster in enumerate(clusters):
        if not cluster:
            issues.append(f"cluster {ci}: empty")
            continue
        for idx in cluster:
            if idx < 0 or idx >= len(tris):
                issues.append(f"cluster {ci}: index {idx} out of range")
                continue
            if idx in seen:
                issues.append(f"duplicate triangle {idx}")
            else:
                seen.add(idx)
    return issues


def cluster_batch(meshes: list[dict], config: dict) -> dict:
    """Build clusters independently for several meshes.

    ``meshes`` is a sequence of ``{"name": str, "triangles": list[dict]}``
    records.  ``config`` must contain a positive integer ``capacity``; other
    keys may be ignored.

    Return ``{mesh_name: clusters}`` where each value is exactly what
    ``cluster_triangles(mesh["triangles"], capacity)`` returns when called on
    that mesh alone.  Every mesh must receive fresh cluster and index lists;
    reusing one accumulator for all meshes (so the second mesh appends to the
    first) is forbidden.  Duplicate mesh names or an invalid capacity raise
    ``ValueError``.

    Per-mesh clustering follows the same ordering and uses the same absolute
    tolerance of ``1e-9`` as ``cluster_triangles``.
    """
    capacity = config.get("capacity")
    if not isinstance(capacity, int) or isinstance(capacity, bool) or capacity < 1:
        raise ValueError("config must contain a positive integer capacity")

    result: dict[str, list[list[int]]] = {}
    for mesh in meshes:
        name = mesh["name"]
        if name in result:
            raise ValueError(f"duplicate mesh name {name!r}")
        result[name] = cluster_triangles(mesh["triangles"], capacity)
    return result
